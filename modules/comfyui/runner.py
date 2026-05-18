import asyncio
import datetime
import io
import json
import os
import random
import urllib.parse
import uuid

import httpx
import websocket
from PIL import Image

from modules.save import DataSaver

from .checker import WorkflowChecker
from .workflow import (
    ComfyUIWorkflow,
    build_comfyui_spec,
    printError,
    printInfo,
    printWarning,
)


class ComufyClient:
    def __init__(self, hostname="http://127.0.0.1:8188") -> None:
        self.client = httpx.AsyncClient()
        self.hostname = hostname
        self.server_address = self.hostname.replace("http://", "").replace(
            "https://", ""
        )
        self.saver = None
        self.checker = WorkflowChecker()

    async def queuePrompt(self, prompt, client_id):
        req = await self.client.post(
            f"{self.hostname}/prompt", json={"prompt": prompt, "client_id": client_id}
        )
        if req.status_code != 200:
            printError("Failed to queue prompt")
            raise Exception(req.text)
        return req.json()

    async def getHistory(self, prompt_id):
        res = await self.client.get(f"{self.hostname}/history/{prompt_id}")
        if res.status_code != 200:
            raise Exception(res.text)
        return res.json()

    async def getImages(self, ws, prompt, client_id):
        try:
            start_time = datetime.datetime.now()
            res = await self.queuePrompt(prompt, client_id)
            prompt_id = res["prompt_id"]
            output_images = {}
            current_node = ""
            while True:
                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    msg_type = message.get("type")
                    data = message.get("data", {})
                    if msg_type == "executing":
                        if data["prompt_id"] == prompt_id:
                            if data["node"] is None:
                                duration = datetime.datetime.now() - start_time
                                print(
                                    f"Execution is done {duration.total_seconds():.2f} sec"
                                )
                                break
                            current_node = data["node"]
                    elif msg_type == "progress":
                        value = data.get("value")
                        max_value = data.get("max")
                        node = data.get("node") or current_node
                        duration = datetime.datetime.now() - start_time
                        print(
                            f"\r\033[Kprogress node={node}: {value}/{max_value} {duration.total_seconds():.2f} sec",
                            end="",
                        )

                    elif msg_type == "executed":
                        node = data.get("node")
                    elif msg_type == "execution_error":
                        raise RuntimeError(data)
                elif current_node == "save_image_websocket_node":
                    print(f"\r\033[K", end="")
                    output_images.setdefault(current_node, []).append(out[8:])
            return output_images
        except KeyboardInterrupt:
            printWarning("Interrupted")
            await self.client.post(f"{self.hostname}/interrupt")
            raise

    async def imageWrapper(self, images, prompt_text, options, info=None):
        info = info or {}
        infotexts = json.dumps(prompt_text, ensure_ascii=False)
        if "prompt" in info:
            infotexts = info["prompt"] + "\n"
            if "negative_prompt" in info:
                infotexts += f"Negative prompt: {info['negative_prompt']}\n"
            infotexts += self.build_a1111_metadata_line(info)
        return {
            "info": {"infotexts": [infotexts]},
            "parameters": dict(info),
            "images": images,
        }, options

    @staticmethod
    def build_a1111_metadata_line(info):
        mapping = [
            ("Steps", "steps"),
            ("Sampler", "sampler_name"),
            ("Schedule type", "scheduler"),
            ("CFG scale", "cfg_scale"),
            ("Seed", "seed"),
            ("Size", None),
            ("Model", "sd_model_name"),
            ("VAE", "sd_vae_name"),
            ("Clip skip", "clip_skip"),
            ("Denoising strength", "denoising_strength"),
        ]
        parts = []
        for label, key in mapping:
            if label == "Size":
                width = info.get("width")
                height = info.get("height")
                if width is not None and height is not None:
                    parts.append(f"{label}: {width}x{height}")
                continue
            value = info.get(key)
            if value is None:
                continue
            parts.append(f"{label}: {value}")
        return ", ".join(parts)

    @staticmethod
    def build_save_options(options, prompt_text):
        save_options = dict(options or {})
        if not isinstance(prompt_text, dict):
            return save_options
        if "verbose" in prompt_text:
            save_options["verbose"] = prompt_text["verbose"]
        if "variables" in prompt_text:
            save_options["variables"] = prompt_text["variables"]
        if "values" in prompt_text:
            save_options["values"] = prompt_text["values"]
        if "attributes" in prompt_text:
            save_options["attributes"] = prompt_text["attributes"]
        if "filepart" in prompt_text:
            save_options["filepart"] = prompt_text["filepart"]
        if "info" in prompt_text and isinstance(prompt_text["info"], dict):
            save_options["info"] = prompt_text["info"]
        if "command" in prompt_text and isinstance(prompt_text["command"], dict):
            save_options["command"] = prompt_text["command"]
        return save_options

    async def saveImage(
        self, image_data, prompt, options=None, info=None, prompt_text=None
    ):
        options = options or {}
        info = info or {}
        prompt_text = prompt_text or {}
        try:
            r, options = await self.imageWrapper(
                [image_data], prompt_text, options, info
            )
            options = self.build_save_options(options, prompt_text)
            options["workflow"] = json.dumps(prompt, ensure_ascii=False)
            if self.saver is None:
                self.saver = DataSaver()
            await self.saver.asave_images(r, options)
        except Exception:
            image = Image.open(io.BytesIO(image_data))
            directory = options.get("dir", "outputs")
            os.makedirs(directory, exist_ok=True)
            imagename = datetime.datetime.now().strftime("%H%M%S")
            image.save(f"{directory}/img{imagename}.png")

    async def uploadImage(
        self, filename, binary=None, minetype="image/png", overwrite=False
    ):
        if binary is None:
            with open(filename, "rb") as f:
                binary = f.read()
        payload = {"image": (os.path.basename(filename), binary, minetype)}
        if overwrite:
            payload["overwrite"] = True  # type: ignore
        res = await self.client.post(f"{self.hostname}/upload/image", files=payload)
        if res.status_code != 200:
            raise Exception(res.text)
        return res.json()

    async def prepare_workflow_assets(self, workflow):
        workflow = json.loads(json.dumps(workflow))
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            if node.get("class_type") not in {"LoadImage", "LoadImageMask"}:
                continue
            image_path = node.get("inputs", {}).get("image")
            if isinstance(image_path, str) and os.path.exists(image_path):
                uploaded = await self.uploadImage(image_path, overwrite=True)
                name = (
                    uploaded.get("name")
                    or uploaded.get("filename")
                    or os.path.basename(image_path)
                )
                node["inputs"]["image"] = name
        return workflow

    async def arun(self, prompts, options=None):
        options = options or {}
        ws = websocket.WebSocket()
        for i, _prompt in enumerate(prompts):
            prompt = _prompt.get("workflow")
            info = _prompt.get("info", {})
            prompt_text = _prompt["prompt_text"]
            printInfo(f"process queuing {i+1}/{len(prompts)}")
            client_id = str(uuid.uuid4())
            ws.connect(f"ws://{self.server_address}/ws?clientId={client_id}")
            images = await self.getImages(ws, prompt, client_id)
            if images is None:
                continue
            for node_id in images:
                seed = int(info.get("seed", -1))
                for image_data in images[node_id]:
                    current_info = info.copy()
                    if seed > 0:
                        current_info["seed"] = seed
                        seed += 1
                    await self.saveImage(
                        image_data, prompt, options, current_info, prompt_text
                    )
            ws.close()

    def run(self, prompt, options=None):
        asyncio.run(self.arun(prompt, options or {}))

    def checkWorkflow(self, workflow, options=None):
        return self.checker.check(workflow, self.hostname, options or {})

    @staticmethod
    def _is_native_workflow_payload(prompt_text):
        if not isinstance(prompt_text, dict):
            return False
        if "workflow" not in prompt_text:
            return False
        workflow = prompt_text.get("workflow")
        if not isinstance(workflow, dict):
            return False
        return all(isinstance(node, dict) for node in workflow.values())

    @staticmethod
    def txt2img(
        prompts,
        vae=None,
        hostname="http://127.0.0.1:8188",
        output_dir="outputs",
        options=None,
    ):
        try:
            options = options or {}
            sd_model = options.get("sd_model", None)
            vae = options.get("sd_vae", vae)
            wf = ComfyUIWorkflow()
            wf.setModel(sd_model)
            wf.setVAE(vae)
            client = ComufyClient(hostname=hostname)
            workflows = []
            for prompt_text in prompts:
                opt = copy_options = options.copy()
                if client._is_native_workflow_payload(prompt_text):
                    workflow = json.loads(json.dumps(prompt_text["workflow"]))
                    workflow.pop("verbose", None)
                    workflow, info = client.checkWorkflow(workflow, opt)
                    if info is None:
                        continue
                    workflows.append(
                        {
                            "workflow": workflow,
                            "info": info,
                            "prompt_text": prompt_text,
                        }
                    )
                    continue
                if (
                    prompt_text.get("prompt") is None
                    and prompt_text.get("comfyui") is None
                    and prompt_text.get("workflow") is None
                ):
                    workflow = json.loads(json.dumps(prompt_text))
                    workflow.pop("verbose", None)
                    workflow, info = client.checkWorkflow(workflow, opt)
                    if info is None:
                        continue
                    workflows.append(
                        {"workflow": workflow, "info": info, "prompt_text": prompt_text}
                    )
                    continue

                spec, merged = build_comfyui_spec(prompt_text, opt)
                if spec.get("model") is None:
                    spec["model"] = sd_model
                n_iter = prompt_text.get("n_iter", 1)
                sampler_name = merged.get(
                    "sampler_name", prompt_text.get("sampler_name")
                )
                if sampler_name is not None:
                    spec.setdefault("sampling", {})
                    spec["sampling"]["sampler_name"] = sampler_name
                seed = spec.get("sampling", {}).get("seed", -1)
                if seed == -1:
                    seed = random.randint(0, 2**31 - 1)
                for _ in range(n_iter):
                    spec["sampling"]["seed"] = seed
                    workflow, info = wf.createWorkflowFromSpec(spec, merged)
                    workflow = asyncio.run(client.prepare_workflow_assets(workflow))
                    workflow, checked = client.checkWorkflow(workflow, merged)
                    if workflow is None:
                        continue
                    if checked:
                        info.update(checked)
                    workflows.append(
                        {"workflow": workflow, "info": info, "prompt_text": prompt_text}
                    )
                    if seed > 0:
                        seed += info.get("batch_size", 1)
            options = dict(options)
            options["dir"] = output_dir
            client.run(workflows, options)
            return True
        except Exception as e:
            printError("Failed to run comfyui", e)
            return False

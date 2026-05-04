import json
import re

import httpx

from .workflow import printDebug, printError, printVerbose, printWarning


class WorkflowChecker:
    def __init__(self):
        self.object_info = None
        self._control_escape_map = {
            "\a": r"\a",
            "\b": r"\b",
            "\f": r"\f",
            "\n": r"\n",
            "\r": r"\r",
            "\t": r"\t",
            "\v": r"\v",
        }
        self._sampler_aliases = {
            "dpm++ 2m": {"sampler": "dpmpp_2m", "scheduler": "karras"},
            "dpm++ sde": {"sampler": "dpmpp_sde", "scheduler": "karras"},
            "dpm++ 2m sde": {"sampler": "dpmpp_2m_sde", "scheduler": "karras"},
            "dpm++ 2m sde heun": {
                "sampler": "dpmpp_2m_sde_heun",
                "scheduler": "karras",
            },
            "dpm++ 2s a": {"sampler": "dpmpp_2s_a", "scheduler": "karras"},
            "dpm++ 3m sde": {"sampler": "dpmpp_3m_sde", "scheduler": "karras"},
            "euler a": {"sampler": "euler_ancestral", "scheduler": "normal"},
            "euler ancestral": {"sampler": "euler_ancestral", "scheduler": "normal"},
            "euler": {"sampler": "euler", "scheduler": "normal"},
            "lms": {"sampler": "lms", "scheduler": "normal"},
            "heun": {"sampler": "heun", "scheduler": "normal"},
            "dpm2": {"sampler": "dpm_2", "scheduler": "normal"},
            "dpm2 a": {"sampler": "dpm_2_ancestral", "scheduler": "normal"},
            "dpm2 ancestral": {"sampler": "dpm_2_ancestral", "scheduler": "normal"},
            "dpm fast": {"sampler": "dpm_fast", "scheduler": "normal"},
            "dpm adaptive": {"sampler": "dpm_adaptive", "scheduler": "normal"},
            "restart": {"sampler": None, "scheduler": "normal"},
            "ddim": {"sampler": "ddim", "scheduler": "normal"},
            "plms": {"sampler": "plms", "scheduler": "normal"},
            "unipc": {"sampler": "unipc", "scheduler": "normal"},
            "uni_pc": {"sampler": "uni_pc", "scheduler": "normal"},
            "uni pc": {"sampler": "uni_pc", "scheduler": "normal"},
            "uni_pc_bh2": {"sampler": "uni_pc_bh2", "scheduler": "normal"},
            "uni pc bh2": {"sampler": "uni_pc_bh2", "scheduler": "normal"},
            "lcm": {"sampler": "lcm", "scheduler": "normal"},
        }

    def _add_issue(self, issues, node_id, class_type, message):
        issues.append(
            {
                "node_id": str(node_id),
                "class_type": class_type or "<unknown>",
                "message": message,
            }
        )

    def _format_issue(self, issue):
        return (
            f"Workflow issue node={issue['node_id']} "
            f"class={issue['class_type']}: {issue['message']}"
        )

    def _restore_backslash_escapes(self, value):
        if not isinstance(value, str):
            return value
        normalized = value
        for raw, escaped in self._control_escape_map.items():
            normalized = normalized.replace(raw, escaped)
        return normalized

    def _normalize_sampler_config(self, sampler_name, scheduler_name):
        if not isinstance(sampler_name, str):
            return sampler_name, scheduler_name
        alias = self._sampler_aliases.get(sampler_name.strip().lower())
        if alias is None:
            return sampler_name, scheduler_name
        normalized_sampler = alias.get("sampler") or sampler_name
        normalized_scheduler = alias.get("scheduler") or scheduler_name
        printVerbose(
            f"Sampler {sampler_name} converted to "
            f"sampler={normalized_sampler}, scheduler={normalized_scheduler}"
        )
        return normalized_sampler, normalized_scheduler

    def _iter_linked_node_ids(self, value):
        if isinstance(value, list):
            if (
                len(value) >= 2
                and isinstance(value[0], str)
                and isinstance(value[1], int)
            ):
                yield value[0]
                return
            for item in value:
                yield from self._iter_linked_node_ids(item)
        elif isinstance(value, dict):
            for item in value.values():
                yield from self._iter_linked_node_ids(item)

    def _collect_active_node_ids(self, workflow, object_info, issues=None):
        output_nodes = []
        for node_id, node in workflow.items():
            if not isinstance(node, dict):
                continue
            class_type = node.get("class_type")
            if not class_type:
                continue
            if object_info.get(class_type, {}).get("output_node"):
                output_nodes.append(node_id)
        if not output_nodes:
            return set(workflow.keys())

        active = set()
        stack = list(output_nodes)
        while stack:
            node_id = stack.pop()
            if node_id in active or node_id not in workflow:
                continue
            node = workflow[node_id]
            if not isinstance(node, dict):
                continue
            active.add(node_id)
            for linked_id in self._iter_linked_node_ids(node.get("inputs", {})):
                if linked_id not in workflow:
                    if issues is not None:
                        self._add_issue(
                            issues,
                            node_id,
                            node.get("class_type"),
                            f"linked node {linked_id} not found",
                        )
                    continue
                if linked_id not in active:
                    stack.append(linked_id)
        return active

    def _value_in_required(self, value, required_values):
        for allowed in required_values or []:
            if isinstance(allowed, (list, tuple, set)):
                if value in allowed:
                    return True
            elif value == allowed:
                return True
        return False

    def _model_search(self, model_name, required):
        model_name = self._restore_backslash_escapes(model_name)
        ext = re.compile(r"\.(safetensors|pt|ckpt)$")
        base_name = ext.sub("", model_name)
        parsed = self.object_info.get("parsed", {})  # type: ignore
        alternames = []
        for model_names in required:
            if model_name in model_names:
                return True, []
            converted = model_name.replace("\\", "/")
            if converted in model_names:
                return True, [converted]
            converted = model_name.replace("/", "\\")
            if converted in model_names:
                return True, [converted]
            for name in model_names:
                parsed_name = parsed.get(name)
                if parsed_name is None:
                    parsed_name = ext.sub("", name)
                    parsed[name] = parsed_name
                if parsed_name.endswith(base_name) or name.endswith(model_name):
                    alternames.append(name)
        self.object_info["parsed"] = parsed  # type: ignore
        return False, alternames

    def _prompt_search(self, workflow, object_info, position, prompt=""):
        node_id = position[0]
        node = workflow[node_id]
        class_type = node["class_type"]
        role = node.get("_meta", {}).get("role")
        if class_type == "CLIPTextEncode":
            return node["inputs"].get("text", "") + prompt
        if class_type == "CLIPTextEncodeSDXL":
            return node["inputs"].get("text_g", "") + prompt
        if class_type == "CLIPTextEncodeSD3":
            return node["inputs"].get("text", "") + prompt
        if class_type == "ConditioningConcat":
            a = self._prompt_search(
                workflow, object_info, node["inputs"]["conditioning_from"]
            )
            b = self._prompt_search(
                workflow, object_info, node["inputs"]["conditioning_to"]
            )
            return a + " BREAK " + b
        if role in {"positive", "negative"}:
            if "text" in node["inputs"]:
                return node["inputs"]["text"]
            if "text_g" in node["inputs"]:
                return node["inputs"]["text_g"]
        try:
            required = (
                object_info.get(class_type, {}).get("input", {}).get("required", {})
            )
            for key, definition in required.items():
                node_type = definition[0]
                if node_type == "CONDITIONING" and key in node["inputs"]:
                    return self._prompt_search(
                        workflow, object_info, node["inputs"][key]
                    )
        except Exception as e:
            printError("Failed to search prompt", e)
        return prompt

    def check(self, workflow, hostname, options=None):
        options = options or {}
        workflow = workflow.copy()
        if self.object_info is None:
            with httpx.Client() as client:
                try:
                    res = client.get(hostname + "/object_info")
                except httpx.TimeoutException as e:
                    printError("Connect timeout, Server is down?")
                    raise e
                except httpx.RequestError as e:
                    printError(f"Failed to get models {e}")
                    raise Exception(f"Failed to get models {e}")
                if res is None:
                    printError("Failed to get models")
                    return None, None
                if res.status_code != 200:
                    printError("Failed to check workflow, object info not found")
                    return None, None
                self.object_info = {"object_info": res.json()}
        object_info = self.object_info["object_info"]
        printDebug("ComfyUI object_info")
        info = {}
        positive = None
        negative = None
        issues = []
        active_nodes = self._collect_active_node_ids(workflow, object_info, issues)
        for node_id, node in workflow.items():
            if node_id not in active_nodes or not isinstance(node, dict):
                continue
            printDebug(f"Checking node {node_id}")
            class_type = node.get("class_type")
            if class_type is None:
                self._add_issue(issues, node_id, None, "class_type not found")
                continue
            if class_type not in object_info:
                self._add_issue(
                    issues, node_id, class_type, "class type not found in object_info"
                )
                continue
            inputs = node.get("inputs", {})
            if not isinstance(inputs, dict):
                self._add_issue(issues, node_id, class_type, "inputs is not a dict")
                continue
            required = object_info[class_type].get("input", {}).get("required", {})
            missing_required = []
            for key in required:
                if key not in inputs:
                    missing_required.append(key)
                    self._add_issue(
                        issues, node_id, class_type, f"required input '{key}' not found"
                    )
            if missing_required:
                continue
            if class_type == "KSampler":
                normalized_sampler, normalized_scheduler = (
                    self._normalize_sampler_config(
                        inputs["sampler_name"], inputs.get("scheduler")
                    )
                )
                if normalized_sampler != inputs["sampler_name"]:
                    node["inputs"]["sampler_name"] = normalized_sampler
                    inputs["sampler_name"] = normalized_sampler
                if (
                    normalized_scheduler is not None
                    and normalized_scheduler != inputs.get("scheduler")
                ):
                    node["inputs"]["scheduler"] = normalized_scheduler
                    inputs["scheduler"] = normalized_scheduler
                info["sampler_name"] = inputs["sampler_name"]
                info["scheduler"] = inputs["scheduler"]
                info["steps"] = inputs["steps"]
                info["seed"] = inputs["seed"]
                info["cfg_scale"] = inputs["cfg"]
                info["denoising_strength"] = inputs["denoise"]
                positive = inputs.get("positive", positive)
                negative = inputs.get("negative", negative)
                if not self._value_in_required(
                    info["sampler_name"], required.get("sampler_name", [])
                ):
                    self._add_issue(
                        issues,
                        node_id,
                        class_type,
                        f"sampler '{info['sampler_name']}' not found",
                    )
                if not self._value_in_required(
                    info["scheduler"], required.get("scheduler", [])
                ):
                    self._add_issue(
                        issues,
                        node_id,
                        class_type,
                        f"scheduler '{info['scheduler']}' not found",
                    )
            elif class_type == "CLIPSetLastLayer":
                if inputs["stop_at_clip_layer"] >= 0:
                    self._add_issue(
                        issues,
                        node_id,
                        class_type,
                        "stop_at_clip_layer must be negative",
                    )
                info["clip_skip"] = abs(inputs["stop_at_clip_layer"])
            elif class_type == "VAELoader":
                normalized_name = self._restore_backslash_escapes(inputs["vae_name"])
                if normalized_name != inputs["vae_name"]:
                    node["inputs"]["vae_name"] = normalized_name
                    inputs["vae_name"] = normalized_name
                info["sd_vae_name"] = inputs["vae_name"]
                if "vae_name" in required:
                    ok, alternames = self._model_search(
                        info["sd_vae_name"], required["vae_name"]
                    )
                    if not ok and alternames:
                        printWarning(
                            f"VAE {info['sd_vae_name']} not found, but found similar models {alternames} use {alternames[0]}"
                        )
                        node["inputs"]["vae_name"] = alternames[0]
                        info["sd_vae_name"] = alternames[0]
                    elif not ok:
                        self._add_issue(
                            issues,
                            node_id,
                            class_type,
                            f"vae '{info['sd_vae_name']}' not found"
                            + (
                                f", candidates: {', '.join(alternames[:5])}"
                                if alternames
                                else ""
                            ),
                        )
            elif class_type in {"CheckpointLoaderSimple", "UNETLoader"}:
                key = "ckpt_name" if "ckpt_name" in inputs else "unet_name"
                req_key = "ckpt_name" if "ckpt_name" in required else "unet_name"
                normalized_name = self._restore_backslash_escapes(inputs[key])
                if normalized_name != inputs[key]:
                    node["inputs"][key] = normalized_name
                    inputs[key] = normalized_name
                info["sd_model_name"] = inputs[key]
                if req_key in required:
                    ok, alternames = self._model_search(
                        info["sd_model_name"], required[req_key]
                    )
                    if not ok and alternames:
                        printWarning(
                            f"Model {info['sd_model_name']} not found, but found similar models {alternames} use {alternames[0]}"
                        )
                        node["inputs"][key] = alternames[0]
                        info["sd_model_name"] = alternames[0]
                    elif not ok:
                        self._add_issue(
                            issues,
                            node_id,
                            class_type,
                            f"model '{info['sd_model_name']}' not found"
                            + (
                                f", candidates: {', '.join(alternames[:5])}"
                                if alternames
                                else ""
                            ),
                        )
            elif class_type == "LoraLoader":
                info.setdefault("loras", []).append(inputs["lora_name"])
                info.setdefault("lora", []).append(inputs["lora_name"])
                if "lora_name" in required:
                    lora_name = inputs["lora_name"]
                    ok, alternames = self._model_search(
                        lora_name, required["lora_name"]
                    )
                    if not ok and alternames:
                        printWarning(
                            f"Lora {lora_name} not found, but found similar loras {alternames} use {alternames[0]}"
                        )
                        node["inputs"]["lora_name"] = alternames[0]
                        info["loras"][-1] = alternames[0]
                        info["lora"][-1] = alternames[0]
                    elif not ok:
                        self._add_issue(
                            issues,
                            node_id,
                            class_type,
                            f"lora '{lora_name}' not found",
                        )

        if positive is not None:
            info["prompt"] = self._prompt_search(workflow, object_info, positive)
        if negative is not None:
            info["negative_prompt"] = self._prompt_search(
                workflow, object_info, negative
            )
        if issues:
            for issue in issues:
                printError(self._format_issue(issue))
            printError("Workflow is invalid")
            return None, None
        printDebug("Workflow is valid")
        return workflow, info

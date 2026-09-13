import copy
import json
import os
import random
import re

import yaml

try:
    from modules.logger import getDefaultLogger

    logger = getDefaultLogger()
except Exception:
    logger = None


def printInfo(*args, **kwargs):
    if logger is not None:
        logger.info(*args, **kwargs)
    else:
        print(*args, **kwargs)


def printError(*args, **kwargs):
    if logger is not None:
        logger.error(*args, **kwargs)
    else:
        print(*args, **kwargs)


def printVerbose(*args, **kwargs):
    if logger is not None:
        logger.verbose(*args, **kwargs)
    else:
        print(*args, **kwargs)


def printWarning(*args, **kwargs):
    if logger is not None:
        logger.warning(*args, **kwargs)
    else:
        print(*args, **kwargs)


def printDebug(*args, **kwargs):
    if logger is not None:
        logger.debug(*args, **kwargs)


class WorkflowBuilderCore:
    def __init__(self, start_index=3):
        self.workflow = {}
        self.next_id = start_index

    def add_node(self, class_type, inputs, role=None, node_id=None):
        if node_id is None:
            node_id = str(self.next_id)
            self.next_id += 1
        else:
            node_id = str(node_id)
        node = {"class_type": class_type, "inputs": inputs}
        if role is not None:
            node["_meta"] = {"role": role, "title": role}
        self.workflow[node_id] = node
        return [node_id, 0]

    def add_save_websocket(self, images, node_id="save_image_websocket_node"):
        self.workflow[str(node_id)] = {
            "class_type": "SaveImageWebsocket",
            "inputs": {"images": images},
            "_meta": {"role": "save_image_websocket", "title": "save_image_websocket"},
        }
        return [str(node_id), 0]

    def add_save_image(self, images, filename_prefix):
        return self.add_node(
            "SaveImage",
            {"images": images, "filename_prefix": filename_prefix},
            role="save_image",
        )


def _family_defaults(family):
    defaults = {
        "sd15": {
            "width": 512,
            "height": 512,
            "checkpoint_loader": "CheckpointLoaderSimple",
            "text_encoder": "CLIPTextEncode",
            "latent": "EmptyLatentImage",
            "supports_clip_skip": True,
        },
        "sdxl": {
            "width": 1024,
            "height": 1024,
            "checkpoint_loader": "CheckpointLoaderSimple",
            "text_encoder": "CLIPTextEncodeSDXL",
            "latent": "EmptyLatentImage",
            "supports_clip_skip": True,
        },
        "sd35": {
            "width": 1024,
            "height": 1024,
            "checkpoint_loader": "CheckpointLoaderSimple",
            "text_encoder": "CLIPTextEncodeSD3",
            "latent": "EmptySD3LatentImage",
            "supports_clip_skip": False,
        },
        "flux": {
            "width": 1024,
            "height": 1024,
            "checkpoint_loader": "UNETLoader",
            "text_encoder": "CLIPTextEncode",
            "latent": "EmptyLatentImage",
            "supports_clip_skip": False,
            "clip_loader": "CLIPLoader",
            "model_adapter": "ModelSamplingAuraFlow",
        },
        "anima": {
            "width": 1024,
            "height": 1024,
            "checkpoint_loader": "CheckpointLoaderSimple",
            "text_encoder": "CLIPTextEncode",
            "latent": "EmptyLatentImage",
            "supports_clip_skip": True,
            "template_only": True,
        },
    }
    return copy.deepcopy(defaults.get(family, defaults["sd15"]))


def _normalize_family_mode(options):
    options = copy.deepcopy(options)
    family = options.get("workflow_family")
    if family is None:
        family = options.get("type", "sd15")
    family = str(family).lower()
    aliases = {
        "sd1.5": "sd15",
        "sd15": "sd15",
        "sdxl": "sdxl",
        "sd3": "sd35",
        "sd3.5": "sd35",
        "sd35": "sd35",
        "flux.1": "flux",
        "flux": "flux",
        "anima": "anima",
    }
    family = aliases.get(family, family)
    mode = options.get("workflow_mode")
    if mode is None:
        mode = "img2img" if options.get("image") is not None else "txt2img"
    options["workflow_family"] = family
    options["workflow_mode"] = mode
    options["type"] = family
    return options


def _extract_prompt_loras(prompt):
    if prompt is None:
        prompt = ""
    matcher = re.compile(r"\<lora\:(.+?)\:([0-9\.]+)\>")
    loras = matcher.findall(prompt)
    return matcher.sub("", prompt), loras


def _normalize_explicit_loras(loras):
    normalized = []
    for item in loras or []:
        if isinstance(item, dict):
            normalized.append(
                {
                    "name": item.get("name"),
                    "weight": float(item.get("weight", 1.0)),
                    "target": item.get("target", "both"),
                }
            )
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            normalized.append(
                {"name": item[0], "weight": float(item[1]), "target": "both"}
            )
    return normalized


def _merge_node_definition(spec, role, default_class, default_inputs=None):
    default_inputs = copy.deepcopy(default_inputs or {})
    node_spec = copy.deepcopy(spec.get("nodes", {}).get(role, {}))
    class_type = node_spec.get("class_type", default_class)
    inputs = copy.deepcopy(node_spec.get("inputs", {}))
    for key, value in inputs.items():
        default_inputs[key] = value
    return class_type, default_inputs


def _load_template(template):
    if template is None or isinstance(template, dict):
        return copy.deepcopy(template)
    if not isinstance(template, str):
        raise TypeError("workflow template must be dict or filename")
    with open(template, encoding="utf-8") as f:
        if template.endswith(".yaml") or template.endswith(".yml"):
            return yaml.safe_load(f) or {}
        return json.load(f)


def build_comfyui_spec(prompt_text, options):
    if "comfyui" in prompt_text and isinstance(prompt_text["comfyui"], dict):
        spec = copy.deepcopy(prompt_text["comfyui"])
    elif "workflow" in prompt_text and isinstance(prompt_text["workflow"], dict):
        spec = copy.deepcopy(prompt_text["workflow"])
    else:
        spec = {}

    merged = copy.deepcopy(options)
    for key, value in prompt_text.items():
        if key not in {"comfyui", "workflow", "verbose"}:
            merged[key] = value
    merged = _normalize_family_mode(merged)

    if not spec:
        spec = {}
    spec.setdefault("family", merged.get("workflow_family", "sd15"))
    spec.setdefault("mode", merged.get("workflow_mode", "txt2img"))
    spec.setdefault(
        "model", merged.get("model", merged.get("checkpoint", merged.get("sd_model")))
    )
    vae = merged.get("vae", merged.get("sd_vae"))
    if vae in ("Automatic", "None"):
        vae = None
    spec.setdefault("vae", vae)
    text_encoder = merged.get("text_encoder")
    if text_encoder not in (None, "Automatic", "None"):
        # ComfyUI names the text-encoder file clip_name.  Keep Automatic
        # unset so the workflow's family default remains in effect.
        spec.setdefault("clip_name", text_encoder)
    spec.setdefault("clip_skip", merged.get("stop_at_clip_layer"))
    spec.setdefault("prompt", merged.get("prompt", ""))
    spec.setdefault("negative_prompt", merged.get("negative_prompt", ""))
    spec.setdefault("width", merged.get("width"))
    spec.setdefault("height", merged.get("height"))
    spec.setdefault("image", merged.get("image"))
    spec.setdefault("mask", merged.get("mask"))
    spec.setdefault("controlnet", merged.get("controlnet", []))
    spec.setdefault("loras", merged.get("loras", []))
    spec.setdefault("template", merged.get("workflow_template"))
    sampling = spec.setdefault("sampling", {})
    sampling.setdefault("seed", merged.get("seed", -1))
    sampling.setdefault("steps", merged.get("steps", 20))
    sampling.setdefault("cfg", merged.get("cfg_scale", 7))
    sampling.setdefault("sampler_name", merged.get("sampler_name", "dpmpp_2m_sde"))
    sampling.setdefault("scheduler", merged.get("scheduler", "karras"))
    sampling.setdefault(
        "denoise", merged.get("denoise", merged.get("nomal_denoising_strength", 1))
    )
    sampling.setdefault("batch_size", merged.get("batch_size", 1))
    save = spec.setdefault("save", {})
    save.setdefault("filename_prefix", merged.get("prefix", merged.get("filename", "Comfy")))
    save.setdefault("save_image", merged.get("save_image", ["websocket"]))
    return spec, merged


class ComfyUIWorkflowCompiler:
    def __init__(self, owner=None):
        self.owner = owner

    def _create_text_encode_node(self, family, text, clip_ref, spec=None):
        family_defaults = _family_defaults(family)
        encoder, _ = _merge_node_definition(
            spec or {}, "text_encoder", family_defaults["text_encoder"], {}
        )
        if encoder == "CLIPTextEncodeSDXL":
            return encoder, {
                "clip": clip_ref,
                "text_g": text,
                "text_l": text,
                "width": 4096,
                "height": 4096,
                "crop_w": 0,
                "crop_h": 0,
                "target_width": 4096,
                "target_height": 4096,
            }
        return encoder, {"clip": clip_ref, "text": text}

    def _add_text_conditioning(self, core, family, text, clip_ref, role, spec=None):
        prompts = text.split("BREAK")
        node_class, node_inputs = self._create_text_encode_node(
            family, prompts[0], clip_ref, spec=spec
        )
        current = core.add_node(node_class, node_inputs, role=role)
        for part in prompts[1:]:
            next_class, next_inputs = self._create_text_encode_node(
                family, part, clip_ref, spec=spec
            )
            next_ref = core.add_node(next_class, next_inputs)
            current = core.add_node(
                "ConditioningConcat",
                {"conditioning_from": current, "conditioning_to": next_ref},
                role=f"{role}_concat",
            )
        return current

    def _add_lora_chain(self, core, model_ref, clip_ref, loras):
        current_model = model_ref
        current_clip = clip_ref
        applied = []
        for lora in loras:
            name = lora.get("name")
            if name is None:
                continue
            if not str(name).endswith(".safetensors"):
                name = str(name) + ".safetensors"
            ref = core.add_node(
                "LoraLoader",
                {
                    "lora_name": name,
                    "strength_model": float(lora.get("weight", 1.0)),
                    "strength_clip": float(lora.get("weight", 1.0)),
                    "model": current_model,
                    "clip": current_clip,
                },
                role="lora_loader",
            )
            current_model = [ref[0], 0]
            current_clip = [ref[0], 1]
            applied.append(name)
        return current_model, current_clip, applied

    def _add_input_latent(self, core, family, mode, spec, vae_ref):
        sampling = spec.get("sampling", {})
        if mode == "img2img":
            image_value = spec.get("image")
            if image_value is None:
                raise ValueError("img2img requires image")
            image_class, image_inputs = _merge_node_definition(
                spec,
                "image_loader",
                "LoadImage",
                {"image": image_value, "upload": "image"},
            )
            image_ref = core.add_node(image_class, image_inputs, role="image")
            encode_class, encode_inputs = _merge_node_definition(
                spec,
                "vae_encode",
                "VAEEncode",
                {"pixels": [image_ref[0], 0], "vae": vae_ref},
            )
            latent_ref = core.add_node(encode_class, encode_inputs, role="vae_encode")
            mask_value = spec.get("mask")
            if mask_value is not None:
                mask_class, mask_inputs = _merge_node_definition(
                    spec,
                    "mask_loader",
                    "LoadImageMask",
                    {"image": mask_value, "channel": "alpha", "upload": "image"},
                )
                mask_ref = core.add_node(mask_class, mask_inputs, role="mask")
                latent_mask_class, latent_mask_inputs = _merge_node_definition(
                    spec,
                    "latent_mask",
                    "SetLatentNoiseMask",
                    {"samples": latent_ref, "mask": [mask_ref[0], 0]},
                )
                latent_ref = core.add_node(
                    latent_mask_class, latent_mask_inputs, role="latent_mask"
                )
            return latent_ref

        defaults = _family_defaults(family)
        latent_class, latent_inputs = _merge_node_definition(
            spec,
            "latent",
            defaults["latent"],
            {
                "batch_size": sampling.get("batch_size", 1),
                "height": spec.get("height", defaults["height"]),
                "width": spec.get("width", defaults["width"]),
            },
        )
        return core.add_node(latent_class, latent_inputs, role="latent")

    def _build_base_graph(self, spec):
        family = spec["family"]
        mode = spec["mode"]
        defaults = _family_defaults(family)
        core = WorkflowBuilderCore()
        model_name = spec.get("model")
        if not model_name:
            raise ValueError("model/checkpoint is required")

        if defaults["checkpoint_loader"] == "UNETLoader":
            model_loader_class, model_loader_inputs = _merge_node_definition(
                spec,
                "model_loader",
                "UNETLoader",
                {"unet_name": model_name, "weight_dtype": "default"},
            )
            model_ref = core.add_node(
                model_loader_class, model_loader_inputs, role="model_loader"
            )
            model_handle = [model_ref[0], 0]
            if defaults.get("model_adapter") is not None:
                adapter_class, adapter_inputs = _merge_node_definition(
                    spec,
                    "model_adapter",
                    defaults["model_adapter"],
                    {"model": model_handle},
                )
                adapter_ref = core.add_node(
                    adapter_class, adapter_inputs, role="model_adapter"
                )
                model_handle = [adapter_ref[0], 0]
            clip_loader_class, clip_loader_inputs = _merge_node_definition(
                spec,
                "clip_loader",
                defaults.get("clip_loader", "CLIPLoader"),
                {
                    "clip_name": spec.get("clip_name", "clip_l.safetensors"),
                    "type": spec.get("clip_type", "stable_diffusion"),
                },
            )
            clip_ref = core.add_node(
                clip_loader_class, clip_loader_inputs, role="clip_loader"
            )
            vae_loader_class, vae_loader_inputs = _merge_node_definition(
                spec,
                "vae_loader",
                "VAELoader",
                {"vae_name": spec.get("vae") or "ae.safetensors"},
            )
            vae_ref = core.add_node(
                vae_loader_class, vae_loader_inputs, role="vae_loader"
            )
            clip_handle = [clip_ref[0], 0]
            vae_handle = [vae_ref[0], 0]
        else:
            checkpoint_loader_class, checkpoint_loader_inputs = _merge_node_definition(
                spec,
                "checkpoint_loader",
                defaults["checkpoint_loader"],
                {"ckpt_name": model_name},
            )
            checkpoint_ref = core.add_node(
                checkpoint_loader_class,
                checkpoint_loader_inputs,
                role="checkpoint_loader",
            )
            model_handle = [checkpoint_ref[0], 0]
            clip_handle = [checkpoint_ref[0], 1]
            vae_handle = [checkpoint_ref[0], 2]
            if spec.get("vae"):
                vae_loader_class, vae_loader_inputs = _merge_node_definition(
                    spec, "vae_loader", "VAELoader", {"vae_name": spec["vae"]}
                )
                vae_ref = core.add_node(
                    vae_loader_class, vae_loader_inputs, role="vae_loader"
                )
                vae_handle = [vae_ref[0], 0]

        if defaults.get("supports_clip_skip") and spec.get("clip_skip") is not None:
            clip_skip = spec["clip_skip"]
            if clip_skip > 0:
                clip_skip = -clip_skip
            clip_skip_class, clip_skip_inputs = _merge_node_definition(
                spec,
                "clip_skip",
                "CLIPSetLastLayer",
                {"stop_at_clip_layer": clip_skip, "clip": clip_handle},
            )
            clip_skip_ref = core.add_node(
                clip_skip_class, clip_skip_inputs, role="clip_skip"
            )
            clip_handle = [clip_skip_ref[0], 0]

        latent_handle = self._add_input_latent(core, family, mode, spec, vae_handle)
        return core, model_handle, clip_handle, vae_handle, latent_handle

    def _inject_controlnet(self, workflow, spec):
        controlnets = spec.get("controlnet", []) or []
        template = spec.get("template")
        if not template or not controlnets:
            return workflow
        workflow = copy.deepcopy(workflow)
        slots = workflow.get("_controlnet_slots", {})
        for idx, controlnet in enumerate(controlnets):
            slot = slots.get(str(idx)) or slots.get(controlnet.get("role"))
            if slot is None:
                continue
            node_id = str(slot.get("node_id"))
            field = slot.get("field", "image")
            if node_id in workflow and "inputs" in workflow[node_id]:
                value = controlnet.get("image")
                if value is not None:
                    workflow[node_id]["inputs"][field] = value
                if "strength" in controlnet and slot.get("strength_field"):
                    workflow[node_id]["inputs"][slot["strength_field"]] = controlnet["strength"]
        return workflow

    def compile(self, spec):
        spec = copy.deepcopy(spec)
        spec["family"] = str(spec.get("family", "sd15")).lower()
        spec["mode"] = str(spec.get("mode", "txt2img")).lower()
        spec.setdefault("controlnet", [])
        spec.setdefault("loras", [])
        spec.setdefault("nodes", {})

        prompt, positive_inline = _extract_prompt_loras(spec.get("prompt", ""))
        negative_prompt, negative_inline = _extract_prompt_loras(
            spec.get("negative_prompt", "")
        )
        explicit_loras = _normalize_explicit_loras(spec.get("loras", []))
        positive_loras = [
            {"name": name, "weight": float(weight), "target": "positive"}
            for name, weight in positive_inline
        ]
        negative_loras = [
            {"name": name, "weight": float(weight), "target": "negative"}
            for name, weight in negative_inline
        ]
        all_loras = explicit_loras + positive_loras + negative_loras
        info = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "loras": [item["name"] for item in all_loras if item.get("name")],
        }

        template = _load_template(spec.get("template"))
        if template is not None:
            spec["template"] = template
            workflow = self._inject_controlnet(copy.deepcopy(template), spec)
            return workflow, info

        core, model_ref, clip_ref, vae_ref, latent_ref = self._build_base_graph(spec)
        positive_chain = [
            item
            for item in all_loras
            if item.get("target", "both") in {"both", "positive"}
        ]
        negative_chain = [
            item
            for item in all_loras
            if item.get("target", "both") in {"both", "negative"}
        ]
        pos_model, pos_clip, _ = self._add_lora_chain(
            core, model_ref, clip_ref, positive_chain
        )
        neg_model, neg_clip, _ = self._add_lora_chain(
            core, model_ref, clip_ref, negative_chain
        )

        positive_ref = self._add_text_conditioning(
            core, spec["family"], prompt, pos_clip, "positive", spec=spec
        )
        negative_ref = self._add_text_conditioning(
            core, spec["family"], negative_prompt, neg_clip, "negative", spec=spec
        )

        sampling = spec.get("sampling", {})
        seed = sampling.get("seed", -1)
        if seed == -1:
            seed = random.randint(0, 2**31 - 1)
        info["seed"] = seed
        info["sd_model_name"] = spec.get("model")
        info["sd_vae_name"] = spec.get("vae")
        info["clip_skip"] = abs(spec.get("clip_skip", 0)) if spec.get("clip_skip") else None
        info["width"] = spec.get("width", _family_defaults(spec["family"])["width"])
        info["height"] = spec.get("height", _family_defaults(spec["family"])["height"])
        info["batch_size"] = sampling.get("batch_size", 1)
        info["cfg_scale"] = sampling.get("cfg", 7)
        info["steps"] = sampling.get("steps", 20)
        info["sampler_name"] = sampling.get("sampler_name", "dpmpp_2m_sde")
        info["scheduler"] = sampling.get("scheduler", "karras")
        info["denoising_strength"] = sampling.get("denoise", 1)

        sampler_class, sampler_inputs = _merge_node_definition(
            spec,
            "sampler",
            "KSampler",
            {
                "cfg": info["cfg_scale"],
                "denoise": info["denoising_strength"],
                "latent_image": latent_ref,
                "model": pos_model if spec["mode"] == "txt2img" else pos_model,
                "positive": positive_ref,
                "negative": negative_ref,
                "sampler_name": info["sampler_name"],
                "scheduler": info["scheduler"],
                "seed": info["seed"],
                "steps": info["steps"],
            },
        )
        sampler_ref = core.add_node(sampler_class, sampler_inputs, role="sampler")
        decode_class, decode_inputs = _merge_node_definition(
            spec,
            "vae_decode",
            "VAEDecode",
            {"samples": sampler_ref, "vae": vae_ref},
        )
        image_ref = core.add_node(decode_class, decode_inputs, role="vae_decode")
        save = spec.get("save", {})
        save_image = save.get("save_image", ["websocket"])
        if "ui" in save_image:
            core.add_save_image(image_ref, save.get("filename_prefix", "Comfy"))
        if "websocket" in save_image or "save" in save_image:
            core.add_save_websocket(image_ref)
        workflow = self._inject_controlnet(core.workflow, spec)
        return workflow, info


class ComfyUIWorkflow:
    def __init__(self, options=None):
        self.options = options or {}
        self.checkpoint = None
        self.vae = None
        self.compiler = ComfyUIWorkflowCompiler(self)

    def setModel(self, model):
        self.checkpoint = model

    def setVAE(self, vae):
        self.vae = vae

    def createWorkflowSDXL(self, prompt, negative_prompt, options=None):
        options = copy.deepcopy(options or {})
        options["type"] = "sdxl"
        return self.createWorkflow(prompt, negative_prompt, options)

    def createWorkflowSD15(self, prompt, negative_prompt, options=None):
        options = copy.deepcopy(options or {})
        options["type"] = "sd15"
        return self.createWorkflow(prompt, negative_prompt, options)

    def createWorkflow(self, prompt, negative_prompt, options=None):
        normalized = _normalize_family_mode(options or {})
        vae = normalized.get("vae", self.vae)
        if vae in ("Automatic", "None"):
            vae = None
        spec = {
            "family": normalized.get("workflow_family", "sd15"),
            "mode": normalized.get("workflow_mode", "txt2img"),
            "model": normalized.get("model", normalized.get("checkpoint", self.checkpoint)),
            "vae": vae,
            "clip_skip": normalized.get("stop_at_clip_layer"),
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": normalized.get("width"),
            "height": normalized.get("height"),
            "image": normalized.get("image"),
            "mask": normalized.get("mask"),
            "controlnet": normalized.get("controlnet", []),
            "loras": normalized.get("loras", []),
            "template": normalized.get("workflow_template"),
            "nodes": normalized.get("nodes", {}),
            "save": {
                "filename_prefix": normalized.get(
                    "prefix", normalized.get("filename", "Comfy")
                ),
                "save_image": normalized.get("save_image", ["websocket"]),
            },
            "sampling": {
                "seed": normalized.get("seed", -1),
                "steps": normalized.get("steps", 20),
                "cfg": normalized.get("cfg_scale", 7),
                "sampler_name": normalized.get("sampler_name", "dpmpp_2m_sde"),
                "scheduler": normalized.get("scheduler", "karras"),
                "denoise": normalized.get(
                    "denoise", normalized.get("nomal_denoising_strength", 1)
                ),
                "batch_size": normalized.get("batch_size", 1),
            },
        }
        text_encoder = normalized.get("text_encoder")
        if text_encoder not in (None, "Automatic", "None"):
            spec["clip_name"] = text_encoder
        return self.createWorkflowFromSpec(spec, normalized)

    def createWorkflowFromSpec(self, spec, options=None):
        spec = copy.deepcopy(spec)
        options = options or {}
        spec.setdefault(
            "model", options.get("model", options.get("checkpoint", options.get("sd_model", self.checkpoint)))
        )
        vae = options.get("vae", options.get("sd_vae", self.vae))
        if vae in ("Automatic", "None"):
            vae = None
        spec.setdefault("vae", vae)
        text_encoder = options.get("text_encoder")
        if "clip_name" not in spec and text_encoder not in (None, "Automatic", "None"):
            spec["clip_name"] = text_encoder
        return self.compiler.compile(spec)

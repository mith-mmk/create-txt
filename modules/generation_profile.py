"""Resolve one generation context and apply conditional YAML profiles."""

import copy
import re

from modules.logger import getDefaultLogger

Logger = getDefaultLogger()

# Parent order is also the order in which configuration is applied.
MODEL_PARENTS = {
    "sd15": None, "sdxl": None, "illustrius": "sdxl", "noobai": "illustrius",
    "pony": "sdxl",
    "mugen": "sdxl", "flux": None, "flux-dev": "flux", "flux-schnell": "flux",
    "flux-krea": "flux", "flux-kontext": "flux", "flux2-klein": None,
    "flux2-klein-4b": "flux2-klein", "flux2-klein-9b": "flux2-klein",
    "chroma": None, "chroma-hd": "chroma", "lumina": None,
    "neta-lumina": "lumina", "netayume-lumina": "lumina",
    "qwen-image": None, "qwen-image-edit": "qwen-image",
    "z-image": None, "z-image-turbo": "z-image",
    "anima": None, "anima_2b": "anima", "anima_2.9b": "anima",
    "anima_3.8b": "anima", "anima-edit": "anima",
    "anima_2b-edit": "anima_2b", "anima_2.9b-edit": "anima_2.9b",
    "anima_3.8b-edit": "anima_3.8b",
    "ernie-image": None, "ernie-image-turbo": "ernie-image",
    "krea2": None, "krea2-turbo": "krea2", "krea2-raw": "krea2",
    "krea2-edit": "krea2", "krea2-turbo-edit": "krea2-turbo", "krea2-raw-edit": "krea2-raw",
    # Existing ComfyUI/WebUI families; deliberately rejected only on Neo.
    "sd2": None, "sd35": None,
}
MODEL_ALIASES = {
    "illustrious": "illustrius", "sd1": "sd15", "sd1.5": "sd15",
    "sd3": "sd35", "sd3.5": "sd35", "flux.1": "flux", "flux1": "flux",
    "flux.1-kontext": "flux-kontext", "flux.2-klein": "flux2-klein",
    "chroma1-hd": "chroma-hd", "lumina-image-2.0": "lumina",
    "krea-2": "krea2", "anima_2.0b": "anima_2b",
}
UI_TYPES = ("webui", "forge", "neo", "comfy")


def normalize_model_type(value):
    if value is None or value == "auto":
        return None
    key = str(value).strip().lower()
    key = MODEL_ALIASES.get(key, key)
    if key not in MODEL_PARENTS:
        raise ValueError(f"Unsupported model_type: {value}")
    return key


def model_chain(model_type):
    result = []
    while model_type:
        result.insert(0, model_type)
        model_type = MODEL_PARENTS[model_type]
    # Version-specific Edit profiles inherit the common Edit profile as well.
    if result and result[-1].endswith("-edit"):
        if result[-1].startswith("anima_"):
            result.insert(-1, "anima-edit")
        elif result[-1] in ("krea2-turbo-edit", "krea2-raw-edit"):
            result.insert(-1, "krea2-edit")
    return result


def infer_model_type(name):
    """Conservative filename/path matching; never infer SDXL from 'XL' alone."""
    if not isinstance(name, str) or "${" in name:
        return None
    name = name.lower().replace("\\", "/")
    compact = re.sub(r"[\s_.-]", "", name)
    if "noobai" in compact:
        return "noobai"
    if "pony" in compact:
        return "pony"
    if "illustri" in compact:
        return "illustrius"
    if "anima" in name and "animagine" not in name:
        version = next((v for v in ("2.9b", "3.8b", "2b")
                        if v.replace(".", "") in compact), None)
        family = f"anima_{version}" if version else "anima"
        return family + "-edit" if "edit" in name else family
    if "qwen" in name and ("image" in name or "edit" in name):
        return "qwen-image-edit" if "edit" in name else "qwen-image"
    if "klein" in name:
        size = next((v for v in ("4b", "9b") if v in compact), None)
        return "flux2-klein" + (f"-{size}" if size else "")
    if "kontext" in name:
        return "flux-kontext"
    if "krea2" in compact:
        variant = next((v for v in ("turbo", "raw") if v in name), None)
        return "krea2" + (f"-{variant}" if variant else "") + ("-edit" if "edit" in name else "")
    if "ernieimage" in compact:
        return "ernie-image-turbo" if "turbo" in name else "ernie-image"
    if "zimage" in compact:
        return "z-image-turbo" if "turbo" in name else "z-image"
    if "chroma" in name:
        return "chroma-hd" if "hd" in name else "chroma"
    if "lumina" in name:
        return "netayume-lumina" if "netayume" in name else (
            "neta-lumina" if "neta" in name else "lumina")
    if "mugen" in name:
        return "mugen"
    if "flux" in name and not re.search(r"flux[._ -]?2", name):
        variant = next((v for v in ("schnell", "krea", "dev") if v in name), None)
        return "flux" + (f"-{variant}" if variant else "")
    if "sdxl" in compact or "stablediffusionxl" in compact or "animaginexl" in compact:
        return "sdxl"
    if "sd35" in compact or "sd3" in compact:
        return "sd35"
    if ("sd15" in compact or "stablediffusionv1" in compact or
            re.search(r"(?:^|/)v1[-_.]5(?:[-_.]|$)", name) or compact in ("sd1", "sdv1")):
        return "sd15"
    return None


def merge(target, patch):
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge(target[key], value)
        else:
            target[key] = copy.deepcopy(value)
    return target


def apply_profile(yml, profile, label):
    if profile is None:
        return
    if not isinstance(profile, dict):
        raise ValueError(f"{label} must be a mapping or null")
    loads = profile.get("load_profile", []) or []
    if isinstance(loads, str):
        loads = [loads]
    for name in loads:
        if name not in yml.get("profiles", {}):
            raise ValueError(f"{label}: load_profile {name} not found")
        pre = yml["profiles"][name] or {}
        if not isinstance(pre, dict):
            raise ValueError(f"profiles.{name} must be a mapping")
        # Same one-level load_profile behavior as regular profiles.
        merge(yml, {k: v for k, v in pre.items() if k not in ("load_profile", "profile")})
    merge(yml, {k: v for k, v in profile.items() if k not in ("load_profile", "profile")})


def resolve_context(yml, opt):
    from modules.webui import inspect_server, lookup_model, read_metadata

    options = yml.get("options", {})
    comfy = bool(opt.get("comfy") or opt.get("api_comfy"))
    active = bool(opt.get("api_mode") or comfy)
    ui = opt.get("ui_type") or options.get("ui_type")
    if ui == "auto":
        ui = None
    if ui and ui not in UI_TYPES:
        raise ValueError(f"Unsupported ui_type: {ui}")
    if comfy and ui and ui != "comfy":
        raise ValueError("ComfyUI flags conflict with ui_type")
    model_type = normalize_model_type(opt.get("model_type") or options.get("model_type"))
    command = yml.get("command", {})
    checkpoint = (opt.get("api_set_sd_model") or options.get("model") or
                  options.get("sd_model") or
                  (command.get("override_settings", {}).get("sd_model_checkpoint")
                   if isinstance(command, dict) else None))
    server = {}
    if active and not comfy and ui != "comfy":
        server = inspect_server(opt.get("api_base", "http://localhost:7860"),
                                opt.get("api_userpass") or options.get("userpass"))
    ui = ui or ("comfy" if comfy else server.get("ui_type"))
    if ui == "comfy" and opt.get("api_mode") and not comfy:
        raise ValueError("ui_type=comfy requires --comfy (not --api-mode)")
    checkpoint = checkpoint or server.get("options", {}).get("sd_model_checkpoint")
    evidence = "explicit" if model_type else "unknown"
    if model_type is None:
        entry = lookup_model(server.get("models", []), checkpoint, required=False)
        metadata = entry.get("metadata", {}) if entry else {}
        if entry and active:
            metadata = metadata or read_metadata(opt.get("api_base", "http://localhost:7860"),
                                                 entry, opt.get("api_userpass") or options.get("userpass"))
        if isinstance(metadata, dict):
            for key in ("modelspec.architecture", "modelspec.implementation", "ss_base_model_version"):
                model_type = infer_model_type(metadata.get(key))
                if model_type:
                    evidence = f"metadata.{key}"
                    break
        named = infer_model_type(checkpoint)
        if named and (model_type is None or model_type in model_chain(named)):
            model_type, evidence = named, "checkpoint name/path"
        if model_type is None and comfy and opt.get("comfy_family"):
            model_type = normalize_model_type(opt["comfy_family"])
            evidence = "comfy_family"
    if ui == "neo" and model_type in ("sd2", "sd35"):
        raise ValueError(f"Forge Neo does not support {model_type}")
    return {"ui_type": ui, "model_type": model_type, "checkpoint": checkpoint,
            "evidence": evidence, "server": server}


def apply_generation_profiles(yml, opt):
    """Called after the regular profile, before variables/methods are evaluated."""
    options = yml.get("options", {})
    requested = any(k in yml for k in ("model_profile", "ui_profile")) or any(
        opt.get(k) is not None or options.get(k) is not None
        for k in ("ui_type", "model_type", "image", "mask", "reference_images"))
    # API execution needs backend detection even for an old YAML (e.g. Neo modules).
    if not requested and not (opt.get("api_mode") or opt.get("comfy") or opt.get("api_comfy")):
        return None
    models = yml.get("model_profile") or {}
    uis = yml.get("ui_profile") or {}
    if not isinstance(models, dict) or not isinstance(uis, dict):
        raise ValueError("model_profile and ui_profile must be mappings")
    normalized = {}
    for name, value in models.items():
        key = normalize_model_type(name)
        if key is None or key in normalized:
            raise ValueError(f"Duplicate or invalid model_profile alias: {name}")
        normalized[key] = copy.deepcopy(value)
    for name in uis:
        if name not in UI_TYPES:
            raise ValueError(f"Unsupported ui_profile: {name}")
    context = resolve_context(yml, opt)
    applied = []
    for name in model_chain(context["model_type"]):
        if name in normalized:
            apply_profile(yml, normalized[name], f"model_profile.{name}")
            applied.append(f"model_profile.{name}")
    ui = context["ui_type"]
    if ui in uis:
        apply_profile(yml, uis[ui], f"ui_profile.{ui}")
        applied.append(f"ui_profile.{ui}")
    if models and context["model_type"] is None:
        Logger.warning("model_type unknown; skipping model_profile. Set --model-type to override.")
    elif context["evidence"] != "explicit" and any(
            name != context["model_type"] and context["model_type"] in model_chain(name)
            for name in normalized):
        Logger.warning(f"Model subtype is not identified; applying {context['model_type']} ancestors only. "
                       "Set --model-type to select a specific variant.")
    if uis and ui is None:
        Logger.warning("ui_type unknown; skipping ui_profile. Set --ui-type to override.")
    context["applied_profiles"] = applied
    Logger.info(f"Generation context: ui={ui}, model={context['model_type']} "
                f"({context['evidence']}), profiles={applied}")
    yml["_generation_context"] = context
    return context

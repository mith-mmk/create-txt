"""WebUI/Forge/Neo capability discovery and request preparation."""

import base64
import copy
import io
import json
import re
from pathlib import Path

import httpx
from PIL import Image

from modules import api
from modules.logger import getDefaultLogger

Logger = getDefaultLogger()


def get_json(base_url, path, userpass=None, required=True, params=None):
    try:
        auth = tuple(userpass.split(":", 1)) if userpass else None
        response = api.get_client().get(base_url.rstrip("/") + path, params=params,
                                        auth=auth, timeout=httpx.Timeout(10, connect=3))
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        if required:
            raise ValueError(f"Cannot read {path}: {type(exc).__name__}") from exc
        return None


def inspect_server(base_url, userpass=None):
    options = get_json(base_url, "/sdapi/v1/options", userpass, required=False)
    if not isinstance(options, dict):
        Logger.warning("WebUI API unavailable; backend remains unknown")
        return {}
    if "forge_additional_modules" in options:
        neo = any(k in options for k in ("forge_checkpoint_anima", "forge_checkpoint_klein", "anima_do_reference"))
        ui = "neo" if neo else "forge"
    else:
        ui = "webui"
    return {"ui_type": ui, "options": options,
            "models": get_json(base_url, "/sdapi/v1/sd-models", userpass, required=False) or []}


def lookup_model(models, selected, required=True):
    if selected is None:
        return None
    wanted = str(selected).replace("\\", "/").casefold()
    matches = []
    for model in models:
        values = [str(model[k]).replace("\\", "/").casefold()
                  for k in ("title", "model_name", "filename", "hash", "sha256") if model.get(k)]
        values += [re.sub(r"\s+\[[0-9a-f]+\]$", "", value) for value in values]
        if wanted in values:
            return model
        basenames = [value.rsplit("/", 1)[-1] for value in values]
        stems = [value.removesuffix(".safetensors").removesuffix(".ckpt") for value in basenames]
        if wanted in basenames or wanted in stems:
            matches.append(model)
    if len(matches) == 1:
        return matches[0]
    if required:
        raise ValueError(f"Checkpoint {'ambiguous' if matches else 'not found'}: {selected}")
    return None


def read_metadata(base_url, model, userpass=None):
    name = str(model.get("filename") or model.get("title", "")).replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"\s+\[[0-9a-fA-F]+\]$", "", name)
    name = name.rsplit(".", 1)[0]
    data = get_json(base_url, "/sd_extra_networks/metadata", userpass, required=False,
                    params={"page": "checkpoints", "item": name})
    value = data.get("metadata") if isinstance(data, dict) else None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = None
    return value if isinstance(value, dict) else {}


def resolve_modules(available, selected):
    if isinstance(selected, str):
        selected = [part.strip() for part in selected.split(",") if part.strip()]
    if not isinstance(selected, list):
        raise ValueError("Additional modules must be a list or comma-separated string")
    result = []
    for name in selected:
        wanted = str(name).replace("\\", "/").casefold()
        exact = [m for m in available if wanted in (
            str(m.get("filename", "")).replace("\\", "/").casefold(),
            str(m.get("model_name", "")).casefold())]
        matches = exact or [m for m in available if str(m.get("model_name", "")).casefold().startswith(wanted)]
        if len(matches) != 1:
            raise ValueError(f"Additional module {'ambiguous' if matches else 'not found'}: {name}")
        # Neo accepts full paths; these also disambiguate equal basenames.
        result.append(matches[0].get("filename") or matches[0]["model_name"])
    return result


def _automatic_module(value):
    return value is None or (
        isinstance(value, str) and value.casefold() in {"automatic", "none"}
    )


def _module_list(value):
    if _automatic_module(value):
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple)):
        return list(value)
    raise ValueError("Module selection must be a list or comma-separated string")


def _selected_modules(vae, text_encoder):
    """Return modules requested by the VAE and text encoder options."""
    values = _module_list(vae) + _module_list(text_encoder)
    explicitly_empty = vae == [] or text_encoder == []
    return values, explicitly_empty


def configure_model(
    sd_model, base_url, sd_vae="Automatic", userpass=None, text_encoder="Automatic"
):
    settings = get_json(base_url, "/sdapi/v1/options", userpass)
    models = get_json(base_url, "/sdapi/v1/sd-models", userpass)
    model = lookup_model(models, sd_model)
    payload = {"sd_model_checkpoint": model["title"]}
    if "forge_additional_modules" in settings:
        # Automatic/omitted means retain current modules, [] explicitly clears them.
        modules, explicitly_empty = _selected_modules(sd_vae, text_encoder)
        if modules or explicitly_empty:
            available = get_json(base_url, "/sdapi/v1/sd-modules", userpass)
            payload["forge_additional_modules"] = resolve_modules(available, modules)
    elif not _automatic_module(text_encoder):
        raise ValueError("text_encoder requires Forge or Forge Neo")
    elif sd_vae is not None:
        payload["sd_vae"] = sd_vae
    if all(settings.get(k) == v for k, v in payload.items()):
        return True
    response = api.request_post_wrapper(base_url.rstrip("/") + "/sdapi/v1/options",
                                        json.dumps(payload), None, base_url, userpass)
    if response is None or response.status_code != 200:
        raise ValueError("Failed to change checkpoint/modules")
    return True


def encode_image(value):
    """Accept an existing API encoding, or encode a local image without modifying it."""
    if not isinstance(value, str):
        raise ValueError("Image input must be a path or Base64 string")
    if value.startswith("data:image/"):
        return value
    if len(value) >= 16 and re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", value):
        try:
            with Image.open(io.BytesIO(base64.b64decode(value, validate=True))) as img:
                img.verify()
            return value
        except Exception:
            pass
    path = Path(value)
    try:
        exists = path.is_file()
    except OSError:
        exists = False
    if not exists:
        raise ValueError(f"Image input not found: {value[:180]}")
    with Image.open(path) as img:
        img.load()
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def prepare_payloads(payloads, opt, mode, context=None):
    """Preflight every payload before changing checkpoints or sending a generation."""
    from modules.generation_profile import model_chain

    context = context or {}
    ui = context.get("ui_type") or opt.get("ui_type")
    model_type = context.get("model_type") or opt.get("model_type")
    base_url = opt.get("base_url", "http://localhost:7860")
    userpass = opt.get("userpass")
    server = context.get("server") or {}
    settings = server.get("options")
    if ui == "neo" and settings is None:
        settings = get_json(base_url, "/sdapi/v1/options", userpass)
    settings = settings or {}
    refs = opt.get("reference_images") or []
    if not isinstance(refs, list):
        raise ValueError("reference_images must be a list")
    references = [encode_image(ref) for ref in refs]
    max_size = opt.get("reference_max_size", 1024)
    if not isinstance(max_size, int) or max_size < 0 or max_size > 2048 or max_size % 256:
        raise ValueError("reference_max_size must be 0..2048 in steps of 256")
    if references:
        if ui != "neo":
            raise ValueError("reference_images requires Forge Neo")
        supported = {"flux-kontext", "flux2-klein", "qwen-image-edit", "anima", "krea2"}
        if not supported.intersection(model_chain(model_type)):
            raise ValueError("Reference images require a supported Edit model; set --model-type")
        scripts = get_json(base_url, "/sdapi/v1/script-info", userpass)
        if not any(s.get("name", "").lower() == "imagestitch integrated" and
                   s.get("is_img2img") == (mode == "img2img") and s.get("is_alwayson")
                   for s in scripts):
            raise ValueError("Forge Neo server lacks ImageStitch Integrated for this mode")
    available_modules = None
    available_models = server.get("models")
    result = []
    for original in payloads:
        item = copy.deepcopy(original)
        if opt.get("image") is not None:
            item["init_images"] = [encode_image(opt["image"])]
        elif item.get("init_images") is not None:
            if not isinstance(item["init_images"], list):
                raise ValueError("command.init_images must be a list")
            item["init_images"] = [encode_image(v) for v in item["init_images"]]
        if opt.get("mask") is not None:
            item["mask"] = encode_image(opt["mask"])
        elif item.get("mask"):
            item["mask"] = encode_image(item["mask"])
        if mode == "img2img" and not item.get("init_images"):
            raise ValueError("img2img requires options.image, --image or command.init_images")
        if mode == "txt2img" and (item.get("init_images") or item.get("mask")):
            raise ValueError("Initial image/mask requires --api-type img2img; use reference_images for txt2img Edit")
        overrides = item.setdefault("override_settings", {})
        selected_model = overrides.get("sd_model_checkpoint")
        if selected_model:
            if not available_models:
                available_models = get_json(base_url, "/sdapi/v1/sd-models", userpass)
            overrides["sd_model_checkpoint"] = lookup_model(available_models, selected_model)["title"]
        # ``vae`` is the canonical YAML key; keep ``sd_vae`` as a legacy alias.
        vae = opt["vae"] if "vae" in opt else opt.get("sd_vae")
        text_encoder = opt.get("text_encoder", "Automatic")
        if ui not in ("neo", "forge") and not _automatic_module(text_encoder):
            raise ValueError("text_encoder requires Forge or Forge Neo")
        module_key = "forge_additional_modules" if ui in ("neo", "forge") else "sd_vae"
        vae_explicit = bool(opt.get("vae_explicit", opt.get("modules_explicit")))
        encoder_explicit = bool(opt.get("text_encoder_explicit"))
        selected_modules, explicitly_empty = _selected_modules(vae, text_encoder)
        if vae_explicit:
            overrides.pop("sd_vae", None)
            overrides.pop("forge_additional_modules", None)
            if ui not in ("neo", "forge"):
                if not _automatic_module(vae):
                    overrides[module_key] = vae
            elif selected_modules or explicitly_empty:
                overrides[module_key] = selected_modules
        elif encoder_explicit and not _automatic_module(text_encoder):
            # An explicit encoder augments a YAML VAE selection and preserves
            # command-level modules when possible.
            current = overrides.get("forge_additional_modules", overrides.get("sd_vae", []))
            overrides[module_key] = _module_list(current) + _module_list(text_encoder)
        elif selected_modules or explicitly_empty:
            if "sd_vae" not in overrides and "forge_additional_modules" not in overrides:
                overrides[module_key] = selected_modules
        if ui in ("neo", "forge"):
            modules = overrides.pop("sd_vae", None)
            modules = overrides.get("forge_additional_modules", modules)
            if modules is not None and modules not in ("Automatic", "None"):
                if available_modules is None:
                    available_modules = get_json(base_url, "/sdapi/v1/sd-modules", userpass)
                overrides["forge_additional_modules"] = resolve_modules(available_modules, modules)
        if ui == "neo":
            chain = model_chain(model_type)
            edit = bool(references or (model_type and model_type.endswith("-edit")))
            for family, key in (("anima", "anima_do_reference"), ("flux2-klein", "klein_do_reference"),
                                ("krea2", "krea2_do_reference")):
                if family not in chain:
                    continue
                if key not in settings:
                    if edit:
                        raise ValueError(f"Forge Neo server lacks {key}; update server for this Edit model")
                    continue
                if mode == "img2img" or edit:
                    overrides.setdefault(key, edit)
                if references and overrides.get(key) is False:
                    raise ValueError(f"reference_images conflicts with {key}=false")
            if edit or model_type in ("flux-kontext", "qwen-image-edit"):
                if mode == "img2img":
                    item.setdefault("denoising_strength", 1.0)
        if references:
            scripts = item.setdefault("alwayson_scripts", {})
            if any(k.lower() == "imagestitch integrated" for k in scripts):
                raise ValueError("Specify reference_images or ImageStitch script_args, not both")
            scripts["ImageStitch Integrated"] = {"args": [True, references, max_size]}
        if not overrides:
            item.pop("override_settings", None)
        result.append(item)
    return result

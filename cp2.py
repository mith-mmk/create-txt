#!/usr/bin/env python3

import argparse
import copy
import json
import os
import sys
from functools import lru_cache

import modules.api as api
from modules.img2img import img2img
from modules.interrogate import interrogate
from modules.logger import getDefaultLogger
from modules.prompt_v2 import create_text_v2, expand_arg
from modules.save import DataSaver
from modules.txt2img import txt2img
from modules.util import divide_values

Logger = getDefaultLogger()


def parse_comfy_lora_arg(value):
    target = "both"
    if "@" in value:
        value, target = value.rsplit("@", 1)
        target = target.strip() or "both"
    if ":" not in value:
        return {"name": value.strip(), "weight": 1.0, "target": target}
    name, weight = value.rsplit(":", 1)
    return {"name": name.strip(), "weight": float(weight), "target": target}


def parse_comfy_controlnet_arg(value):
    if value.strip().startswith("{"):
        return json.loads(value)
    result = {}
    for item in value.split(","):
        if "=" not in item:
            continue
        key, val = item.split("=", 1)
        key = key.strip()
        val = val.strip()
        if key in {"strength", "start_percent", "end_percent"}:
            try:
                result[key] = float(val)
                continue
            except ValueError:
                pass
        result[key] = val
    return result


def parse_comfy_node_arg(value):
    if "=" not in value or "." not in value:
        raise ValueError(
            "comfy-node must be role.field=value or role.inputs.key=value format"
        )
    path, raw_value = value.split("=", 1)
    parts = path.split(".")
    role = parts[0]
    payload = {}
    current = payload
    for part in parts[1:-1]:
        current[part] = {}
        current = current[part]
    try:
        parsed_value = json.loads(raw_value)
    except Exception:
        parsed_value = raw_value
    current[parts[-1]] = parsed_value
    return role, payload


def merge_nested_dict(target, patch):
    for key, value in patch.items():
        if (
            key in target
            and isinstance(target[key], dict)
            and isinstance(value, dict)
        ):
            merge_nested_dict(target[key], value)
        else:
            target[key] = value
    return target


class PromptArgumentParser(argparse.ArgumentParser):
    def parse_known_args(self, args=None, namespace=None):
        tokens = list(sys.argv[1:] if args is None else args)
        result, rest = super().parse_known_args(tokens, namespace)
        result._explicit_args = {
            self._option_string_actions[token.split("=", 1)[0]].dest
            for token in tokens if token.split("=", 1)[0] in self._option_string_actions
        }
        for token in tokens:
            if token.startswith("-") and not token.startswith("--") and len(token) > 2:
                action = self._option_string_actions.get(token[:2])
                if action is not None:
                    result._explicit_args.add(action.dest)
        return result, rest


def build_parser():
    parser = PromptArgumentParser(argument_default=None)
    parser.add_argument("input", type=str, nargs="?", default=None)
    parser.add_argument("--append-dir", type=str, default="./appends")
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--json", type=bool, nargs="?", const=True, default=False)
    parser.add_argument(
        "--escape-filename", type=bool, nargs="?", const=True, default=False
    )
    parser.add_argument(
        "--api-mode", "-x", type=bool, nargs="?", const=True, default=False
    )
    parser.add_argument(
        "--api-base", "--hostname", "-H", type=str, default="http://localhost:7860"
    )
    parser.add_argument("--api-userpass", type=str, default=None)
    parser.add_argument("--api-output-dir", "-o", type=str, default="outputs")
    parser.add_argument("--api-input-json", "-i", type=str, default=None)
    parser.add_argument("--api-filename-pattern", "-P", type=str, default=None)
    parser.add_argument("--api-filname-pattern", type=str, default=None)
    parser.add_argument("--max-number", "-N", type=int, default=-1)
    parser.add_argument("--num-length", type=int, default=None)
    parser.add_argument(
        "--api-filename-variable",
        type=bool,
        nargs="?",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--json-verbose", "-j", type=bool, nargs="?", const=True, default=False
    )
    parser.add_argument("--num-once", type=bool, nargs="?", const=True, default=False)
    parser.add_argument("--api-set-sd-model", "-C", type=str, default=None)
    parser.add_argument("--api-set-sd-vae", "-V", type=str, default="Automatic")
    parser.add_argument("--override", type=str, nargs="*", default=None)
    parser.add_argument("--info", type=str, nargs="*", default=None)
    parser.add_argument(
        "--save-extend-meta", type=bool, nargs="?", const=True, default=False
    )
    parser.add_argument(
        "--image-type",
        type=str,
        default="png",
        choices=["jpg", "png", "webp"],
    )
    parser.add_argument("--image-quality", type=int, default=80)
    parser.add_argument(
        "--api-type",
        "-t",
        type=str,
        default="txt2img",
        choices=["txt2img", "img2img", "interrogate"],
    )
    parser.add_argument(
        "--interrogate",
        type=str,
        choices=["clip", "deepdanbooru"],
        default=None,
    )
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--alt-image-dir", type=str, default=None)
    parser.add_argument("--mask-dirs", type=str, default=None)
    parser.add_argument("--mask-blur", type=int, default=None)
    parser.add_argument("--cn-images-dir", type=str, default=None)
    parser.add_argument(
        "--cn-save-pre", type=bool, nargs="?", const=True, default=False
    )
    parser.add_argument("--profile", "-p", type=str, default=None)
    parser.add_argument("--model-type", default=None)
    parser.add_argument("--ui-type", choices=["webui", "forge", "neo", "comfy"], default=None)
    parser.add_argument("--image", default=None)
    parser.add_argument("--mask", default=None)
    parser.add_argument("--reference-image", action="append", dest="reference_images", default=None)
    parser.add_argument("--values", "-v", type=str, default=None)
    parser.add_argument(
        "--api-comfy-save",
        "--comfy-save",
        "-S",
        type=str,
        default="save",
        choices=["save", "both", "ui"],
    )
    parser.add_argument("--debug", type=bool, nargs="?", const=True, default=False)
    parser.add_argument("--verbose", type=bool, nargs="?", const=True, default=False)
    parser.add_argument("--v1json", type=bool, nargs="?", const=True, default=False)
    parser.add_argument("--prompt", type=bool, nargs="?", const=True, default=False)
    parser.add_argument(
        "--json-escape", type=bool, nargs="?", const=True, default=False
    )
    parser.add_argument(
        "--api-comfy", "-X", type=bool, nargs="?", const=True, default=False
    )

    parser.add_argument("--comfy", type=bool, nargs="?", const=True, default=False)
    parser.add_argument(
        "--comfy-mode",
        type=str,
        default=None,
        choices=["txt2img", "img2img", "interrogate"],
    )
    parser.add_argument(
        "--comfy-family",
        type=str,
        default=None,
        choices=["sd15", "sdxl", "sd35", "flux", "anima"],
    )
    parser.add_argument("--comfy-template", type=str, default=None)
    parser.add_argument("--comfy-image", type=str, default=None)
    parser.add_argument("--comfy-mask", type=str, default=None)
    parser.add_argument(
        "--comfy-controlnet", action="append", default=None, dest="comfy_controlnet"
    )
    parser.add_argument("--comfy-lora", action="append", default=None, dest="comfy_lora")
    parser.add_argument("--comfy-node", action="append", default=None, dest="comfy_node")
    return parser


@lru_cache(maxsize=1)
def get_parser_defaults():
    parser = build_parser()
    defaults = {}
    for action in parser._actions:
        if action.dest != "help":
            defaults[action.dest] = action.default
    return defaults


def resolve_arg_or_option(args, options, dest, option_key=None):
    option_key = option_key or dest
    value = getattr(args, dest, None)
    if dest in getattr(args, "_explicit_args", set()):
        return value
    default = get_parser_defaults().get(dest)
    option_value = options.get(option_key)
    if value is not None and value != default:
        return value
    if option_value is not None:
        return option_value
    return value


def apply_logging_options(args):
    if args.debug:
        Logger.print_levels = [
            "info",
            "warning",
            "error",
            "critical",
            "verbose",
            "debug",
        ]
    if args.verbose:
        Logger.print_levels = ["info", "warning", "error", "critical", "verbose"]


def _resolve_save_image(comfy_save):
    mode = comfy_save.lower()
    if mode == "save":
        return ["websocket"]
    if mode == "both":
        return ["ui", "save"]
    if mode == "ui":
        return ["ui"]
    raise ValueError("api-comfy-save option error use [save, both, ui]")


def resolve_filename_pattern(args, options):
    defaults = get_parser_defaults()
    if (
        getattr(args, "api_filename_pattern", None) is not None
        and args.api_filename_pattern != defaults.get("api_filename_pattern")
    ):
        return args.api_filename_pattern
    if (
        getattr(args, "api_filname_pattern", None) is not None
        and args.api_filname_pattern != defaults.get("api_filname_pattern")
    ):
        return args.api_filname_pattern
    return options.get("filename_pattern")


def build_common_save_options(args, options):
    opt = {}
    opt["save_extend_meta"] = bool(
        resolve_arg_or_option(args, options, "save_extend_meta")
    )
    opt["image_type"] = resolve_arg_or_option(args, options, "image_type")
    opt["image_quality"] = resolve_arg_or_option(args, options, "image_quality")
    opt["escape_filename"] = bool(
        resolve_arg_or_option(args, options, "escape_filename")
    )
    filename_pattern = resolve_filename_pattern(args, options)
    if filename_pattern is not None:
        opt["filename_pattern"] = filename_pattern
    num_length = resolve_arg_or_option(args, options, "num_length")
    if num_length is not None:
        opt["num_length"] = num_length
    num_once = resolve_arg_or_option(args, options, "num_once")
    if num_once is not None:
        opt["num_once"] = num_once
    filename_variable = resolve_arg_or_option(args, options, "api_filename_variable")
    if filename_variable is not None:
        opt["api_filename_variable"] = bool(filename_variable)
    return opt


def normalize_comfy_args(args):
    config = {
        "enabled": bool(args.comfy or args.api_comfy),
        "mode": args.comfy_mode or None,
        "family": args.comfy_family,
        "template": args.comfy_template,
        "image": args.comfy_image,
        "mask": args.comfy_mask,
        "save": args.api_comfy_save,
        "controlnet": [],
        "loras": [],
        "nodes": {},
        "deprecated_flags_used": [],
    }

    if args.api_comfy:
        config["deprecated_flags_used"].append("--api-comfy")
    if args.api_comfy and args.api_comfy_save:
        config["deprecated_flags_used"].append("--api-comfy-save")

    if config["mode"] is None:
        if args.api_comfy and args.api_type in {"txt2img", "img2img", "interrogate"}:
            config["mode"] = args.api_type
        else:
            config["mode"] = "img2img" if config["image"] else "txt2img"

    if config["image"] is None and config["mode"] == "img2img" and args.input:
        if os.path.isfile(args.input):
            config["image"] = args.input

    if config["mask"] is None and args.mask_dirs:
        config["mask"] = args.mask_dirs

    for item in args.comfy_controlnet or []:
        config["controlnet"].append(parse_comfy_controlnet_arg(item))
    for item in args.comfy_lora or []:
        config["loras"].append(parse_comfy_lora_arg(item))
    for item in args.comfy_node or []:
        role, payload = parse_comfy_node_arg(item)
        config["nodes"].setdefault(role, {})
        merge_nested_dict(config["nodes"][role], payload)

    return config


def _serialize_output_text(output_text, options, args):
    if isinstance(output_text, str):
        return output_text

    text = copy.deepcopy(output_text)
    if not options.get("verbose"):
        for t in text:
            if t.get("verbose"):
                del t["verbose"]
    elif args.v1json:
        for t in text:
            verbose = t.get("verbose", {})
            variables = verbose.get("variables", {})
            for variable in variables:
                if len(variables[variable]) > 0:
                    t.setdefault("variables", {})
                    t["variables"][variable] = variables[variable][0]
            info = verbose.get("info", {})
            for item in info:
                if len(info[item]) > 0:
                    t.setdefault("info", {})
                    t["info"][item] = info[item][0]
            t.pop("verbose", None)
            t.pop("array", None)
    if args.prompt:
        text = [item.get("prompt", "") for item in text]
    if args.v1json or args.json_escape:
        return json.dumps(text, indent=2)
    return json.dumps(text, ensure_ascii=False, indent=2)


def build_or_load_payload(args):
    # Legacy image/directory input is handled by the img2img path, not the YAML reader.
    if (args.api_mode and args.api_type == "img2img" and args.input and
            os.path.splitext(args.input)[1].lower() not in (".yaml", ".yml")):
        return {"options": {}, "yml": {}, "output_text": [], "serialized_output": ""}
    if args.input is not None:
        opt = vars(args)
        result = create_text_v2(opt)
        if result is None:
            return None
        result["serialized_output"] = _serialize_output_text(
            result.get("output_text", []), result.get("options", {}), args
        )
        return result

    if args.api_input_json:
        options = {}
        yml = {}
        with open(args.api_input_json, "r", encoding="utf-8") as f:
            output_text = json.loads(f.read())
        if args.v1json:
            for t in output_text:
                if "verbose" in t:
                    verbose = t["verbose"]
                    t["variables"] = copy.deepcopy(verbose.get("variables", {}))
                    t["info"] = copy.deepcopy(verbose.get("info", {}))
                    del t["verbose"]
        if not isinstance(output_text, list):
            output_text["verbose"] = output_text.get("verbose", {})
            output_text = [output_text]
        return {
            "options": options,
            "yml": yml,
            "output_text": output_text,
            "serialized_output": json.dumps(output_text, ensure_ascii=False, indent=2),
        }

    raise Exception("option error")


def save_payload_if_needed(result, args):
    options = result.get("options", {})
    yml = result.get("yml", {})
    output_filename = yml.get("options", {}).get("output")
    if isinstance(output_filename, str):
        saver = DataSaver()
        saver.save_text(output_filename, result["serialized_output"])
        Logger.info(f"outputed file creat {output_filename}")
    return options, yml


def build_webui_config(args, options, yml):
    opt = build_common_save_options(args, options)
    userpass = resolve_arg_or_option(args, options, "api_userpass", "userpass")
    if userpass is not None:
        opt["userpass"] = userpass
    if "command" in yml:
        opt["command"] = yml["command"]
    if "info" in yml:
        opt["info"] = yml["info"]
    opt["sd_model"] = resolve_arg_or_option(args, options, "api_set_sd_model", "sd_model")
    opt["sd_vae"] = resolve_arg_or_option(args, options, "api_set_sd_vae", "sd_vae")
    opt["base_url"] = args.api_base
    opt["cn_images_dir"] = args.cn_images_dir
    opt["cn_save_pre"] = args.cn_save_pre
    for key in ("ui_type", "model_type", "image", "mask", "reference_images", "reference_max_size"):
        value = getattr(args, key, None)
        if value is None:
            value = options.get(key)
        if value is not None:
            opt[key] = value
    opt["generation_context"] = yml.get("_generation_context", {})
    opt["modules_explicit"] = "api_set_sd_vae" in getattr(args, "_explicit_args", set())
    return opt


def dispatch_interrogate(args):
    filenames = [args.input] if isinstance(args.input, str) else args.input
    for filename in filenames:
        result = interrogate(filename, base_url=args.api_base, model=args.model)
        Logger.info(result)
        if result.status_code == 200:
            Logger.info(filename)
            Logger.info(result.json()["caption"])
        else:
            Logger.info(result.text)
            Logger.info("Is Web UI replace newest version?")
    return True


def dispatch_webui_img2img(args):
    items = [
        "denoising_strength",
        "seed",
        "subseed",
        "subseed_strength",
        "batch_size",
        "n_iter",
        "steps",
        "cfg_scale",
        "width",
        "height",
        "prompt",
        "negative_prompt",
        "sampler_index",
        "mask_blur",
        "inpainting_fill",
        "inpaint_full_res",
        "inpaint_full_res_padding",
        "inpainting_mask_invert",
    ]
    overrides_arg = expand_arg(args.override)
    overrides = {}
    if overrides_arg is not None:
        for item in items:
            if overrides_arg.get(item):
                overrides[item] = overrides_arg[item]
    filenames = [args.input] if isinstance(args.input, str) else []
    output_dir = args.api_output_dir or "./outputs"
    input_files = []
    for filename in filenames:
        if os.path.isdir(filename):
            for file in os.listdir(filename):
                file = os.path.join(filename, file)
                if os.path.isfile(file):
                    input_files.append(file)
        elif os.path.isfile(filename):
            input_files.append(filename)
    if len(input_files) == 0:
        Logger.error("no exit files")
        return False
    img_opt = build_webui_config(args, {}, {})
    sd_model = img_opt.get("sd_model")
    sd_vae = img_opt.get("sd_vae")
    if sd_model is not None:
        api.set_sd_model(
            base_url=args.api_base,
            sd_model=sd_model,
            sd_vae=sd_vae,
        )
    img_opt["alt_image_dir"] = args.alt_image_dir
    img_opt["interrogate"] = args.interrogate
    img_opt["verbose"] = args.verbose
    img_opt["mask_dir"] = args.mask_dirs
    result = img2img(
        input_files,
        base_url=args.api_base,
        overrides=overrides,
        output_dir=output_dir,
        opt=img_opt,
    )
    return result if isinstance(result, bool) else bool(result) and all(r.get("success") for r in result)


def dispatch_webui(args, payload, options, yml):
    if args.api_type == "img2img" and not yml and not payload:
        return dispatch_webui_img2img(args)
    if args.api_type == "interrogate":
        return dispatch_interrogate(args)

    opt = build_webui_config(args, options, yml)
    from modules.generation_profile import resolve_context
    from modules.webui import prepare_payloads
    context = yml.get("_generation_context") or resolve_context(yml, vars(args))
    opt["generation_context"] = context
    opt["ui_type"] = context.get("ui_type")
    payload = copy.deepcopy(payload)
    if args.api_set_sd_model:
        from modules.webui import get_json, lookup_model
        models = context.get("server", {}).get("models") or get_json(
            args.api_base, "/sdapi/v1/sd-models", opt.get("userpass"))
        selected = lookup_model(models, args.api_set_sd_model)["title"]
        for item in payload:
            item.setdefault("override_settings", {})["sd_model_checkpoint"] = selected
    payload = prepare_payloads(payload, opt, args.api_type, context)
    sd_model = opt.get("sd_model")
    sd_vae = opt.get("sd_vae")
    if sd_model is not None:
        api.set_sd_model(base_url=args.api_base, sd_model=sd_model, sd_vae=sd_vae,
                         userpass=opt.get("userpass"))
    opt["api_type"] = args.api_type
    result = txt2img(
        payload, base_url=args.api_base, output_dir=args.api_output_dir, opt=opt
    )
    return bool(result)


def dispatch_comfy(args, payload, options, yml, comfy_config):
    from modules.comfyui import ComufyClient

    for flag in comfy_config.get("deprecated_flags_used", []):
        Logger.warning(f"{flag} is deprecated, use --comfy* options")

    save_image = _resolve_save_image(comfy_config["save"])
    opt = build_common_save_options(args, options)
    opt.update(
        {
        "sd_model": resolve_arg_or_option(args, options, "api_set_sd_model", "sd_model"),
        "sd_vae": resolve_arg_or_option(args, options, "api_set_sd_vae", "sd_vae"),
        "save_image": save_image,
        "workflow_family": comfy_config.get("family"),
        "workflow_mode": comfy_config.get("mode"),
        "workflow_template": comfy_config.get("template"),
        }
    )
    if opt["sd_vae"] == "Automatic":
        opt["sd_vae"] = None
    for key in ("image", "mask"):
        value = getattr(args, key, None) or options.get(key)
        if value is not None:
            opt[key] = value
    if opt.get("image") and not args.comfy_mode:
        opt["workflow_mode"] = "img2img"
    if args.reference_images or options.get("reference_images"):
        raise ValueError("reference_images requires Forge Neo; use a ComfyUI template for reference inputs")
    if comfy_config.get("image") is not None:
        opt["image"] = comfy_config["image"]
    if comfy_config.get("mask") is not None:
        opt["mask"] = comfy_config["mask"]
    if comfy_config.get("controlnet"):
        opt["controlnet"] = comfy_config["controlnet"]
    if comfy_config.get("loras"):
        opt["loras"] = comfy_config["loras"]
    if comfy_config.get("nodes"):
        opt["nodes"] = comfy_config["nodes"]
    result = ComufyClient.txt2img(
        payload,
        hostname=args.api_base,
        output_dir=args.api_output_dir,
        options=opt,
    )
    return bool(result)


def dispatch_backend(args, payload_result, comfy_config):
    options = payload_result.get("options", {})
    yml = payload_result.get("yml", {})
    payload = payload_result.get("output_text", [])

    if comfy_config["enabled"]:
        return dispatch_comfy(args, payload, options, yml, comfy_config)
    if args.api_mode:
        return dispatch_webui(args, payload, options, yml)
    return True


def main(args):
    # Runner integrations may provide a partial Namespace.
    supplied = vars(args).copy()
    defaults = vars(build_parser().parse_args([]))
    defaults.update(supplied)
    args = argparse.Namespace(**defaults)
    from modules.generation_profile import normalize_model_type
    normalize_model_type(args.model_type)
    if (args.comfy or args.api_comfy) and args.ui_type not in (None, "comfy"):
        raise ValueError("ComfyUI flags conflict with ui_type")
    if args.ui_type == "comfy" and args.api_mode:
        raise ValueError("ui_type=comfy requires --comfy (not --api-mode)")
    if (args.api_comfy or args.comfy) and args.api_mode:
        Logger.error("api-comfy and api-mode is not same time")
        return False

    comfy_config = normalize_comfy_args(args)
    payload_result = build_or_load_payload(args)
    if payload_result is None:
        return False
    save_payload_if_needed(payload_result, args)
    return dispatch_backend(args, payload_result, comfy_config)


def run_from_args(command_args=None):
    parser = build_parser()
    args = parser.parse_args(command_args)
    if args.values:
        args.values = divide_values(args.values)
    apply_logging_options(args)

    if args.input is None and not (
        (args.api_mode or args.api_comfy or args.comfy) and args.api_input_json is not None
    ):
        parser.print_help()
        Logger.info("need [input] or api/comfy input json")
        return False
    return main(args)


if __name__ == "__main__":
    try:
        result = run_from_args()
        if not result:
            exit(1)
    except Exception as e:
        print(f"Error, help is --help option {e}")
        exit(1)

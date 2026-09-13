import cp2
import os


def test_explicit_parser_default_overrides_yaml():
    args = cp2.build_parser().parse_args(["--image-type", "png", "--api-set-sd-vae", "Automatic"])
    opt = cp2.build_webui_config(args, {"image_type": "webp", "sd_vae": ["vae"]}, {})
    assert opt["image_type"] == "png"
    assert opt["sd_vae"] == "Automatic"
    args = cp2.build_parser().parse_args(["-VAutomatic"])
    assert cp2.build_webui_config(args, {"sd_vae": ["vae"]}, {})["sd_vae"] == "Automatic"


def test_text_encoder_default_and_yaml_cli_precedence():
    parser = cp2.build_parser()
    args = parser.parse_args(["input.yaml"])
    assert args.text_encoder == "Automatic"
    config = cp2.build_webui_config(
        args, {"vae": "neo-vae", "text_encoder": "qwen-encoder"}, {}
    )
    assert config["vae"] == "neo-vae"
    assert config["sd_vae"] == "neo-vae"
    assert config["text_encoder"] == "qwen-encoder"

    args = parser.parse_args(
        ["--api-set-sd-vae", "cli-vae", "--text-encoder", "cli-encoder", "input.yaml"]
    )
    config = cp2.build_webui_config(
        args, {"vae": "yaml-vae", "text_encoder": "yaml-encoder"}, {}
    )
    assert config["vae"] == "cli-vae"
    assert config["text_encoder"] == "cli-encoder"
    assert config["text_encoder_explicit"] is True
    assert config["modules_explicit"] is True

    args = parser.parse_args(["input.yaml"])
    config = cp2.build_webui_config(
        args, {"vae": "canonical", "sd_vae": "legacy"}, {}
    )
    assert config["vae"] == "canonical"

    config = cp2.build_webui_config(args, {"model": "canonical-model"}, {})
    assert config["sd_model"] == "canonical-model"


def test_normalize_comfy_args_from_legacy_flags():
    parser = cp2.build_parser()
    args = parser.parse_args(["--api-comfy", "--api-type", "img2img", "--mask-dirs", "mask.png"])
    config = cp2.normalize_comfy_args(args)
    assert config["enabled"] is True
    assert config["mode"] == "img2img"
    assert config["mask"] == "mask.png"
    assert "--api-comfy" in config["deprecated_flags_used"]


def test_normalize_comfy_args_from_new_flags():
    parser = cp2.build_parser()
    args = parser.parse_args(
        [
            "--comfy",
            "--comfy-family",
            "flux",
            "--comfy-mode",
            "txt2img",
            "--comfy-lora",
            "test_lora:0.8@positive",
            "--comfy-controlnet",
            "image=cn.png,strength=0.7",
            "--comfy-node",
            "model_adapter.class_type=ModelSamplingAuraFlow",
            "input.yaml",
        ]
    )
    config = cp2.normalize_comfy_args(args)
    assert config["enabled"] is True
    assert config["family"] == "flux"
    assert config["mode"] == "txt2img"
    assert config["loras"][0]["name"] == "test_lora"
    assert config["loras"][0]["weight"] == 0.8
    assert config["controlnet"][0]["image"] == "cn.png"
    assert config["nodes"]["model_adapter"]["class_type"] == "ModelSamplingAuraFlow"


def test_parse_comfy_node_arg_nested_inputs():
    role, payload = cp2.parse_comfy_node_arg("sampler.inputs.scheduler=karras")
    assert role == "sampler"
    assert payload["inputs"]["scheduler"] == "karras"


def test_build_webui_config_prefers_cli_filename_pattern():
    parser = cp2.build_parser()
    args = parser.parse_args(
        ["--api-mode", "--api-filename-pattern", "[seed]-cli", "input.yaml"]
    )
    opt = cp2.build_webui_config(
        args,
        {"filename_pattern": "[seed]-yaml", "escape_filename": False},
        {},
    )
    assert opt["filename_pattern"] == "[seed]-cli"


def test_build_webui_config_uses_legacy_typo_filename_pattern():
    parser = cp2.build_parser()
    args = parser.parse_args(
        ["--api-mode", "--api-filname-pattern", "[seed]-legacy", "input.yaml"]
    )
    opt = cp2.build_webui_config(
        args,
        {"filename_pattern": "[seed]-yaml", "escape_filename": False},
        {},
    )
    assert opt["filename_pattern"] == "[seed]-legacy"


def test_dispatch_comfy_passes_cli_filename_pattern():
    parser = cp2.build_parser()
    args = parser.parse_args(
        ["--api-comfy", "--api-filename-pattern", "[seed]-cli", "input.yaml"]
    )
    payload_result = {"output_text": [], "options": {"filename_pattern": "[seed]-yaml"}, "yml": {}}
    comfy_config = cp2.normalize_comfy_args(args)

    captured = {}

    class DummyClient:
        @staticmethod
        def txt2img(payload, hostname=None, output_dir=None, options=None):
            captured["payload"] = payload
            captured["hostname"] = hostname
            captured["output_dir"] = output_dir
            captured["options"] = options
            return True

    original = __import__("modules.comfyui", fromlist=["ComufyClient"])
    old_client = original.ComufyClient
    original.ComufyClient = DummyClient
    try:
        result = cp2.dispatch_backend(args, payload_result, comfy_config)
    finally:
        original.ComufyClient = old_client

    assert result is True
    assert captured["options"]["filename_pattern"] == "[seed]-cli"


def test_build_webui_config_keeps_automatic_sd_vae_default():
    parser = cp2.build_parser()
    args = parser.parse_args(["--api-mode", "input.yaml"])
    opt = cp2.build_webui_config(args, {}, {})
    assert opt["sd_vae"] == "Automatic"


def test_dispatch_comfy_converts_automatic_sd_vae_to_none():
    parser = cp2.build_parser()
    args = parser.parse_args(["--api-comfy", "input.yaml"])
    payload_result = {"output_text": [], "options": {}, "yml": {}}
    comfy_config = cp2.normalize_comfy_args(args)

    captured = {}

    class DummyClient:
        @staticmethod
        def txt2img(payload, hostname=None, output_dir=None, options=None):
            captured["options"] = options
            return True

    original = __import__("modules.comfyui", fromlist=["ComufyClient"])
    old_client = original.ComufyClient
    original.ComufyClient = DummyClient
    try:
        result = cp2.dispatch_backend(args, payload_result, comfy_config)
    finally:
        original.ComufyClient = old_client

    assert result is True
    assert captured["options"]["sd_vae"] is None


def test_build_webui_config_prefers_cli_save_options_over_yaml():
    parser = cp2.build_parser()
    args = parser.parse_args(
        [
            "--api-mode",
            "--image-type",
            "webp",
            "--image-quality",
            "91",
            "--save-extend-meta",
            "--escape-filename",
            "--num-length",
            "7",
            "--num-once",
            "--api-filename-variable",
            "input.yaml",
        ]
    )
    opt = cp2.build_webui_config(
        args,
        {
            "image_type": "png",
            "image_quality": 80,
            "save_extend_meta": False,
            "escape_filename": False,
            "num_length": 5,
            "num_once": False,
            "api_filename_variable": False,
        },
        {},
    )
    assert opt["image_type"] == "webp"
    assert opt["image_quality"] == 91
    assert opt["save_extend_meta"] is True
    assert opt["escape_filename"] is True
    assert opt["num_length"] == 7
    assert opt["num_once"] is True
    assert opt["api_filename_variable"] is True


def test_build_webui_config_uses_yaml_when_cli_is_parser_default():
    parser = cp2.build_parser()
    args = parser.parse_args(["--api-mode", "input.yaml"])
    opt = cp2.build_webui_config(
        args,
        {
            "image_type": "webp",
            "image_quality": 93,
            "save_extend_meta": True,
            "escape_filename": True,
            "num_length": 6,
            "num_once": True,
            "api_filename_variable": True,
        },
        {},
    )
    assert opt["image_type"] == "webp"
    assert opt["image_quality"] == 93
    assert opt["save_extend_meta"] is True
    assert opt["escape_filename"] is True
    assert opt["num_length"] == 6
    assert opt["num_once"] is True
    assert opt["api_filename_variable"] is True


def test_dispatch_webui_img2img_passes_hyphenated_options():
    parser = cp2.build_parser()
    image_path = os.path.abspath(__file__)
    args = parser.parse_args(
        [
            "--api-mode",
            "--api-type",
            "img2img",
            "--api-set-sd-model",
            "model.safetensors",
            "--api-set-sd-vae",
            "Automatic",
            "--image-type",
            "webp",
            "--image-quality",
            "95",
            "--save-extend-meta",
            "--escape-filename",
            "--num-length",
            "8",
            "--num-once",
            "--api-filename-pattern",
            "[seed]-[num]",
            "--api-filename-variable",
            "--mask-dirs",
            "mask-dir",
            "--alt-image-dir",
            "alt-dir",
            "--cn-images-dir",
            "cn-dir",
            "--cn-save-pre",
            "True",
            image_path,
        ]
    )

    captured = {}

    def fake_set_sd_model(base_url=None, sd_model=None, sd_vae=None):
        captured["set_sd_model"] = {
            "base_url": base_url,
            "sd_model": sd_model,
            "sd_vae": sd_vae,
        }

    def fake_img2img(imagefiles, overrides=None, base_url=None, output_dir=None, opt=None):
        captured["imagefiles"] = imagefiles
        captured["overrides"] = overrides
        captured["base_url"] = base_url
        captured["output_dir"] = output_dir
        captured["opt"] = opt
        return True

    old_set_sd_model = cp2.api.set_sd_model
    old_img2img = cp2.img2img
    cp2.api.set_sd_model = fake_set_sd_model
    cp2.img2img = fake_img2img
    try:
        result = cp2.dispatch_webui_img2img(args)
    finally:
        cp2.api.set_sd_model = old_set_sd_model
        cp2.img2img = old_img2img

    assert result is True
    assert captured["set_sd_model"]["sd_model"] == "model.safetensors"
    assert captured["set_sd_model"]["sd_vae"] == "Automatic"
    assert captured["imagefiles"] == [image_path]
    assert captured["opt"]["image_type"] == "webp"
    assert captured["opt"]["image_quality"] == 95
    assert captured["opt"]["save_extend_meta"] is True
    assert captured["opt"]["escape_filename"] is True
    assert captured["opt"]["num_length"] == 8
    assert captured["opt"]["num_once"] is True
    assert captured["opt"]["filename_pattern"] == "[seed]-[num]"
    assert captured["opt"]["api_filename_variable"] is True
    assert captured["opt"]["mask_dir"] == "mask-dir"
    assert captured["opt"]["alt_image_dir"] == "alt-dir"
    assert captured["opt"]["cn_images_dir"] == "cn-dir"
    assert captured["opt"]["cn_save_pre"] is True

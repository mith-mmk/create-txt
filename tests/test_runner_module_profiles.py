import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

import cp2
import create_prompts
from modules import api, webui
from modules.prompt_v2 import create_text_v2
from modules.tools.txt2img import _build_cp2_namespace


@pytest.fixture(params=[
    ("profile-vae", "profile-encoder"),
    ("null", "profile-encoder"), ("'None'", "profile-encoder"),
    ("[]", "profile-encoder"), ("null", "null"), ("[]", "[]"),
])
def profile_yaml(tmp_path, monkeypatch, request):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(webui, "inspect_server", lambda *a: {})
    path = tmp_path / "modules.yaml"
    source = """version: 2
options: {json: true, ui_type: neo}
command: {prompt: test}
methods: [{random: 1}]
model_profile:
  sdxl:
    options: {vae: profile-vae, text_encoder: profile-encoder}
"""
    vae, encoder = request.param
    source = source.replace("vae: profile-vae", f"vae: {vae}")
    source = source.replace("text_encoder: profile-encoder", f"text_encoder: {encoder}")
    path.write_text(source, encoding="utf-8")
    return (path, "profile-vae" if vae == "profile-vae" else [],
            "profile-encoder" if encoder == "profile-encoder" else [])


@pytest.mark.parametrize("selection", [None, "None", "", "explicit-vae", []])
def test_runner_inherits_modules_after_model_profile(profile_yaml, selection):
    profile_yaml, profile_vae, profile_encoder = profile_yaml
    args = _build_cp2_namespace(
        {"input": str(profile_yaml), "vae": selection, "text_encoder": "None"},
        "http://localhost:7860", SimpleNamespace(server_type="neo"),
    )
    args.api_set_sd_model = "sd_xl_base_1.0"
    args = SimpleNamespace(**(cp2.get_parser_defaults() | vars(args)))
    result = create_text_v2(vars(args))
    opt = cp2.build_webui_config(args, result["options"], result["yml"])
    expected = selection if selection == [] or selection == "explicit-vae" else profile_vae
    assert opt["vae"] == expected
    assert opt["text_encoder"] == profile_encoder


def test_explicit_cli_none_inherits_profile_modules(profile_yaml):
    profile_yaml, profile_vae, profile_encoder = profile_yaml
    args = cp2.build_parser().parse_args([
        str(profile_yaml), "--api-set-sd-model", "sd_xl_base_1.0",
        "--api-set-sd-vae", "None", "--text-encoder", "None",
    ])
    result = create_text_v2(vars(args))
    opt = cp2.build_webui_config(args, result["options"], result["yml"])
    assert opt["vae"] == profile_vae
    assert opt["text_encoder"] == profile_encoder
    assert not opt["vae_explicit"] and not opt["text_encoder_explicit"]


def test_legacy_cli_inherits_profile_modules(profile_yaml, monkeypatch):
    profile_yaml, profile_vae, profile_encoder = profile_yaml
    captured = []
    monkeypatch.setattr(api, "set_sd_model", lambda **kw: captured.append(kw) or True)
    monkeypatch.setattr(create_prompts, "txt2img", lambda *a, **kw: True)
    assert create_prompts.run_from_args([
        str(profile_yaml), "--api-mode", "--api-set-sd-model", "sd_xl_base_1.0",
        "--api-set-sd-vae", "None", "--text-encoder", "None",
    ])
    assert captured[0]["sd_vae"] == profile_vae
    assert captured[0].get("text_encoder", []) == profile_encoder


@pytest.mark.parametrize("direct", [True, False])
def test_run_loop_inherits_modules_for_selected_model(profile_yaml, monkeypatch, direct):
    profile_yaml, profile_vae, profile_encoder = profile_yaml
    spec = importlib.util.spec_from_file_location("run_loop", Path(__file__).parents[1] / "run-loop.py")
    loop = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loop)
    captured = []
    monkeypatch.setattr(api, "set_sd_model", lambda **kw: captured.append(kw) or True)
    import modules.txt2img
    monkeypatch.setattr(modules.txt2img, "txt2img", lambda *a, **kw: True)
    monkeypatch.setattr(create_prompts, "txt2img", lambda *a, **kw: True)
    def dispatch(args, result, comfy):
        captured.append(cp2.build_webui_config(args, result["options"], result["yml"]))
        return True
    monkeypatch.setattr(cp2, "dispatch_backend", dispatch)
    config = {
        "host": "http://localhost:7860",
        "txt2img": {
            "direct_call": direct, "version": 2,
            "models": [{"model_name": "sd_xl_base_1.0", "vae": "None", "mode": "XL"}],
            "prompts": [{"prompt_name": str(profile_yaml), "folder": "out", "number": "1",
                         "genre": "xl", "file_pattern": "[seed]"}],
            "prefix": {"default": "", "exception": "", "suffix": ""},
            "abort_matrix": {"XL": ["xl"]}, "output": str(profile_yaml.parent),
        },
    }
    loop.run_txt2img(config)
    assert len(captured) == 1
    assert captured[0]["sd_vae"] == profile_vae
    assert captured[0]["text_encoder"] == profile_encoder


def test_sdxl_builtin_modules_clear_previous_neo_selection(profile_yaml, monkeypatch):
    path, vae, encoder = profile_yaml
    args = cp2.build_parser().parse_args([
        str(path), "--api-set-sd-model", "sd_xl_base_1.0", "--api-set-sd-vae", "None",
    ])
    result = create_text_v2(vars(args))
    opt = cp2.build_webui_config(args, result["options"], result["yml"])
    settings = {"forge_additional_modules": ["old-vae", "old-encoder"]}
    models = [{"title": "sd_xl_base_1.0", "model_name": "sd_xl_base_1.0"}]
    modules = [{"model_name": name, "filename": "/" + name}
               for name in ("profile-vae", "profile-encoder")]
    monkeypatch.setattr(webui, "get_json", lambda base, route, *a: {
        "/sdapi/v1/options": settings, "/sdapi/v1/sd-models": models,
        "/sdapi/v1/sd-modules": modules,
    }[route])
    expected = ["/" + value for value in (vae, encoder) if value]
    prepared = webui.prepare_payloads(result["output_text"], opt, "txt2img", result["yml"]["_generation_context"])
    assert prepared[0]["override_settings"]["forge_additional_modules"] == expected
    import json
    captured = []
    monkeypatch.setattr(api, "request_post_wrapper", lambda *a: captured.append(json.loads(a[1])) or SimpleNamespace(status_code=200))
    api.set_sd_model("sd_xl_base_1.0", sd_vae=opt["vae"], text_encoder=opt["text_encoder"])
    assert captured[0]["forge_additional_modules"] == expected

import copy

import pytest
import yaml

import cp2
from modules.generation_profile import (
    apply_generation_profiles, infer_model_type, model_chain, resolve_context,
)
from modules.prompt_v2 import create_text_v2
from modules import webui


def test_full_profile_order_and_variables_before_expansion(tmp_path, monkeypatch):
    monkeypatch.setattr(webui, "get_json", lambda *a, **k: pytest.fail("offline network access"))
    source = {
        "version": 2, "options": {"json": True}, "methods": [{"random": 1}],
        "command": {"prompt": "${subject}", "steps": 1, "cfg_scale": 1},
        "variables": {"subject": ["base"]},
        "profiles": {
            "pre": {"command": {"steps": 2}},
            "selected": {"load_profile": ["pre"], "options": {"model_type": "noobai", "ui_type": "neo"},
                         "command": {"steps": 3}},
            "loaded": {"command": {"width": 1024}},
        },
        "model_profile": {
            "sdxl": {"command": {"steps": 4, "override_settings": {"x": 1}}, "variables": {"subject": ["parent"]}},
            "illustrious": {"command": {"steps": 5}},
            "noobai": {"load_profile": "loaded", "command": {"steps": 6, "cfg_scale": 4}},
        },
        "ui_profile": {"forge": {"command": {"width": 1}}, "neo": {
            "command": {"steps": 7, "override_settings": {"y": 2}},
            "variables": {"subject": ["ui"]}, "methods": [{"random": 2}],
        }},
    }
    path = tmp_path / "input.yaml"
    path.write_text(yaml.safe_dump(source), encoding="utf-8")
    result = create_text_v2({"input": str(path), "profile": "selected", "max_number": -1,
                             "override": ["steps=8,cfg_scale=0,tiling=false"]})
    assert len(result["output_text"]) == 2
    item = result["output_text"][0]
    assert item["prompt"] == "ui"
    assert item["steps"] == 8 and item["cfg_scale"] == 0 and item["tiling"] is False
    assert item["width"] == 1024
    assert item["override_settings"] == {"x": 1, "y": 2}
    assert result["yml"]["_generation_context"]["applied_profiles"] == [
        "model_profile.sdxl", "model_profile.illustrius", "model_profile.noobai", "ui_profile.neo"]
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == source
    again = create_text_v2({"input": str(path), "profile": "selected", "max_number": -1})
    assert again["output_text"][0]["steps"] == 7


@pytest.mark.parametrize("version", ["2b", "2.9b", "3.8b"])
def test_anima_version_inheritance_and_null(version):
    yml = {"options": {"model_type": f"anima_{version}"}, "command": {},
           "model_profile": {"anima": {"command": {"steps": 20}}, f"anima_{version}": None}}
    context = apply_generation_profiles(yml, {})
    assert yml["command"]["steps"] == 20
    assert context["model_type"] == f"anima_{version}"


def test_duplicate_alias_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        apply_generation_profiles({"model_profile": {"illustrious": {}, "illustrius": {}}}, {})


def test_profiles_deep_copy_and_single_resolution():
    patch = {"command": {"steps": 3}, "options": {"model_type": "noobai"}}
    original = copy.deepcopy(patch)
    yml = {"options": {"model_type": "sdxl"}, "model_profile": {
        "sdxl": patch, "noobai": {"command": {"steps": 99}}}}
    context = apply_generation_profiles(yml, {})
    assert context["model_type"] == "sdxl"
    assert yml["command"]["steps"] == 3
    yml["command"]["steps"] = 4
    assert patch == original


@pytest.mark.parametrize(("name", "expected"), [
    (r"models\NoobAI-XL-v1.safetensors", "noobai"),
    ("waiIllustriousSDXL_v170", "illustrius"), ("sd_xl_base_1.0", "sdxl"),
    ("anima_2.9b_fp8", "anima_2.9b"), ("Anima-3.8B", "anima_3.8b"),
    ("anima/Asuma_Anima_V1", "anima"), ("anima_2b-edit", "anima_2b-edit"),
    ("qwen_image_edit_2509", "qwen-image-edit"), ("flux1-kontext-dev", "flux-kontext"),
    ("flux2-klein-9b", "flux2-klein-9b"), ("chroma1-hd", "chroma-hd"),
    ("NetaYume-Lumina", "netayume-lumina"), ("z_image_turbo", "z-image-turbo"),
    ("ernie-image-turbo", "ernie-image-turbo"), ("krea2-raw", "krea2-raw"),
    ("v1-5-pruned", "sd15"), ("unknownXL", None), ("${model}", None),
    ("Wan2.2", None), ("PiD-1.5", None), ("flux2-dev", None),
])
def test_model_names(name, expected):
    assert infer_model_type(name) == expected


def test_explicit_checkpoint_over_current_and_metadata(monkeypatch):
    monkeypatch.setattr(webui, "inspect_server", lambda *a: {
        "ui_type": "neo", "options": {"sd_model_checkpoint": "anima_2b"},
        "models": [{"title": "custom", "metadata": {"modelspec.architecture": "stable-diffusion-xl-v1-base"}}]})
    context = resolve_context({}, {"api_mode": True, "api_set_sd_model": "custom"})
    assert context["checkpoint"] == "custom"
    assert context["model_type"] == "sdxl"
    context = resolve_context({"options": {"model_type": "sdxl"}},
                              {"api_mode": True, "model_type": "anima_3.8b"})
    assert context["model_type"] == "anima_3.8b"


def test_failed_connection_not_webui(monkeypatch):
    monkeypatch.setattr(webui, "get_json", lambda *a, **k: None)
    context = resolve_context({}, {"api_mode": True})
    assert context["ui_type"] is None and context["model_type"] is None


def test_unknown_skips_model_but_applies_ui():
    yml = {"options": {"ui_type": "neo"}, "model_profile": {"anima": {"command": {"steps": 1}}},
           "ui_profile": {"neo": {"command": {"steps": 2}}}}
    context = apply_generation_profiles(yml, {})
    assert context["model_type"] is None
    assert yml["command"]["steps"] == 2


@pytest.mark.parametrize("opt", [{"comfy": True, "ui_type": "neo"}, {"api_mode": True, "ui_type": "comfy"}])
def test_comfy_conflicts(opt):
    with pytest.raises(ValueError, match="[Cc]omfy"):
        resolve_context({}, opt)


def test_ui_type_does_not_enable_api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "prompt.yaml"
    path.write_text("version: 2\noptions: {json: true}\ncommand: {prompt: cat}\nmethods: [{random: 1}]\n", encoding="utf-8")
    monkeypatch.setattr(webui, "get_json", lambda *a, **k: pytest.fail("offline network access"))
    args = cp2.build_parser().parse_args([str(path), "--ui-type", "neo", "--model-type", "sdxl"])
    assert cp2.main(args)


def test_neo_rejects_sd3_but_comfy_keeps_it():
    with pytest.raises(ValueError, match="does not support"):
        resolve_context({}, {"ui_type": "neo", "model_type": "sd35"})
    assert resolve_context({}, {"comfy": True, "model_type": "sd35"})["model_type"] == "sd35"

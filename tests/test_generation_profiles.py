import copy

import pytest
import yaml

import cp2
from modules.generation_profile import (
    apply_generation_profiles, checkpoint_identifiers, infer_model_type, model_chain,
    resolve_context,
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


def test_model_profile_options_include_modules():
    yml = {
        "options": {"model_type": "noobai"},
        "model_profile": {
            "sdxl": {"options": {"vae": "base-vae"}},
            "illustrius": {"options": {"text_encoder": "clip-l"}},
            "noobai": {"options": {"vae": "noobai-vae"}},
        },
    }
    context = apply_generation_profiles(yml, {})
    assert context["applied_profiles"] == [
        "model_profile.sdxl", "model_profile.illustrius", "model_profile.noobai"
    ]
    assert yml["options"]["vae"] == "noobai-vae"
    assert yml["options"]["text_encoder"] == "clip-l"


def test_checkpoint_profile_applies_after_model_before_ui_and_before_expansion():
    yml = {
        "options": {"model_type": "anima_2.9b", "model": "JANIMAAnima_v1029B_bf16.safetensors"},
        "command": {"prompt": "${subject}", "steps": 1},
        "variables": {"subject": ["base"]},
        "profiles": {"checkpoint-base": {"command": {"width": 1024}}},
        "model_profile": {
            "anima": {"command": {"steps": 20}, "variables": {"subject": ["anima"]}},
            "anima_2.9b": {"command": {"steps": 24}, "options": {"vae": "base-vae"}},
        },
        "checkpoint_profile": {
            "JANIMAAnima_v1029B_bf16.safetensors": {
                "load_profile": "checkpoint-base",
                "command": {"steps": 30},
                "variables": {"subject": ["checkpoint"]},
                "options": {"text_encoder": "qwen-encoder"},
            },
        },
        "ui_profile": {"neo": {"command": {"steps": 32}, "variables": {"subject": ["ui"]}}},
    }

    context = apply_generation_profiles(yml, {"ui_type": "neo"})

    assert context["checkpoint"] == "JANIMAAnima_v1029B_bf16.safetensors"
    assert context["applied_profiles"] == [
        "model_profile.anima",
        "model_profile.anima_2.9b",
        "checkpoint_profile.JANIMAAnima_v1029B_bf16.safetensors",
        "ui_profile.neo",
    ]
    assert yml["command"] == {"prompt": "${subject}", "steps": 32, "width": 1024}
    assert yml["options"]["vae"] == "base-vae"
    assert yml["options"]["text_encoder"] == "qwen-encoder"
    assert yml["variables"]["subject"] == ["ui"]


def test_checkpoint_profile_matches_path_basename_stem_and_hash_suffix():
    assert checkpoint_identifiers(r"models\anima\JANIMAAnima_v1029B_bf16.safetensors [abc123]") == {
        "models/anima/janimaanima_v1029b_bf16.safetensors",
        "janimaanima_v1029b_bf16.safetensors",
        "janimaanima_v1029b_bf16",
    }
    yml = {
        "options": {"model": r"E:\models\JANIMAAnima_v1029B_bf16.safetensors [abc123]"},
        "command": {},
        "checkpoint_profile": {
            "JANIMAAnima_v1029B_bf16.safetensors": {"command": {"cfg_scale": 4}}
        },
    }
    context = apply_generation_profiles(yml, {})
    assert context["applied_profiles"] == [
        "checkpoint_profile.JANIMAAnima_v1029B_bf16.safetensors"
    ]
    assert yml["command"]["cfg_scale"] == 4

    yml["options"]["model"] = r"E:\models\JANIMAAnima_v1029B_bf16.safetensors"
    yml["checkpoint_profile"] = {
        "JANIMAAnima_v1029B_bf16": {"command": {"steps": 31}}
    }
    context = apply_generation_profiles(yml, {})
    assert context["applied_profiles"] == [
        "checkpoint_profile.JANIMAAnima_v1029B_bf16"
    ]
    assert yml["command"]["steps"] == 31


def test_checkpoint_profile_unknown_and_empty_are_noop():
    empty = {"options": {"model": "unknown.safetensors"}, "command": {"steps": 1},
             "checkpoint_profile": {}}
    context = apply_generation_profiles(empty, {})
    assert context["applied_profiles"] == []
    assert empty["command"] == {"steps": 1}

    unknown = {"options": {"model": "unknown.safetensors"}, "command": {"steps": 1},
               "checkpoint_profile": {"known.safetensors": {"command": {"steps": 2}}}}
    context = apply_generation_profiles(unknown, {})
    assert context["applied_profiles"] == []
    assert unknown["command"] == {"steps": 1}


def test_checkpoint_profile_duplicate_match_is_rejected():
    yml = {
        "options": {"model": "shared.safetensors"},
        "checkpoint_profile": {
            r"models\a\shared.safetensors": {},
            r"models\b\shared.safetensors": {},
        },
    }
    with pytest.raises(ValueError, match="Ambiguous checkpoint_profile"):
        apply_generation_profiles(yml, {})


def test_checkpoint_profile_prefers_exact_path_over_duplicate_basename():
    yml = {
        "options": {"model": r"models\a\shared.safetensors"},
        "checkpoint_profile": {
            r"models\a\shared.safetensors": {"command": {"cfg_scale": 3}},
            r"models\b\shared.safetensors": {"command": {"cfg_scale": 4}},
            "shared.safetensors": {"command": {"cfg_scale": 5}},
        },
    }
    context = apply_generation_profiles(yml, {})
    assert context["applied_profiles"] == [
        r"checkpoint_profile.models\a\shared.safetensors"
    ]
    assert yml["command"]["cfg_scale"] == 3


def test_checkpoint_profile_matches_api_model_entry(monkeypatch):
    monkeypatch.setattr(webui, "inspect_server", lambda *a: {
        "ui_type": "neo",
        "options": {"sd_model_checkpoint": r"anima\JANIMAAnima_v1029B_bf16.safetensors [abc123]"},
        "models": [{
            "title": r"anima\JANIMAAnima_v1029B_bf16.safetensors [abc123]",
            "model_name": "anima_JANIMAAnima_v1029B_bf16",
            "filename": r"E:\models\JANIMAAnima_v1029B_bf16.safetensors",
        }],
    })
    yml = {
        "options": {"ui_type": "neo"},
        "command": {},
        "checkpoint_profile": {
            "JANIMAAnima_v1029B_bf16.safetensors": {"command": {"steps": 30}}
        },
    }
    context = apply_generation_profiles(yml, {"api_mode": True})
    assert context["checkpoint_entry"]["model_name"] == "anima_JANIMAAnima_v1029B_bf16"
    assert context["applied_profiles"] == [
        "checkpoint_profile.JANIMAAnima_v1029B_bf16.safetensors"
    ]
    assert yml["command"]["steps"] == 30


def test_checkpoint_profile_is_expanded_before_variables(tmp_path):
    path = tmp_path / "checkpoint-profile.yaml"
    path.write_text("""version: 2
options:
  json: true
  model: exact.safetensors
  model_type: anima
  ui_type: neo
command: {prompt: '${subject}'}
variables: {subject: [base]}
methods: [{random: 1}]
model_profile:
  anima:
    variables: {subject: [anima]}
checkpoint_profile:
  exact.safetensors:
    variables: {subject: [checkpoint]}
ui_profile:
  neo:
    variables: {subject: [ui]}
""", encoding="utf-8")
    result = create_text_v2({"input": str(path), "max_number": -1})
    assert result["output_text"][0]["prompt"] == "ui"
    assert result["yml"]["_generation_context"]["applied_profiles"] == [
        "model_profile.anima",
        "checkpoint_profile.exact.safetensors",
        "ui_profile.neo",
    ]


@pytest.mark.parametrize(("name", "expected"), [
    (r"models\NoobAI-XL-v1.safetensors", "noobai"),
    (r"models\Pony-v6.safetensors", "pony"),
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


def test_pony_inherits_sdxl():
    assert model_chain("pony") == ["sdxl", "pony"]


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
    context = resolve_context({"options": {"model": "pony-v6.safetensors"}}, {})
    assert context["checkpoint"] == "pony-v6.safetensors"
    assert context["model_type"] == "pony"


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

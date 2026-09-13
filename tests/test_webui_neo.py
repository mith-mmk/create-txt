import base64
import copy
import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

import cp2
from modules import api, webui
from modules.txt2img import txt2img
from modules.save import save_images


@pytest.fixture
def picture(tmp_path):
    path = tmp_path / "input.png"
    Image.new("RGB", (64, 64), "white").save(path)
    return str(path)


def context(model="anima", **options):
    return {"ui_type": "neo", "model_type": model, "server": {"options": {
        "anima_do_reference": False, "klein_do_reference": True, **options}}}


def test_image_mask_reference_order_and_edit_setting(picture, monkeypatch):
    scripts = [{"name": "imagestitch integrated", "is_alwayson": True, "is_img2img": True}]
    monkeypatch.setattr(webui, "get_json", lambda *a, **k: scripts)
    original = [{"prompt": "cat", "override_settings": {"unrelated": 1}}]
    opt = {"image": picture, "mask": picture, "reference_images": [picture, picture], "reference_max_size": 512}
    result = webui.prepare_payloads(original, opt, "img2img", context())[0]
    assert len(result["init_images"]) == 1
    Image.open(io.BytesIO(base64.b64decode(result["mask"]))).verify()
    args = result["alwayson_scripts"]["ImageStitch Integrated"]["args"]
    assert args == [True, [webui.encode_image(picture)] * 2, 512]
    assert result["override_settings"] == {"unrelated": 1, "anima_do_reference": True}
    assert result["denoising_strength"] == 1.0
    assert original == [{"prompt": "cat", "override_settings": {"unrelated": 1}}]


@pytest.mark.parametrize("model,key", [("anima", "anima_do_reference"), ("flux2-klein-4b", "klein_do_reference")])
def test_normal_img2img_disables_edit(picture, model, key):
    result = webui.prepare_payloads([{}], {"image": picture}, "img2img", context(model))[0]
    assert result["override_settings"][key] is False


def test_missing_script_fails_before_generation(picture, monkeypatch):
    monkeypatch.setattr(webui, "get_json", lambda *a, **k: [])
    with pytest.raises(ValueError, match="ImageStitch"):
        webui.prepare_payloads([{}], {"reference_images": [picture]}, "txt2img", context())


def test_missing_edit_capability(picture):
    ctx = {"ui_type": "neo", "model_type": "anima-edit", "server": {"options": {}}}
    with pytest.raises(ValueError, match="anima_do_reference"):
        webui.prepare_payloads([{}], {"image": picture}, "img2img", ctx)


@pytest.mark.parametrize("opt,mode", [({}, "img2img"), ({"reference_images": "wrong"}, "txt2img"),
                                      ({"reference_max_size": 3}, "txt2img")])
def test_invalid_inputs(opt, mode):
    with pytest.raises(ValueError):
        webui.prepare_payloads([{}], opt, mode, context())


def test_missing_image_no_generation(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        webui.encode_image(str(tmp_path / "missing.png"))


def test_small_base64_init_image_is_not_treated_as_filename(picture):
    encoded = webui.encode_image(picture)
    assert len(encoded) < 512
    item = webui.prepare_payloads([{"init_images": [encoded]}], {}, "img2img", context())[0]
    assert item["init_images"] == [encoded]


def test_module_resolution_and_ambiguity():
    modules = [{"model_name": "vae.safetensors", "filename": "/a/vae.safetensors"},
               {"model_name": "vae-other.safetensors", "filename": "/a/vae-other.safetensors"}]
    assert webui.resolve_modules(modules, "vae.safetensors") == ["/a/vae.safetensors"]
    with pytest.raises(ValueError, match="ambiguous"):
        webui.resolve_modules(modules, "vae")
    with pytest.raises(ValueError, match="not found"):
        webui.resolve_modules(modules, "missing")


def test_checkpoint_hash_suffix_and_metadata_item(monkeypatch):
    model = {"title": "anima\\custom.safetensors [123456abcd]", "filename": "models\\anima\\custom.safetensors"}
    assert webui.lookup_model([model], "anima/custom.safetensors") == model
    assert webui.lookup_model([model], "custom") == model
    captured = {}
    def get(*a, **kwargs):
        captured.update(kwargs)
        return {"metadata": '{"modelspec.architecture": "sdxl"}'}
    monkeypatch.setattr(webui, "get_json", get)
    assert webui.read_metadata("http://localhost:7860", model)["modelspec.architecture"] == "sdxl"
    assert captured["params"] == {"page": "checkpoints", "item": "custom"}


def test_modules_option_without_checkpoint_and_explicit_automatic(monkeypatch):
    monkeypatch.setattr(webui, "get_json", lambda *a, **k: [
        {"model_name": "vae.safetensors", "filename": "/vae.safetensors"}])
    item = webui.prepare_payloads([{}], {"sd_vae": ["vae.safetensors"]}, "txt2img", context())[0]
    assert item["override_settings"]["forge_additional_modules"] == ["/vae.safetensors"]
    item = webui.prepare_payloads([{"override_settings": {"forge_additional_modules": ["bad"]}}],
                                 {"sd_vae": "Automatic", "modules_explicit": True}, "txt2img", context())[0]
    assert "override_settings" not in item


def test_vae_and_text_encoder_modules_are_combined(monkeypatch):
    monkeypatch.setattr(webui, "get_json", lambda *a, **k: [
        {"model_name": "vae.safetensors", "filename": "/modules/vae.safetensors"},
        {"model_name": "encoder.safetensors", "filename": "/modules/encoder.safetensors"},
    ])
    item = webui.prepare_payloads(
        [{}],
        {"vae": "vae.safetensors", "text_encoder": "encoder.safetensors"},
        "txt2img",
        context(),
    )[0]
    assert item["override_settings"]["forge_additional_modules"] == [
        "/modules/vae.safetensors", "/modules/encoder.safetensors"
    ]


def test_canonical_vae_wins_over_legacy_alias(monkeypatch):
    monkeypatch.setattr(webui, "get_json", lambda *a, **k: [
        {"model_name": "canonical", "filename": "/modules/canonical.safetensors"}
    ])
    item = webui.prepare_payloads(
        [{}], {"vae": "canonical", "sd_vae": "legacy"}, "txt2img", context()
    )[0]
    assert item["override_settings"]["forge_additional_modules"] == [
        "/modules/canonical.safetensors"
    ]


def test_automatic_text_encoder_does_not_clear_modules(monkeypatch):
    monkeypatch.setattr(webui, "get_json", lambda *args, **kwargs: [
        {"model_name": "existing", "filename": "/modules/existing.safetensors"}
    ])
    item = webui.prepare_payloads(
        [{"override_settings": {"forge_additional_modules": ["existing"]}}],
        {"vae": "Automatic", "text_encoder": "Automatic"},
        "txt2img",
        context(),
    )[0]
    assert item["override_settings"]["forge_additional_modules"] == [
        "/modules/existing.safetensors"
    ]


def test_plain_webui_rejects_explicit_text_encoder():
    with pytest.raises(ValueError, match="requires Forge"):
        webui.prepare_payloads(
            [{}], {"text_encoder": "clip.safetensors"}, "txt2img",
            {"ui_type": "webui", "model_type": "sdxl", "server": {"options": {}}},
        )


def test_configure_model_combines_vae_and_text_encoder(monkeypatch):
    responses = {
        "/sdapi/v1/options": {"sd_model_checkpoint": "old", "forge_additional_modules": []},
        "/sdapi/v1/sd-models": [{"title": "anima/model.safetensors"}],
        "/sdapi/v1/sd-modules": [
            {"model_name": "vae.safetensors", "filename": "/vae.safetensors"},
            {"model_name": "clip.safetensors", "filename": "/clip.safetensors"},
        ],
    }
    monkeypatch.setattr(webui, "get_json", lambda _base, path, *args, **kwargs: responses[path])
    sent = []
    monkeypatch.setattr(
        api,
        "request_post_wrapper",
        lambda _url, data, *args, **kwargs: sent.append(json.loads(data))
        or SimpleNamespace(status_code=200),
    )
    assert api.set_sd_model(
        "model.safetensors", sd_vae="vae.safetensors", text_encoder="clip.safetensors"
    )
    assert sent[0]["forge_additional_modules"] == ["/vae.safetensors", "/clip.safetensors"]


def test_missing_payload_checkpoint_is_rejected(monkeypatch):
    monkeypatch.setattr(webui, "get_json", lambda *a, **k: [])
    with pytest.raises(ValueError, match="Checkpoint not found"):
        webui.prepare_payloads([{"override_settings": {"sd_model_checkpoint": "missing"}}], {}, "txt2img", context())


@pytest.mark.parametrize("vae,expected", [("Automatic", None), (None, None), ([], []),
                                        ("qwen_vae", ["/vae/qwen_vae.safetensors"])])
def test_set_model_preserves_omitted_modules_and_reports_errors(monkeypatch, vae, expected):
    def fake_get(base, path, *a, **k):
        return {
            "/sdapi/v1/options": {"sd_model_checkpoint": "old", "forge_additional_modules": ["current"]},
            "/sdapi/v1/sd-models": [{"title": "anima/model.safetensors", "model_name": "anima_model"}],
            "/sdapi/v1/sd-modules": [{"model_name": "qwen_vae.safetensors", "filename": "/vae/qwen_vae.safetensors"}],
        }[path]
    monkeypatch.setattr(webui, "get_json", fake_get)
    sent = []
    monkeypatch.setattr(api, "request_post_wrapper", lambda *a, **k: sent.append(json.loads(a[1])) or SimpleNamespace(status_code=200))
    assert api.set_sd_model("model", sd_vae=vae)
    assert sent[0]["sd_model_checkpoint"] == "anima/model.safetensors"
    if expected is None:
        assert "forge_additional_modules" not in sent[0]
    else:
        assert sent[0]["forge_additional_modules"] == expected
    monkeypatch.setattr(api, "request_post_wrapper", lambda *a, **k: SimpleNamespace(status_code=500))
    with pytest.raises(ValueError, match="Failed to change"):
        api.set_sd_model("model")


def test_yaml_img2img_dispatch_uses_profile_settings_and_cli(tmp_path, picture, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "input.yaml"
    path.write_text("""version: 2
options:
  ui_type: neo
  model_type: anima
  image: IMAGE_PATH
methods: [{random: 1}]
command: {prompt: cat, steps: 1}
model_profile:
  anima:
    command: {steps: 2}
ui_profile:
  neo:
    options: {image_type: webp}
    command: {steps: 3}
""".replace("IMAGE_PATH", json.dumps(picture)), encoding="utf-8")
    monkeypatch.setattr(webui, "inspect_server", lambda *a: context()["server"])
    captured = {}
    def send(payload, **kw):
        captured.update(payload=copy.deepcopy(payload), **kw)
        return True
    monkeypatch.setattr(cp2, "txt2img", send)
    args = cp2.build_parser().parse_args([str(path), "--api-mode", "--api-type", "img2img", "--override", "steps=4"])
    assert cp2.main(args)
    assert captured["payload"][0]["steps"] == 4
    assert captured["payload"][0]["init_images"]
    assert captured["opt"]["image_type"] == "webp"
    assert captured["opt"]["api_type"] == "img2img"


@pytest.mark.parametrize("status,images,expected", [(500, [], False), (200, [], False), (200, ["image"], True)])
def test_generation_success_requires_saved_images(tmp_path, monkeypatch, status, images, expected):
    monkeypatch.setattr(api, "request_post_wrapper", lambda *a, **k: SimpleNamespace(
        status_code=status, text="failed", json=lambda: {"images": images}))
    import importlib
    module = importlib.import_module("modules.txt2img")
    monkeypatch.setattr(module, "save_images", lambda *a, **k: len(images))
    assert txt2img([{"prompt": "cat"}], output_dir=str(tmp_path), opt={}) is expected


def test_real_saver_returns_saved_count(tmp_path, picture):
    response = {"images": [webui.encode_image(picture)], "info": json.dumps({
        "infotexts": ["cat\nSteps: 1, Sampler: Euler, CFG scale: 1, Seed: 42, Size: 64x64"],
        "all_seeds": [42], "all_prompts": ["cat"], "seed": 42}), "parameters": {"seed": 42}}
    assert save_images(response, {"dir": str(tmp_path), "filename_pattern": "generated-[num]-[seed]", "verbose": False}) == 1
    assert len(list(tmp_path.glob("generated-*.png"))) == 1
    response["images"] = ["invalid"]
    with pytest.raises(Exception):
        save_images(response, {"dir": str(tmp_path)})


def test_image_save_failure_is_propagated(tmp_path, monkeypatch):
    from modules.save import image_save
    def fail(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(Image.Image, "save", fail)
    with pytest.raises(OSError, match="disk full"):
        image_save(Image.new("RGB", (1, 1)), str(tmp_path / "out.png"), "", None)


def test_runner_detects_neo_before_other_comfy_port(monkeypatch):
    from modules.tools import events
    calls = []
    def get(url):
        calls.append(url)
        return SimpleNamespace(status_code=200, json=lambda: {"forge_additional_modules": [], "anima_do_reference": False})
    monkeypatch.setattr(events, "_get", get)
    assert events.detect_server("http://localhost:7860") == "neo"
    assert calls == ["http://localhost:7860/sdapi/v1/options"]


def test_runner_passes_selected_model_without_eager_switch(monkeypatch):
    from modules.tools import txt2img as runner
    profile = {"input": "example.yaml", "models": ["anima_2b"], "model_type": "anima_2b",
               "options": {"ui_type": "neo", "reference_images": ["reference.png"]}}
    context_stub = SimpleNamespace(get_profile=lambda *a: profile, effective_host=lambda: "http://localhost:7860",
                                   dry_run=False, config={}, get_var=lambda *a: None, server_type="neo")
    captured = []
    monkeypatch.setattr(cp2, "main", lambda args: captured.append(args) or False)
    monkeypatch.setattr(api, "set_sd_model", lambda *a, **k: pytest.fail("eager switch"))
    assert runner.run("sample", context_stub) is False
    assert captured[0].api_set_sd_model == "anima_2b"
    assert captured[0].ui_type == "neo" and captured[0].reference_images == ["reference.png"]


def test_runner_namespace_uses_canonical_module_options():
    from modules.tools import txt2img as runner
    profile = {"options": {"vae": "vae.safetensors", "text_encoder": "clip.safetensors"}}
    context_stub = SimpleNamespace(server_type="neo")
    args = runner._build_cp2_namespace(profile, "http://localhost:7860", context_stub)
    assert args.api_set_sd_vae == "vae.safetensors"
    assert args.text_encoder == "clip.safetensors"

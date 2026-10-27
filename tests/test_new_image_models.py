"""Contracts shared by conditional profiles, CLI and the ComfyUI compiler."""

import pytest
from pathlib import Path

import cp2
from modules.comfyui import ComfyUIWorkflow
from modules.comfyui.checker import WorkflowChecker
from modules.comfyui.workflow import build_comfyui_spec
from modules.prompt_v2 import create_text_v2


@pytest.mark.parametrize("family,clip_type,latent", [
    ("qwen-image-2.1", "qwen_image", "EmptyLatentImage"),
    ("qwen-image2.1", "qwen_image", "EmptyLatentImage"),
    ("moss-image", "moss_image", "EmptyFlux2LatentImage"),
    ("moss-turbo", "moss_image", "EmptyFlux2LatentImage"),
    ("moss-image-turbo", "moss_image", "EmptyFlux2LatentImage"),
])
@pytest.mark.parametrize("mode", ["txt2img", "img2img"])
def test_new_model_graphs(family, clip_type, latent, mode):
    options = {"workflow_family": family, "workflow_mode": mode,
               "checkpoint": "model.safetensors", "vae": "custom-vae.safetensors",
               "text_encoder": "custom-encoder.safetensors"}
    if mode == "img2img":
        options.update(image="input.png", mask="mask.png")
    workflow, info = ComfyUIWorkflow().createWorkflow("teapot", "blurry", options)
    roles = {node["_meta"]["role"]: node for node in workflow.values()}
    assert roles["model_loader"]["class_type"] == "UNETLoader"
    assert roles["clip_loader"]["inputs"] == {
        "clip_name": "custom-encoder.safetensors", "type": clip_type,
    }
    assert roles["vae_loader"]["inputs"]["vae_name"] == "custom-vae.safetensors"
    sampler = roles["sampler"]["inputs"]
    assert sampler["scheduler"] == "simple"
    assert sampler["sampler_name"] == "euler"
    assert info["width"] == info["height"] == 1024
    if mode == "txt2img":
        assert roles["latent"]["class_type"] == latent
        assert roles["latent"]["inputs"]["width"] == 1024
    else:
        assert roles["vae_encode"]["class_type"] == "VAEEncode"
        assert roles["latent_mask"]["class_type"] == "SetLatentNoiseMask"
    if clip_type == "qwen_image":
        positive_id = sampler["positive"][0]
        encoder = workflow[positive_id]
        assert encoder["class_type"] == "TextEncodeQwenImage21"
        assert encoder["inputs"]["prompt"] == "teapot"
        assert encoder["inputs"]["negative_prompt"] == "blurry"
        assert sampler["negative"] == [positive_id, 1]
        checker = WorkflowChecker()
        assert checker._prompt_search(workflow, {}, sampler["positive"]) == "teapot"
        assert checker._prompt_search(workflow, {}, sampler["negative"]) == "blurry"


@pytest.mark.parametrize("family,encoder,vae", [
    ("qwen-image-2.1", "qwen3vl_8b_int8_convrot.safetensors", "qwen_image_2.1_vae_bf16.safetensors"),
    ("moss", "qwen3.5_9b_w4a8_gptq.safetensors", "flux2-vae_small.safetensors"),
    ("moss-turbo", "qwen3.5_9b_w4a8_gptq.safetensors", "flux2-vae_small.safetensors"),
])
def test_runner_spec_and_defaults(family, encoder, vae):
    spec, merged = build_comfyui_spec({"prompt": "test"}, {
        "workflow_family": family, "sd_model": "model.safetensors",
        "text_encoder": "Automatic", "vae": "Automatic",
    })
    workflow, _ = ComfyUIWorkflow().createWorkflowFromSpec(spec, merged)
    roles = {node["_meta"]["role"]: node for node in workflow.values()}
    assert roles["clip_loader"]["inputs"]["clip_name"] == encoder
    assert roles["vae_loader"]["inputs"]["vae_name"] == vae
    assert roles["sampler"]["inputs"]["scheduler"] == "simple"
    checker = WorkflowChecker()
    assert checker._normalize_sampler_config("euler", "simple") == ("euler", "simple")


@pytest.mark.parametrize("model_type", ["qwen-image-2.1", "qwen-image-2.1-turbo", "moss", "moss-turbo"])
def test_comfy_dispatch_uses_resolved_profile_family(model_type, monkeypatch):
    from modules.comfyui import ComufyClient

    captured = {}

    def generate(payload, **kwargs):
        captured.update(kwargs["options"])
        return True

    monkeypatch.setattr(ComufyClient, "txt2img", generate)
    args = cp2.build_parser().parse_args(["--comfy", "input.yaml"])
    assert cp2.dispatch_comfy(args, [{"prompt": "teapot"}], {
        "vae": "custom-vae", "text_encoder": "custom-encoder",
    }, {"_generation_context": {"model_type": model_type}}, cp2.normalize_comfy_args(args))
    assert captured["workflow_family"] == model_type
    assert captured["vae"] == "custom-vae"
    assert captured["text_encoder"] == "custom-encoder"


@pytest.mark.parametrize("family", ["moss-image", "moss-turbo", "moss-image-turbo"])
def test_comfy_family_cli_override(monkeypatch, family):
    from modules.comfyui import ComufyClient

    captured = {}
    monkeypatch.setattr(ComufyClient, "txt2img", lambda payload, **kw: captured.update(kw["options"]) or True)
    args = cp2.build_parser().parse_args(["--comfy", "--comfy-family", family, "input.yaml"])
    cp2.dispatch_comfy(args, [], {}, {"_generation_context": {"model_type": "qwen-image-2.1"}},
                       cp2.normalize_comfy_args(args))
    assert captured["workflow_family"] == family


@pytest.mark.parametrize("profile,model_type,steps", [
    ("qwen21", "qwen-image-2.1", 32), ("moss", "moss", 50),
    ("qwen21-turbo", "qwen-image-2.1-turbo", 8),
])
def test_example_profiles_compile_offline(profile, model_type, steps):
    path = Path(__file__).resolve().parents[1] / "examples" / "qwen21-moss.yaml"
    result = create_text_v2({"input": str(path), "profile": profile,
                             "ui_type": "comfy", "json": True, "max_number": -1})
    context = result["yml"]["_generation_context"]
    assert context["model_type"] == model_type
    expected = [f"model_profile.{model_type}", "ui_profile.comfy"]
    if model_type.endswith("-turbo"):
        expected.insert(0, "model_profile.qwen-image-2.1")
    assert context["applied_profiles"] == expected
    options = dict(result["options"], workflow_family=model_type)
    spec, merged = build_comfyui_spec(result["output_text"][0], options)
    workflow, info = ComfyUIWorkflow().createWorkflowFromSpec(spec, merged)
    assert info["steps"] == steps
    assert info["scheduler"] == ("qwen21_turbo" if model_type.endswith("-turbo") else "simple")
    assert any(n["class_type"] == "UNETLoader" for n in workflow.values())


@pytest.mark.parametrize("mode", ["txt2img", "img2img"])
def test_turbo_uses_official_manual_sigmas(mode):
    from modules.comfyui.workflow import QWEN21_TURBO_SIGMAS

    options = {"workflow_family": "qwen21-turbo", "model": "turbo.safetensors",
               "workflow_mode": mode}
    if mode == "img2img":
        options["image"] = "input.png"
    workflow, info = ComfyUIWorkflow().createWorkflow("teapot", "", options)
    roles = {node["_meta"]["role"]: node for node in workflow.values()}
    assert info["steps"] == 8 and info["cfg_scale"] == 1
    assert roles["sigmas"]["inputs"]["sigmas"] == QWEN21_TURBO_SIGMAS
    assert roles["sampler"]["class_type"] == "SamplerCustomAdvanced"
    assert roles["noise"]["inputs"]["noise_seed"] == info["seed"]
    assert roles["guider"]["inputs"]["cfg"] == 1


def test_turbo_rejects_incompatible_step_count():
    with pytest.raises(ValueError, match="8 steps"):
        ComfyUIWorkflow().createWorkflow("test", "", {
            "workflow_family": "qwen-image-2.1-turbo", "model": "turbo.safetensors", "steps": 20,
        })


def test_neo_scheduler_script_registers_once_and_uses_fixed_sigmas(monkeypatch):
    import runpy
    import sys
    from types import SimpleNamespace
    import modules

    schedulers = SimpleNamespace(all_schedulers=[], schedulers=[], schedulers_map={},
                                 Scheduler=lambda name, label, fn: SimpleNamespace(name=name, label=label, function=fn))
    monkeypatch.setattr(modules, "sd_schedulers", schedulers, raising=False)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        float32="float32", tensor=lambda values, **kwargs: tuple(values),
    ))
    path = Path(__file__).resolve().parents[1] / "examples" / "neo-qwen21-turbo-scheduler.py"
    runpy.run_path(str(path))
    runpy.run_path(str(path))
    assert len(schedulers.schedulers) == len(schedulers.all_schedulers) == 1
    fn = schedulers.schedulers_map["qwen21_turbo"].function
    assert fn(8, 0, 1, "cpu") == (1.0, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568, 0.0)
    with pytest.raises(ValueError, match="8 steps"):
        fn(20, 0, 1, "cpu")


@pytest.mark.parametrize("minimum,valid", [(0, True), (1, False)])
def test_checker_handles_empty_v3_autogrow(minimum, valid):
    checker = WorkflowChecker()
    checker.object_info = {"object_info": {
        "TextEncodeQwenImage21": {"input": {"required": {
            "clip": ["CLIP"], "prompt": ["STRING"], "negative_prompt": ["STRING"],
            "resolution": ["INT"], "images": ["COMFY_AUTOGROW_V3", {"template": {"min": minimum}}],
        }}},
        "CLIPLoader": {"input": {"required": {}}},
        "Output": {"output_node": True, "input": {"required": {"conditioning": ["CONDITIONING"]}}},
    }}
    workflow = {
        "1": {"class_type": "CLIPLoader", "inputs": {"clip_name": "encoder", "type": "qwen_image"}},
        "2": {"class_type": "TextEncodeQwenImage21", "inputs": {
            "clip": ["1", 0], "prompt": "test", "negative_prompt": "", "resolution": 1024,
        }},
        "3": {"class_type": "Output", "inputs": {"conditioning": ["2", 0]}},
    }
    checked, _ = checker.check(workflow, "unused")
    assert (checked is not None) is valid


def test_comfy_rejects_all_invalid_workflows(monkeypatch):
    from modules.comfyui import ComufyClient

    monkeypatch.setattr(ComufyClient, "checkWorkflow", lambda *a, **k: (None, None))
    monkeypatch.setattr(ComufyClient, "run", lambda *a, **k: pytest.fail("invalid workflow submitted"))
    assert ComufyClient.txt2img([{"workflow": {"1": {"class_type": "Missing", "inputs": {}}}}]) is False


@pytest.mark.parametrize("options,expected", [
    ({"denoising_strength": 0.5}, 0.5),
    ({"nomal_denoising_strength": 0.4}, 0.4),
    ({"denoising_strength": 0.5, "nomal_denoising_strength": 0.4}, 0.5),
    ({"denoise": 0.3, "denoising_strength": 0.5}, 0.3),
    ({"denoising_strength": 0}, 0),
])
def test_comfy_img2img_preserves_denoising_strength(options, expected):
    options = dict(options, workflow_family="moss", model="moss.safetensors", image="input.png")
    spec, merged = build_comfyui_spec({"prompt": "test"}, options)
    assert spec["sampling"]["denoise"] == expected
    workflow, info = ComfyUIWorkflow().createWorkflow("test", "", options)
    sampler = next(n for n in workflow.values() if n.get("class_type") == "KSampler")
    assert sampler["inputs"]["denoise"] == expected
    assert info["denoising_strength"] == expected


def test_comfy_upload_uses_form_field_for_overwrite(monkeypatch):
    import asyncio
    import httpx
    from modules.comfyui import ComufyClient

    requests = []

    def receive(request):
        requests.append(request)
        return httpx.Response(200, json={"name": "input.png"})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda: original_client(transport=httpx.MockTransport(receive)))
    client = ComufyClient()
    result = asyncio.run(client.uploadImage("input.png", binary=b"image-bytes", overwrite=True))
    assert result["name"] == "input.png"
    body = requests[0].content
    assert b'name="overwrite"\r\n\r\ntrue' in body
    assert b'name="image"; filename="input.png"' in body
    assert b"image-bytes" in body
    assert b'filename="overwrite"' not in body

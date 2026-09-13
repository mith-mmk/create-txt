import asyncio
from pathlib import Path
from uuid import uuid4
import json
from unittest.mock import patch

from modules.comfyui import ComfyUIWorkflow
from modules.comfyui.checker import WorkflowChecker
from modules.comfyui.runner import ComufyClient
from modules.comfyui.workflow import build_comfyui_spec
from modules.save import create_files, get_variables, merge_generation_parameters


def make_test_dir(name):
    path = Path(__file__).resolve().parents[1] / "temp" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_sd15_workflow_has_expected_nodes():
    workflow, info = ComfyUIWorkflow().createWorkflow(
        "1girl", "bad", {"type": "sd15", "checkpoint": "sd15.safetensors"}
    )
    class_types = [node["class_type"] for node in workflow.values() if isinstance(node, dict)]
    assert "CheckpointLoaderSimple" in class_types
    assert "CLIPTextEncode" in class_types
    assert "EmptyLatentImage" in class_types
    assert "KSampler" in class_types
    assert info["sd_model_name"] == "sd15.safetensors"


def test_sdxl_workflow_has_expected_nodes():
    workflow, _ = ComfyUIWorkflow().createWorkflow(
        "1girl", "bad", {"type": "sdxl", "checkpoint": "sdxl.safetensors"}
    )
    class_types = [node["class_type"] for node in workflow.values() if isinstance(node, dict)]
    assert "CheckpointLoaderSimple" in class_types
    assert "CLIPTextEncodeSDXL" in class_types
    assert "KSampler" in class_types


def test_img2img_with_mask_uses_image_nodes():
    workflow, _ = ComfyUIWorkflow().createWorkflow(
        "1girl",
        "bad",
        {
            "workflow_family": "sd15",
            "workflow_mode": "img2img",
            "checkpoint": "sd15.safetensors",
            "image": "input.png",
            "mask": "mask.png",
        },
    )
    class_types = [node["class_type"] for node in workflow.values() if isinstance(node, dict)]
    assert "LoadImage" in class_types
    assert "VAEEncode" in class_types
    assert "LoadImageMask" in class_types
    assert "SetLatentNoiseMask" in class_types


def test_flux_family_uses_customizable_nodes():
    workflow, _ = ComfyUIWorkflow().createWorkflow(
        "test",
        "",
        {
            "workflow_family": "flux",
            "checkpoint": "flux1-dev.safetensors",
            "nodes": {
                "model_adapter": {"class_type": "ModelSamplingAuraFlow"},
                "clip_loader": {
                    "class_type": "CLIPLoader",
                    "inputs": {"clip_name": "clip_l.safetensors", "type": "flux"},
                },
            },
        },
    )
    class_types = [node["class_type"] for node in workflow.values() if isinstance(node, dict)]
    assert "UNETLoader" in class_types
    assert "ModelSamplingAuraFlow" in class_types
    assert "CLIPLoader" in class_types


def test_flux_text_encoder_option_selects_clip_file():
    workflow, _ = ComfyUIWorkflow().createWorkflow(
        "test",
        "",
        {
            "workflow_family": "flux",
            "checkpoint": "flux1-dev.safetensors",
            "text_encoder": "qwen_3_4b.safetensors",
        },
    )
    clip_nodes = [
        node for node in workflow.values()
        if isinstance(node, dict) and node.get("class_type") == "CLIPLoader"
    ]
    assert clip_nodes[0]["inputs"]["clip_name"] == "qwen_3_4b.safetensors"


def test_automatic_text_encoder_keeps_flux_default():
    workflow, _ = ComfyUIWorkflow().createWorkflow(
        "test", "", {"workflow_family": "flux", "checkpoint": "flux1-dev.safetensors"}
    )
    clip_nodes = [
        node for node in workflow.values()
        if isinstance(node, dict) and node.get("class_type") == "CLIPLoader"
    ]
    assert clip_nodes[0]["inputs"]["clip_name"] == "clip_l.safetensors"


def test_template_controlnet_injection():
    template = {
        "10": {"class_type": "LoadImage", "inputs": {"image": "old.png"}},
        "_controlnet_slots": {"0": {"node_id": "10", "field": "image"}},
    }
    workflow, _ = ComfyUIWorkflow().createWorkflowFromSpec(
        {
            "family": "anima",
            "mode": "txt2img",
            "model": "anima.safetensors",
            "template": template,
            "controlnet": [{"image": "new.png"}],
        }
    )
    assert workflow["10"]["inputs"]["image"] == "new.png"


def test_build_comfyui_spec_from_prompt_item():
    spec, merged = build_comfyui_spec(
        {
            "prompt": "1girl",
            "negative_prompt": "bad",
            "comfyui": {"family": "flux", "nodes": {"sampler": {"class_type": "KSampler"}}},
        },
        {"sd_model": "flux.safetensors"},
    )
    assert spec["family"] == "flux"
    assert spec["model"] == "flux.safetensors"
    assert spec["nodes"]["sampler"]["class_type"] == "KSampler"


def test_build_comfyui_spec_carries_width_and_height():
    spec, _ = build_comfyui_spec(
        {
            "prompt": "1girl",
            "negative_prompt": "bad",
            "width": 832,
            "height": 1216,
        },
        {"sd_model": "sdxl.safetensors"},
    )
    assert spec["width"] == 832
    assert spec["height"] == 1216


def test_wrapped_native_workflow_payload_is_treated_as_workflow_mode():
    payload = {
        "workflow": {
            "1": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
            "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
        }
    }

    with patch.object(ComufyClient, "checkWorkflow", return_value=(payload["workflow"], {})) as check_mock:
        with patch.object(ComufyClient, "run", return_value=None) as run_mock:
            result = ComufyClient.txt2img([payload], options={})

    assert result is True
    check_mock.assert_called_once()
    run_mock.assert_called_once()


def test_checker_ignores_disconnected_invalid_nodes():
    checker = WorkflowChecker()
    checker.object_info = {
        "object_info": {
            "CheckpointLoaderSimple": {
                "input": {"required": {"ckpt_name": [["model.safetensors"]]}}
            },
            "CLIPTextEncode": {"input": {"required": {"text": ["STRING"], "clip": ["CLIP"]}}},
            "KSampler": {
                "input": {
                    "required": {
                        "seed": ["INT"],
                        "steps": ["INT"],
                        "cfg": ["FLOAT"],
                        "sampler_name": [["euler"]],
                        "scheduler": [["normal"]],
                        "denoise": ["FLOAT"],
                        "model": ["MODEL"],
                        "positive": ["CONDITIONING"],
                        "negative": ["CONDITIONING"],
                        "latent_image": ["LATENT"],
                    }
                }
            },
            "EmptyLatentImage": {
                "input": {"required": {"width": ["INT"], "height": ["INT"], "batch_size": ["INT"]}}
            },
            "VAEDecode": {"input": {"required": {"samples": ["LATENT"], "vae": ["VAE"]}}},
            "SaveImage": {"input": {"required": {"images": ["IMAGE"]}}, "output_node": True},
        }
    }
    workflow = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "ok", "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "ng", "clip": ["1", 1]}},
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 1,
                "steps": 20,
                "cfg": 7,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0]}},
        "99": {"class_type": "CLIPTextEncode", "inputs": {"text": "orphan without clip"}},
    }

    checked, info = checker.check(workflow, "http://127.0.0.1:8188")

    assert checked is not None
    assert info["steps"] == 20


def test_checker_reports_missing_required_input_details():
    checker = WorkflowChecker()
    checker.object_info = {
        "object_info": {
            "CLIPTextEncode": {"input": {"required": {"text": ["STRING"], "clip": ["CLIP"]}}},
            "SaveImage": {"input": {"required": {"images": ["IMAGE"]}}, "output_node": True},
        }
    }
    workflow = {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "missing clip"}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }

    with patch("modules.comfyui.checker.printError") as error_mock:
        checked, info = checker.check(workflow, "http://127.0.0.1:8188")

    assert checked is None
    assert info is None
    messages = [call.args[0] for call in error_mock.call_args_list]
    assert any("node=1" in msg and "class=CLIPTextEncode" in msg and "required input 'clip' not found" in msg for msg in messages)
    assert messages[-1] == "Workflow is invalid"


def test_checker_reports_missing_linked_node_details():
    checker = WorkflowChecker()
    checker.object_info = {
        "object_info": {
            "SaveImage": {"input": {"required": {"images": ["IMAGE"]}}, "output_node": True},
        }
    }
    workflow = {
        "2": {"class_type": "SaveImage", "inputs": {"images": ["404", 0]}},
    }

    with patch("modules.comfyui.checker.printError") as error_mock:
        checked, info = checker.check(workflow, "http://127.0.0.1:8188")

    assert checked is None
    assert info is None
    messages = [call.args[0] for call in error_mock.call_args_list]
    assert any("node=2" in msg and "linked node 404 not found" in msg for msg in messages)
    assert messages[-1] == "Workflow is invalid"


def test_checker_restores_backslash_escaped_model_name():
    checker = WorkflowChecker()
    checker.object_info = {
        "object_info": {
            "CheckpointLoaderSimple": {
                "input": {"required": {"ckpt_name": [["il_=il\\flux.safetensors"]]}}
            },
            "SaveImage": {"input": {"required": {"images": ["IMAGE"]}}, "output_node": True},
        }
    }
    workflow = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "il_=il\flux.safetensors"},
        },
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }

    checked, info = checker.check(workflow, "http://127.0.0.1:8188")

    assert checked is not None
    assert checked["1"]["inputs"]["ckpt_name"] == r"il_=il\flux.safetensors"
    assert info["sd_model_name"] == r"il_=il\flux.safetensors"


def test_checker_normalizes_legacy_sampler_name():
    checker = WorkflowChecker()
    checker.object_info = {
        "object_info": {
            "KSampler": {
                "input": {
                    "required": {
                        "seed": ["INT"],
                        "steps": ["INT"],
                        "cfg": ["FLOAT"],
                        "sampler_name": [["euler", "euler_ancestral", "dpmpp_2m_sde"]],
                        "scheduler": [["normal"]],
                        "denoise": ["FLOAT"],
                        "model": ["MODEL"],
                        "positive": ["CONDITIONING"],
                        "negative": ["CONDITIONING"],
                        "latent_image": ["LATENT"],
                    }
                }
            },
            "SaveImage": {"input": {"required": {"images": ["IMAGE"]}}, "output_node": True},
        }
    }
    workflow = {
        "1": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 1,
                "steps": 20,
                "cfg": 7,
                "sampler_name": "Euler a",
                "scheduler": "normal",
                "denoise": 1,
                "model": ["2", 0],
                "positive": ["2", 0],
                "negative": ["2", 0],
                "latent_image": ["2", 0],
            },
        },
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }

    checked, info = checker.check(workflow, "http://127.0.0.1:8188")

    assert checked is not None
    assert checked["1"]["inputs"]["sampler_name"] == "euler_ancestral"
    assert info["sampler_name"] == "euler_ancestral"
    assert checked["1"]["inputs"]["scheduler"] == "normal"
    assert info["scheduler"] == "normal"


def test_checker_normalizes_legacy_sampler_and_scheduler_pair():
    checker = WorkflowChecker()
    checker.object_info = {
        "object_info": {
            "KSampler": {
                "input": {
                    "required": {
                        "seed": ["INT"],
                        "steps": ["INT"],
                        "cfg": ["FLOAT"],
                        "sampler_name": [["dpmpp_2m", "dpmpp_sde", "dpmpp_2m_sde"]],
                        "scheduler": [["normal", "karras"]],
                        "denoise": ["FLOAT"],
                        "model": ["MODEL"],
                        "positive": ["CONDITIONING"],
                        "negative": ["CONDITIONING"],
                        "latent_image": ["LATENT"],
                    }
                }
            },
            "SaveImage": {"input": {"required": {"images": ["IMAGE"]}}, "output_node": True},
        }
    }
    workflow = {
        "1": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 1,
                "steps": 20,
                "cfg": 7,
                "sampler_name": "DPM++ SDE",
                "scheduler": "normal",
                "denoise": 1,
                "model": ["2", 0],
                "positive": ["2", 0],
                "negative": ["2", 0],
                "latent_image": ["2", 0],
            },
        },
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }

    checked, info = checker.check(workflow, "http://127.0.0.1:8188")

    assert checked is not None
    assert checked["1"]["inputs"]["sampler_name"] == "dpmpp_sde"
    assert checked["1"]["inputs"]["scheduler"] == "karras"
    assert info["sampler_name"] == "dpmpp_sde"
    assert info["scheduler"] == "karras"


def test_comfyui_image_wrapper_preserves_direct_info_parameters():
    client = ComufyClient()
    wrapped, _ = asyncio.run(
        client.imageWrapper(
            [],
            {"prompt": "raw"},
            {},
            {
                "prompt": "1girl",
                "negative_prompt": "bad",
                "seed": 12345,
                "width": 512,
                "height": 768,
            },
        )
    )

    assert wrapped["parameters"]["seed"] == 12345
    assert wrapped["parameters"]["width"] == 512
    assert wrapped["parameters"]["height"] == 768
    infotext = wrapped["info"]["infotexts"][0]
    assert "Seed: 12345" in infotext
    assert "Size: 512x768" in infotext


def test_comfyui_image_wrapper_preserves_model_metadata_fields():
    client = ComufyClient()
    wrapped, _ = asyncio.run(
        client.imageWrapper(
            [],
            {"prompt": "raw"},
            {},
            {
                "prompt": "1girl",
                "negative_prompt": "bad",
                "seed": 271760848,
                "steps": 28,
                "sampler_name": "euler_ancestral",
                "cfg_scale": 6.5,
                "sd_model_name": "model.safetensors",
            },
        )
    )

    infotext = wrapped["info"]["infotexts"][0]
    assert "Steps: 28" in infotext
    assert "Sampler: euler_ancestral" in infotext
    assert "CFG scale: 6.5" in infotext
    assert "Seed: 271760848" in infotext
    assert "Model: model.safetensors" in infotext


def test_comfyui_build_save_options_preserves_verbose_variables():
    save_options = ComufyClient.build_save_options(
        {"dir": "outputs"},
        {
            "verbose": {
                "values": {"character": "alice"},
                "attributes": {"character": {"costume": "uniform"}},
            },
            "filepart": "scene01",
            "info": {"episode": "01"},
            "command": {"cfg_scale": 7},
        },
    )

    variables = get_variables(save_options)

    assert variables["character"] == "alice"
    assert save_options["filepart"] == "scene01"
    assert save_options["info"]["episode"] == "01"
    assert save_options["command"]["cfg_scale"] == 7


def test_comfyui_create_files_restores_var_filename_replacers_from_verbose():
    save_options = ComufyClient.build_save_options(
        {"dir": "outputs", "filename_pattern": "[var:character]-[var:character:costume]"},
        {
            "verbose": {
                "values": {"character": "alice"},
                "attributes": {"character": {"costume": "uniform"}},
            }
        },
    )

    filename_pattern, need_names, _, nameseed = asyncio.run(
        create_files({"info": {"infotexts": [""]}, "images": []}, save_options)
    )

    assert nameseed == "[var:character]-[var:character:costume]"
    assert need_names == ["var:character", "var:character:costume"]
    assert filename_pattern["var:character"] == "alice"
    assert filename_pattern["var:character:costume"] == "uniform"


def test_merge_generation_parameters_prefers_direct_info_for_seed():
    params = merge_generation_parameters(
        "1girl\nNegative prompt: bad\n",
        {"seed": 12345, "width": 512, "height": 768},
    )

    assert params["seed"] == 12345
    assert params["width"] == 512
    assert params["height"] == 768


def test_checker_collects_lora_alias_and_resolves_similar_name():
    checker = WorkflowChecker()
    checker.object_info = {
        "object_info": {
            "LoraLoader": {
                "input": {
                    "required": {
                        "lora_name": [["artist\\real.safetensors"]],
                        "strength_model": ["FLOAT"],
                        "strength_clip": ["FLOAT"],
                        "model": ["MODEL"],
                        "clip": ["CLIP"],
                    }
                }
            },
            "SaveImage": {"input": {"required": {"images": ["IMAGE"]}}, "output_node": True},
        }
    }
    workflow = {
        "1": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": "real.safetensors",
                "strength_model": 1.0,
                "strength_clip": 1.0,
                "model": ["2", 0],
                "clip": ["2", 1],
            },
        },
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }

    checked, info = checker.check(workflow, "http://127.0.0.1:8188")

    assert checked is not None
    assert checked["1"]["inputs"]["lora_name"] == "artist\\real.safetensors"
    assert info["loras"] == ["artist\\real.safetensors"]
    assert info["lora"] == ["artist\\real.safetensors"]

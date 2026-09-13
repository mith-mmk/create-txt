from types import SimpleNamespace

from PIL import Image

import create_prompts


def test_legacy_img2img_forwards_text_encoder_and_canonical_modules(tmp_path, monkeypatch):
    image = tmp_path / "input.png"
    Image.new("RGB", (8, 8), "white").save(image)
    captured = {}
    monkeypatch.setattr(
        create_prompts.api,
        "set_sd_model",
        lambda **kwargs: captured.setdefault("model", kwargs) or True,
    )
    monkeypatch.setattr(
        create_prompts,
        "img2img",
        lambda files, **kwargs: captured.setdefault("generation", kwargs) or [],
    )
    args = SimpleNamespace(
        input=str(image), api_set_sd_model="model.safetensors", api_set_sd_vae="Automatic",
        text_encoder="clip.safetensors", override=None, api_base="http://localhost:7860",
        api_output_dir=str(tmp_path / "out"), alt_image_dir=None, interrogate=None,
        filename_pattern=None, api_filename_variables=False, mask_dir=None,
        userpass=None, num_once=False, num_length=None,
    )
    assert create_prompts.img2img_from_args(args) is True
    assert captured["model"]["text_encoder"] == "clip.safetensors"
    assert captured["generation"]["opt"]["vae"] == "Automatic"
    assert captured["generation"]["opt"]["text_encoder"] == "clip.safetensors"

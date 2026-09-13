"""
modules/tools/txt2img.py — DSL txt2img コマンドの実装
cp2.main() を直接呼び出して prompt 生成 + API 送信を行う。
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING, Any

import modules.api as api
import modules.logger as logger
import modules.share as share
from modules.tools.model_selector import random_model

if TYPE_CHECKING:
    from modules.tools.context import RunnerContext

Logger = logger.getDefaultLogger()


def run(profile_name: str, context: "RunnerContext") -> bool:
    """
    DSL コマンド: txt2img <profile_name>
    context.config["profiles"]["txt2img"][profile_name] の設定で生成を実行する。
    """
    profile = context.get_profile("txt2img", profile_name)
    if not profile:
        Logger.error(f"[txt2img] profile not found: {profile_name}")
        return False

    host = context.effective_host()
    dry_run = context.dry_run

    # --- モデル選択 ---
    model_source = profile.get("models") or profile.get("models_file")
    raw_profile_options = profile.get("options", {})
    profile_options = raw_profile_options if isinstance(raw_profile_options, dict) else {}
    model = profile.get("model") or profile_options.get("model", profile_options.get("sd_model"))
    if model_source and profile.get("random_model", True):
        abort_matrix = context.config.get("abort_matrix") or profile.get("abort_matrix")
        genre = profile.get("genre") or context.get_var("genre")
        model = random_model(
            model_source, context, abort_matrix=abort_matrix, genre=genre
        )
        if model:
            Logger.info(f"[txt2img] set model: {model}")

    # --- cp2.main() を呼び出す ---
    try:
        import cp2
    except ImportError:
        Logger.error("[txt2img] cp2.py が見つかりません")
        return False

    opt = _build_cp2_namespace(profile, host, context)
    opt.api_set_sd_model = model
    Logger.info(f"[txt2img] running cp2.main(input={opt.input}, profile={opt.profile})")

    if dry_run:
        Logger.info("[txt2img] dry_run: skip cp2.main()")
        return True

    try:
        return bool(cp2.main(opt))
    except Exception as e:
        Logger.error(f"[txt2img] cp2.main() error: {e}")
        return False


# ---------------------------------------------------------------------------
# cp2 用 argparse.Namespace 生成
# ---------------------------------------------------------------------------


def _build_cp2_namespace(
    profile: dict[str, Any], host: str, context: "RunnerContext"
) -> argparse.Namespace:
    """
    cp2.py の argparse 引数に相当する Namespace を辞書から組み立てる。
    profile キーと cp2 引数名の対応を吸収する。
    """
    opt_map = profile.get("options", {})
    if not isinstance(opt_map, dict):
        opt_map = {}
    vae = opt_map.get("vae", opt_map.get("sd_vae", profile.get("vae", "Automatic")))
    text_encoder = opt_map.get("text_encoder", profile.get("text_encoder", "Automatic"))

    return argparse.Namespace(
        input=profile.get("input"),
        api_mode=(context.server_type != "comfyui"),
        api_base=host,
        api_output_dir=profile.get("output", "./outputs"),
        api_input_json=profile.get("input_json"),
        api_filename_pattern=opt_map.get("filename_pattern")
        or profile.get("filename_pattern"),
        max_number=profile.get("number", -1),
        api_set_sd_model=None,  # run() supplies the selected model before profile resolution.
        api_set_sd_vae=vae,
        text_encoder=text_encoder,
        model_type=profile.get("model_type") or opt_map.get("model_type"),
        ui_type=profile.get("ui_type") or opt_map.get("ui_type"),
        image=profile.get("image") or opt_map.get("image"),
        mask=profile.get("mask") or opt_map.get("mask"),
        reference_images=profile.get("reference_images") or opt_map.get("reference_images"),
        reference_max_size=profile.get("reference_max_size", opt_map.get("reference_max_size")),
        api_type=profile.get("api_type", "txt2img"),
        override=profile.get("override"),
        profile=profile.get("profile"),
        values=profile.get("values"),
        api_comfy=(context.server_type == "comfyui"),
        api_comfy_save=profile.get("comfy_save", "save"),
        json_verbose=False,
        v1json=False,
        save_extend_meta=profile.get("save_extend_meta", False),
        image_type=opt_map.get("image_type") or profile.get("image_type", "png"),
        num_length=profile.get("num_length"),
        cn_images_dir=profile.get("cn_images_dir"),
    )

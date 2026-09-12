"""
modules/tools/comfyui.py — DSL workflow コマンドの実装

2 つの実行パスを持つ:

  [Path A] YAML input あり（input: prompts/v2/xxx.yaml）
    → cp2.main(api_comfy=True) 経由で create_text_v2() を呼んでプロンプト生成
    → ComufyClient.txt2img(output_text) へ
    ※ YAML の command: にワークフロー JSON パスを書くのが標準使い方

  [Path B] workflow: JSON ファイル直指定（input なし）
    → JSON を直接読み込み、${var} 展開 + overrides 適用
    → ComufyClient.txt2img([workflow]) へ
    ※ プロンプト生成不要な場合の生 JSON 投入
"""

from __future__ import annotations

import argparse
import json
import os
import re
from typing import TYPE_CHECKING, Any

import yaml

import modules.logger as logger

if TYPE_CHECKING:
    from modules.tools.context import RunnerContext

Logger = logger.getDefaultLogger()


# ---------------------------------------------------------------------------
# DSL エントリーポイント
# ---------------------------------------------------------------------------


def run_workflow(
    workflow_or_profile: str,
    context: "RunnerContext",
    extra_args: list[str] | None = None,
) -> bool:
    """
    DSL コマンド: workflow <file_or_profile> [args...]

    workflow_or_profile:
      - config.profiles.comfyui[name] のプロファイル名
      - JSON ファイルパス（直接指定・Path B のみ）

    extra_args: key=value 形式のオーバーライド引数（Path B の overrides に追加）
    """
    profile = context.get_profile("comfyui", workflow_or_profile)

    if profile:
        # --- Path A: YAML input がある場合は cp2.main() を通す ---
        if profile.get("input"):
            return _run_via_cp2(profile, context, extra_args)

        # --- Path B: workflow JSON 直指定 ---
        workflow_file = profile.get("workflow", "")
        output_dir = profile.get("output", "./outputs")
        overrides = dict(profile.get("overrides", {}))
        opt_profile = dict(profile.get("options", {}))
        opt_profile.setdefault("image_type", profile.get("image_type", "png"))
        opt_profile.setdefault("comfy_save", profile.get("comfy_save", "save"))

    elif os.path.isfile(workflow_or_profile):
        # --- Path B: ファイルパス直指定 ---
        workflow_file = workflow_or_profile
        output_dir = "./outputs"
        overrides = {}
        opt_profile = {}

    else:
        Logger.error(f"[comfyui] workflow not found: {workflow_or_profile}")
        return False

    # extra_args で overrides を上書き
    if extra_args:
        for a in extra_args:
            if "=" in a:
                k, v = a.split("=", 1)
                overrides[k.strip()] = v.strip()

    if not os.path.isfile(workflow_file):
        Logger.error(f"[comfyui] workflow file not found: {workflow_file}")
        return False

    with open(workflow_file, encoding="utf-8") as f:
        if workflow_file.endswith(".yaml") or workflow_file.endswith(".yml"):
            workflow = yaml.safe_load(f) or {}
        else:
            workflow = json.load(f)

    workflow = _apply_overrides(workflow, overrides, context)

    if context.dry_run:
        Logger.info("[comfyui] dry_run: skip ComufyClient.txt2img()")
        return True

    hostname = context.effective_host("comfyui")
    save_image = _resolve_save_image(opt_profile.get("comfy_save", "save"))
    opt_profile["save_image"] = save_image

    try:
        from modules.comfyui import ComufyClient

        payload = workflow
        if "family" in workflow or "mode" in workflow or "nodes" in workflow:
            payload = {"comfyui": workflow}

        ComufyClient.txt2img(
            prompts=[payload],
            hostname=hostname,
            output_dir=output_dir,
            options=opt_profile,
        )
        return True
    except Exception as e:
        Logger.error(f"[comfyui] error: {e}")
        return False


# ---------------------------------------------------------------------------
# Path A: cp2.main() 経由（create_text_v2 → ComufyClient）
# ---------------------------------------------------------------------------


def _run_via_cp2(
    profile: dict,
    context: "RunnerContext",
    extra_args: list[str] | None = None,
) -> bool:
    """
    YAML input を create_text_v2() で処理してから ComfyUI に送る。
    cp2.main(api_comfy=True) を呼ぶことで cp2.py と同じフローを踏む。
    """
    try:
        import cp2
    except ImportError:
        Logger.error("[comfyui] cp2.py が見つかりません")
        return False

    hostname = context.effective_host("comfyui")
    ns = _build_cp2_namespace(profile, hostname, context, extra_args)

    Logger.info(
        f"[comfyui] running cp2.main(input={ns.input}, profile={ns.profile},"
        f" api_comfy=True)"
    )

    if context.dry_run:
        Logger.info("[comfyui] dry_run: skip cp2.main()")
        return True

    try:
        result = cp2.main(ns)
        return bool(result)
    except Exception as e:
        Logger.error(f"[comfyui] cp2.main() error: {e}")
        return False


def _build_cp2_namespace(
    profile: dict,
    hostname: str,
    context: "RunnerContext",
    extra_args: list[str] | None = None,
) -> argparse.Namespace:
    """
    cp2.main() が必要とする argparse.Namespace を組み立てる。
    ComfyUI 用なので api_comfy=True, api_mode=False。
    """
    opt_map = profile.get("options", {})

    # extra_args の key=value を values に追加
    extra_values: dict = {}
    if extra_args:
        for a in extra_args:
            if "=" in a:
                k, v = a.split("=", 1)
                extra_values[k.strip()] = v.strip()

    # profile の values と extra_values をマージ
    values = profile.get("values")
    if extra_values:
        if isinstance(values, dict):
            values = {**values, **extra_values}
        else:
            values = extra_values

    # api_comfy_save → save_image の変換は cp2.main() が行う
    comfy_save = opt_map.get("comfy_save") or profile.get("comfy_save", "save")

    return argparse.Namespace(
        # 必須
        input=profile.get("input"),
        api_comfy=True,
        api_mode=False,
        api_type="txt2img",
        api_base=hostname,
        api_output_dir=profile.get("output", "./outputs"),
        api_comfy_save=comfy_save,
        # プロンプト生成
        profile=profile.get("profile"),
        values=values,
        max_number=profile.get("number", -1),
        override=profile.get("override"),
        # ファイル名
        api_filename_pattern=opt_map.get("filename_pattern")
        or profile.get("filename_pattern"),
        api_filname_pattern=None,  # cp2.py のタイポを吸収
        num_length=profile.get("num_length"),
        num_once=False,
        # 保存オプション
        image_type=opt_map.get("image_type") or profile.get("image_type", "png"),
        image_quality=profile.get("image_quality", 80),
        save_extend_meta=profile.get("save_extend_meta", False),
        escape_filename=profile.get("escape_filename", False),
        # モデル（モデル切り替えは呼び出し元で設定済みのため None）
        api_set_sd_model=profile.get("model"),
        api_set_sd_vae=profile.get("vae", "Automatic"),
        model_type=profile.get("model_type") or opt_map.get("model_type"),
        ui_type=profile.get("ui_type") or opt_map.get("ui_type", "comfy"),
        # ControlNet
        cn_images_dir=profile.get("cn_images_dir"),
        cn_save_pre=profile.get("cn_save_pre", False),
        # 未使用だが cp2.main() が参照する可能性のあるフィールド
        api_input_json=None,
        api_userpass=None,
        info=None,
        v1json=False,
        json_verbose=False,
        json_escape=False,
        verbose=False,
        debug=False,
        prompt=False,
    )


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------


def _resolve_save_image(comfy_save: str) -> list[str]:
    """comfy_save 文字列を save_image リストに変換する（cp2.py と同ロジック）。"""
    mode = comfy_save.lower()
    if mode == "save":
        return ["websocket"]
    elif mode == "both":
        return ["ui", "save"]
    elif mode == "ui":
        return ["ui"]
    else:
        Logger.warning(
            f"[comfyui] unknown comfy_save value '{comfy_save}', using 'save'"
        )
        return ["websocket"]


# ---------------------------------------------------------------------------
# 内部: ${var} 展開 + overrides 適用
# ---------------------------------------------------------------------------

_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _expand_vars(value: str, context: "RunnerContext") -> str:
    """文字列中の ${var} を context.variables で置換する。"""

    def replacer(m: re.Match) -> str:
        key = m.group(1).strip()
        v = context.get_var(key)
        return str(v) if v is not None else m.group(0)

    return _VAR_PATTERN.sub(replacer, value)


def _apply_overrides(workflow: Any, overrides: dict, context: "RunnerContext") -> Any:
    """
    ワークフロー JSON を再帰的に走査して:
    1. 文字列値を ${var} 展開する
    2. overrides の "node_id.field" または "field" 形式でノード値を上書きする

    overrides の例:
      "6.text": "1girl, ..."   → ノード ID 6 の inputs.text を書き換え
      "positive": "1girl, ..."  → inputs.text に "positive" を含むノードを書き換え
    """
    # まず ${var} 展開
    workflow = _walk_expand(workflow, context)

    # overrides 適用
    for key, val in overrides.items():
        if isinstance(val, str):
            val = _expand_vars(val, context)
        _apply_override(workflow, key, val)

    return workflow


def _walk_expand(obj: Any, context: "RunnerContext") -> Any:
    if isinstance(obj, str):
        return _expand_vars(obj, context)
    if isinstance(obj, dict):
        return {k: _walk_expand(v, context) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_expand(v, context) for v in obj]
    return obj


def _apply_override(workflow: dict, key: str, value: Any) -> None:
    """
    key が "node_id.field" 形式 → 直接書き換え
    key が "field" のみ → 全ノードを走査して inputs[field] を書き換え
    """
    if "." in key:
        node_id, field = key.split(".", 1)
        node = workflow.get(node_id) or workflow.get(str(node_id))
        if node and "inputs" in node:
            node["inputs"][field] = value
    else:
        for node in workflow.values():
            if isinstance(node, dict) and "inputs" in node:
                if key in node["inputs"]:
                    node["inputs"][key] = value

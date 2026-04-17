"""
runner.py — YAML ベース疑似プログラムのエントリーポイント

使い方:
  python runner.py [config.yaml] [options]

オプション:
  config.yaml            設定ファイルパス（省略時: prompts/runner.yaml）
  --script FILE, -s FILE 外部スクリプトファイル（設定の script: を上書き）
  --host HOST, -H HOST   API ホスト URL（設定の host: を上書き）
  --dry-run, -n          API 呼び出しをスキップ（テスト実行）
  --profile NAME, -p NAME profiles セクションのデフォルトプロファイル
  --loop, -l             スクリプト終了後に再度実行（無限ループ）
  --version              バージョン表示

設定ファイル（YAML version: 3）:
  host: http://localhost:7860
  comfyui_host: http://localhost:8188   # 省略可
  log:
    path: ./log/runner.log
    level: info
    days: 7
  profiles:
    txt2img:
      sdxl:
        input: prompts/v2/prompts-v2-xl.yaml
        models: [checkpoint.safetensors]
        output: ./outputs/
    img2img: ...
    comfyui: ...
    img2txt2img: ...
  script: |
    LOOP -1
      PING
      CHECKSERVER
      SET server = EXITCODE
      IF server == "comfyui"
        HOST http://localhost:8188
      ENDIF
      CHECK 07:00-18:30
      txt2img nsfw
      SLEEP 5
    ENDLOOP
"""

from __future__ import annotations

import argparse
import os
import sys

import yaml

import modules.logger as logger
import modules.share as share

VERSION = "3.0.0"
DEFAULT_CONFIG = "prompts/runner.yaml"


# ---------------------------------------------------------------------------
# エントリーポイント
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"runner.py v{VERSION}")
        return 0

    try:
        # --- 設定ファイルロード ---
        config_path = args.config or DEFAULT_CONFIG
        config = _load_config(config_path)

        if not config:
            print(
                f"[runner] 設定ファイルが見つかりません: {config_path}", file=sys.stderr
            )
            return 1

        # --- ロガー初期化 ---
        log_cfg = config.get("log", {})
        _setup_logger(log_cfg)
        Logger = logger.getDefaultLogger()
        Logger.info(f"[runner] start  config={config_path}  v{VERSION}")

        # --- share にグローバル状態を登録（plugins との互換性） ---
        share.set("config", config)

        # --- RunnerContext 生成 ---
        from modules.tools.context import RunnerContext

        host = args.host or config.get("host", "http://localhost:7860")
        ctx = RunnerContext(config=config, host=host)
        ctx.dry_run = args.dry_run
        if config.get("comfyui_host"):
            ctx.comfyui_host = config["comfyui_host"]

        # --- スクリプト取得 ---
        script = _load_script(args, config)
        if not script:
            Logger.error(
                "[runner] 実行するスクリプトが見つかりません (script: キーまたは --script を指定してください)"
            )
            return 1

        # --- DSL 実行 ---
        from modules.tools.dsl import DSLInterpreter, ExitException

        dsl = DSLInterpreter(ctx)

        def _run_once() -> None:
            try:
                dsl.run(script)
            except ExitException:
                Logger.info("[runner] EXIT")
                raise
            except KeyboardInterrupt:
                Logger.info("[runner] interrupted")
                raise

        if args.loop:
            Logger.info("[runner] --loop mode: run indefinitely")
            while True:
                try:
                    _run_once()
                except ExitException:
                    break
                except KeyboardInterrupt:
                    break
        else:
            try:
                _run_once()
            except (ExitException, KeyboardInterrupt):
                pass

        Logger.info("[runner] done")
        return 0
    finally:
        _cleanup_runtime()


# ---------------------------------------------------------------------------
# CLI パーサー
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="runner.py",
        description="YAML ベース疑似プログラムランナー (v3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "config",
        nargs="?",
        default=None,
        metavar="CONFIG",
        help=f"設定 YAML ファイル (default: {DEFAULT_CONFIG})",
    )
    p.add_argument(
        "--script",
        "-s",
        default=None,
        metavar="FILE",
        help="外部スクリプトファイル (設定の script: を上書き)",
    )
    p.add_argument("--host", "-H", default=None, metavar="URL", help="API ホスト URL")
    p.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="API 呼び出しをスキップ（テスト実行）",
    )
    p.add_argument(
        "--loop",
        "-l",
        action="store_true",
        help="スクリプト終了後に再実行（無限ループ）",
    )
    p.add_argument(
        "--profile", "-p", default=None, metavar="NAME", help="デフォルトプロファイル名"
    )
    p.add_argument("--version", action="store_true", help="バージョンを表示して終了")
    return p


# ---------------------------------------------------------------------------
# 設定ロード
# ---------------------------------------------------------------------------


def _load_config(config_path: str) -> dict:
    if not os.path.isfile(config_path):
        return {}
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_script(args: argparse.Namespace, config: dict) -> str | list | None:
    """--script ファイル > config の script_file: > config の script: の順で取得する。"""
    # --script FILE
    if args.script:
        if not os.path.isfile(args.script):
            print(f"[runner] script file not found: {args.script}", file=sys.stderr)
            return None
        with open(args.script, encoding="utf-8") as f:
            return f.read()

    # config の script_file:
    script_file = config.get("script_file")
    if script_file:
        if not os.path.isfile(script_file):
            print(f"[runner] script_file not found: {script_file}", file=sys.stderr)
            return None
        with open(script_file, encoding="utf-8") as f:
            return f.read()

    # config の script:（文字列またはリスト）
    return config.get("script")


# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------


def _setup_logger(log_cfg: dict) -> None:
    log_path = log_cfg.get("path", "")
    if log_path:
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    level = log_cfg.get("level", "info")
    days = log_cfg.get("days", 7)
    print_levels = log_cfg.get("print_levels", ["info", "warning", "error", "critical"])

    log = logger.getDefaultLogger()
    try:
        log.setConfig(
            log_dir=log_path or None,  # type: ignore
            print_levels=print_levels,
            logging_level=level,
            log_days=days,
        )
    except Exception:
        pass  # ロガー設定失敗は無視して続行


def _cleanup_runtime() -> None:
    """終了時の後始末。HTTP クライアントとロガーのハンドルを閉じる。"""
    try:
        import modules.api as api

        api.shutdown()
    except Exception:
        pass

    try:
        logger.closeAllLoggers()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# スクリプト起動
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())

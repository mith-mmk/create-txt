"""
RunnerContext — DSL実行コンテキスト
スクリプト実行中の状態（変数・設定・ホスト等）を保持する。
"""

from __future__ import annotations

from typing import Any


class RunnerContext:
    """DSL インタープリタが共有するランタイム状態。"""

    def __init__(self, config: dict | None = None, host: str = "http://localhost:7860"):
        # YAMLから読んだ全設定（profiles を含む）
        self.config: dict = config or {}
        # API ホスト URL（HOST コマンドで変更可能）
        self.host: str = host
        # comfyui 専用ホスト（未設定なら host を流用）
        self.comfyui_host: str = config.get("comfyui_host", "") if config else ""
        # 直前コマンドの戻り値（EXITCODE 変数）
        self.exitcode: Any = None
        # CHECKSERVER で検出したサーバー種別
        self.server_type: str = ""
        # ドライランモード（API 呼び出しをスキップ）
        self.dry_run: bool = False
        # ユーザー変数ストア（SET コマンドで書き込み）
        self.variables: dict[str, Any] = {}
        # ログレベルなど実行オプション
        self.options: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 変数アクセス
    # ------------------------------------------------------------------

    def set_var(self, name: str, value: Any) -> None:
        """変数を設定する。"""
        self.variables[name] = value
        # EXITCODE を特別扱い
        if name.upper() == "EXITCODE":
            self.exitcode = value

    def get_var(self, name: str, default: Any = None) -> Any:
        """変数を取得する。大文字小文字区別なし検索。"""
        # 大文字完全一致を優先
        if name in self.variables:
            return self.variables[name]
        # 大文字小文字を無視して検索
        lower = name.lower()
        for k, v in self.variables.items():
            if k.lower() == lower:
                return v
        return default

    # ------------------------------------------------------------------
    # プロファイル取得
    # ------------------------------------------------------------------

    def get_profile(self, category: str, name: str) -> dict:
        """config["profiles"][category][name] を返す。なければ空dict。"""
        return self.config.get("profiles", {}).get(category, {}).get(name, {})

    # ------------------------------------------------------------------
    # ホスト解決
    # ------------------------------------------------------------------

    def effective_host(self, server_type: str | None = None) -> str:
        """server_type (comfyui / a1111 / forge) に応じたホストを返す。"""
        stype = server_type or self.server_type
        if stype == "comfyui" and self.comfyui_host:
            return self.comfyui_host.rstrip("/")
        return self.host.rstrip("/")

    # ------------------------------------------------------------------
    # オプション
    # ------------------------------------------------------------------

    def set_option(self, key: str, value: Any) -> None:
        self.options[key] = value

    def get_option(self, key: str, default: Any = None) -> Any:
        return self.options.get(key, default)

    def __repr__(self) -> str:
        return (
            f"RunnerContext(host={self.host!r}, server_type={self.server_type!r},"
            f" dry_run={self.dry_run}, variables={list(self.variables.keys())})"
        )

# runner.py マニュアル

## 概要
`runner.py` は YAML 設定（version: 3）と DSL スクリプトを使って、
`txt2img` / `img2img` / `img2txt2img` / `workflow(ComfyUI)` をイベントドリブンで実行するランナーです。

## 実行方法

```bash
python runner.py [CONFIG] [options]
```

- `CONFIG`: 設定 YAML（省略時 `prompts/runner.yaml`）

主なオプション:

- `--script`, `-s`: 外部 DSL スクリプトファイル（設定の `script:` を上書き）
- `--host`, `-H`: API ホスト URL（設定の `host:` を上書き）
- `--dry-run`, `-n`: API 呼び出しをスキップ
- `--loop`, `-l`: スクリプト終了後に再実行（無限ループ）
- `--profile`, `-p`: デフォルトプロファイル名（将来拡張用）
- `--version`: バージョン表示

例:

```bash
python runner.py examples/runner-example.yaml --dry-run
python runner.py examples/runner-example.yaml --host http://127.0.0.1:7860
python runner.py examples/runner-example.yaml --script scripts/runner.dsl
```

## 設定ファイル

最小例:

```yaml
version: 3
host: http://127.0.0.1:7860
comfyui_host: http://127.0.0.1:8188

log:
  path: ./log/runner.log
  level: info
  days: 7

profiles:
  txt2img:
    sfw:
      input: prompts/v2/sfw.yaml
      output: ./outputs
      models:
        - modelA.safetensors
  comfyui:
    anima:
      input: prompts/v2/comfy-anima.yaml
      output: ./outputs/comfy
      comfy_save: save

script: |
  PING
  CHECKSERVER
  txt2img sfw
```

### キー説明

- `host`: A1111 / Forge 側の API ベース URL
- `comfyui_host`: ComfyUI 側 API URL
- `log`: ログ設定
- `profiles`: 実行プロファイル定義
  - `txt2img`, `img2img`, `img2txt2img`, `comfyui` をカテゴリとして持つ
- `script` または `script_file`: DSL 実行内容

## DSL コマンド（主要）

制御:

- `LOOP N ... ENDLOOP`
- `FOREACH var IN arr ... END`
- `WHILE expr ... END`
- `IF expr ... ELSE ... ENDIF`
- `BREAK`, `EXIT`

変数:

- `SET x = expr`
- `ARRAY arr = [a,b,c]`
- `VALLOAD file.yaml|file.csv`
- `VALSAVE file.yaml`

イベント/待機:

- `PING [host]`
- `PING [host] [timeout_sec]` (`timeout_sec=0` は無期限待機)
- `CHECK HH:MM-HH:MM`
- `WAIT HH:MM`
- `SLEEP sec`
- `WATCH path [pattern] [timeout]`

サーバー関連:

- `CHECKSERVER`
- `UNLOAD [host]`
- `SETMODEL model [vae]`
- `GETMODEL`
- `HOST url`

実行:

- `txt2img <profile>`
- `img2img <profile>`
- `img2txt2img <profile>`
- `workflow <profile_or_json> [key=value ...]`
- `JSONL ...`
- `CALL ...`
- `CUSTOM plugin_name [args...]`

## ComfyUI 実行モード

`workflow` は 2 モードあります。

1. YAML モード（推奨）
- `profiles.comfyui.<name>.input` を指定
- 内部で `cp2.main(api_comfy=True)` を呼び、`create_text_v2()` 前段を通して実行

2. 直接 JSON モード
- `profiles.comfyui.<name>.workflow` または `workflow path/to/workflow.json`
- ワークフロー JSON を直接送信

## ログと終了処理

- `runner.py` は終了時に以下を実行します:
  - `modules.api.shutdown()`
  - `logger.closeAllLoggers()`
- これにより、ログファイルハンドルや HTTP クライアントが残ってプロセス終了を妨げる問題を防ぎます。

## トラブルシュート

- 設定ファイルが見つからない:
  - `python runner.py <config.yaml>` のパスを確認
- `script` が無い:
  - YAML に `script:` か `script_file:` を設定
- ComfyUI に繋がらない:
  - `comfyui_host` の URL とポートを確認
- テスト実行で終わらない:
  - `PING` を `PING http://127.0.0.1:7860 10` のようにタイムアウト付きで実行
  - `LOOP -1` をテスト時は `LOOP 1` など有限回に変更
- モデル切替が効かない:
  - `CHECKSERVER` でサーバー種別を確認し、対象 API が model/vae 切替対応か確認

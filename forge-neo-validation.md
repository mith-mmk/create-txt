# Forge Neo対応の検証（2026-09-12）

## 実装

- 基本YAML → 通常profile → model_profile（親→子）→ ui_profile → 明示CLIの順で適用。
- 条件別profileは変数展開前に一度だけ評価。辞書を再帰マージし、配列を置換。
- UI・モデル種別の自動判定、明示指定、別名、未知種別の警告を追加。
- YAMLのimg2img、画像・マスク・複数参照入力、Neoの追加モジュールと編集切替に対応。
- runnerへの設定伝播とNeo判定、画像ゼロ・生成失敗・保存失敗の成否伝播を修正。
- 使用例は `examples/neo-txt2img.yaml` と `examples/neo-edit.yaml`。

## 自動テスト

関連テスト **92件成功**。

```sh
python -m pytest tests/test_generation_profiles.py tests/test_webui_neo.py tests/test_cp2_cli.py tests/test_comfyui_workflow.py -q -p no:cacheprovider
```

確認内容: 継承・適用順、CLIの既定値を明示した場合の優先、変数展開、別名重複、
空設定、load_profile、実行間の設定混入、種別判定、通信不可、オフライン生成、
画像・マスク・参照画像、編集モード、追加モジュール、モデル名のハッシュ接尾辞、
APIエラー、画像ゼロ、保存失敗、runner連携、既存ComfyUIワークフロー。

全体では **135件成功、既存の失敗1件**。
OneDrive配下への書込みが拒否される環境のため、全体テストは同じソースを
書込み可能な一時ディレクトリへコピーして実行した。

既存失敗: `tests/test_reader_db.py::test_jsonl2db_import_creates_readable_rows`。
ランダムな名前のJSONLを取り込みながら `__name__ = sample` で検索するため0件になる。
変更前HEADを `git archive` で取り出した環境でも同じ失敗を再現した（同ファイルは2件成功・1件失敗）。
対象のDBテスト・読込実装・インポート実装に今回の変更はない。

変更したPythonコードのコンパイル確認と `git diff --check` も完了。

## ローカルNeoでの実生成

接続先: `http://localhost:7860/`。生成情報のサーバーバージョン: `neo-2.29`。
次の経路で画像生成・PNG保存・512×512サイズ・生成メタデータを確認した。

| 経路 | モデル | 結果 |
| --- | --- | --- |
| YAML txt2img | Anima | 成功。model_profileの5ステップとui_profileのNormalスケジューラーを確認 |
| YAML img2img | Anima | 成功。初期画像・denoising_strengthを使用 |
| 従来の画像ファイル入力img2img | Anima | 成功。2ステップ指定と保存を確認 |
| 参照画像2枚のtxt2img編集 | Flux.2-Klein 4B FP8 | 成功。ImageStitchと追加モジュールを使用 |
| 初期画像＋参照画像2枚のimg2img編集 | Flux.2-Klein 4B FP8 | 成功 |

編集生成では、緑のティーポットに変更する指示に対応した画像を目視確認した。
検証画像・入力YAML・ログは `C:/temp/temp-python/neo-live/` に保存。
編集リクエスト後、チェックポイント・追加モジュール・Anima/Klein編集設定が
検証前の値へ復元されたことをAPIで比較確認した。
明示種別を省略した読取確認でも `ui=neo` / `model=anima` を判定した。

## 検証範囲の限界

AnimaとFlux.2-Klein以外の登録モデルの実生成、および専用LoRAが必要な
Anima Edit・Krea 2 Editの実生成は未検証。モデル登録・設定生成・機能不足時の
エラーは自動テストとNeoのAPI／ソースで確認した。
WebUI・旧Forge・ComfyUIの実サーバーでの今回の生成試験は行っていない。
対応種別の登録は、全モデルの品質・速度・動作を実機で保証するものではない。

# Create prompt V2（日本語）

[英語版README](README.md)

Create prompt V2はstable-diffusion-webuiとComfyUI用のプロンプト作成ツールです。現バージョンはSD WebUI Forge NeoとComfyUIを対象にしています。


## 新機能

- AnimaのComfyUI対応
- モデルタイプによる指定
- UIタイプによる指定
- ファイル名による個別指定

## 目的

ProfileからStable Diffusion用のプロンプトを自動作成します。
APIを呼び出して画像を自動生成することもできます。
ComfyUI APIにも対応しています（[ComfyUIの説明](#comfyui)）。

- 詳細はexamplesを参照してください

input.yaml

```yaml
version: 2.0 # must(必須)
options:
  output: ./outputs/v2/girls.json # output file(出力ファイル)
  json: true # output json(jsonで出力)
  number: 50 # number of prompt(プロンプトの数)
methods: # random: 1  or multiple: array
  - random: 0 # random 0 is use options.number(0はoptions.numberを使用) randam is generate random prompt(randomはランダムプロンプトを生成します)
  - cleanup: prompt negative_prompt # clean up prompt (promptをクリーンアップします)

variables: # variables(変数)
  negative: ['nsfw, easynegative'] # If you define variables in the config, define them as an array(config内に変数を定義する場合は配列で定義します)
  actions: $json/actions.jsonl # actions(アクション)
  outfits: $jsonl/outfits.json # outfits(服)
  place: $jsonl/places.jsonl[places] # place(場所)

  eyes: $jsonl/eyes.jsonl[eyes] # ${eyes} 目
  hair: $jsonl/hairs.jsonl[hair] # ${hair} 髪

command: # prompt command(プロンプトコマンド) The content that will be output to the file(ファイルに出力される内容になります)
  prompt: '${eyes} ${hair} girl wearing ${outfits} is ${actions} ${place} ' # prompt command(プロンプトコマンド)
  negative_prompt: '${negative}'
  seed: -1
  width: 512
  height: 512
  steps: 20
  cfg_scale: 7.5
  sampler_name: DPM++ SDE
  batch_size: 1 # if you can use n size batch
  n_iter: 1 # also same butch count
  # higher.fix
  enable_hr: true
  hr_scale: 2
  hr_upscaler: R-ESRGAN 4x+ Anime6B
  denoising_strength: 0.5
  hr_second_pass_steps: 10
  override_settings: # override settings(設定を上書き)
    CLIP_stop_at_last_layers: 2 # CLIP stop at last layers(CLIPを停止する階層を指定、2を推奨するケースが多い)
```

JSONL（eyes.jsonl）

```jsonl
/*
  If you want write comment in jsonl, you can it.(jsonl内でコメントを書く場合は、このようにします)
*/
// You can write like this(これでも可能です)
{"W": 0.1, "C": ["eyes"], "V": "blue eyes"} // W C V is upper case(W C Vは大文字)
{"W": 0.1, "C": ["eyes"], "V": "green eyes"}
{"W": 0.1, "C": ["eyes"], "V": "black eyes"}
{"W": 0.1, "C": ["eyes"], "V": "brown eyes"}
{"W": 0.1, "C": ["eyes"], "V": ["red eyes"]}  // "V" is string or string array("V"は文字列または文字列配列)
```

テキストファイル（セミコロン区切り）も使えますが、カテゴリーは指定できません。

eyes.txt

```text
0.1;blue eyes
0.1;green eyes
0.1;black eyes
0.1;brown eyes
0.1;red eyes
```

## 実行方法

```
python cp2.py input.yaml
```

オプションを追加すると、APIを呼び出して画像を自動生成できます。
WebUIの起動時に--apiと--listenを追加してください。

WebUIの"Prompts from file or textbox"にはtext形式で出力し、APIを呼び出す場合はJSON形式で出力します。

実行例

```
python .\cp2.py .\examples\prompts-girls.yaml
```

出力例

```txt
--prompt (petite kawaii girl) wearing (yellow camisor), normal yellow eyes, annoyed, brown curly twin-tail hair between eyes shiny long hair, (medium breasts) 2girls are serving dish, diorama style (hiten_1, Production I.G), on the fantasy field in the day, steam, (blur), (flock of birds), from side --negative_prompt nsfw, easynegative, ${doing, 2}, pixel_art, halftone, multiple views, monochrome, futanari, futa, yaoi, speech bubble, (low quality, worst quality:1.4), text, blurry, bad autonomy --seed -1 --width 512 --height 704 --steps 30 --cfg_scale 12.5 --sampler_name DPM++ SDE --batch_size 1 --n_iter 1
--prompt (teenage girl) wearing (check pink t-shirt and black denim shorts), white grove, garter belt and knee sox, mole under eye white eyes, embarrassed, light orange wavy triple bun twin-tail dyed bangs short hair, (large breasts) 1girl is claw pose, super-deformed (tony_taka, grisaia_\(series\)), in the bus, vanishing point, long shot, from below --negative_prompt nsfw, easynegative, ${doing, 2}, pixel_art, halftone, multiple views, monochrome, futanari, futa, yaoi, speech bubble, (low quality, worst quality:1.4), text, blurry, bad autonomy --seed -1 --width 512 --height 704 --steps 30 --cfg_scale 12.5 --sampler_name DPM++ SDE --batch_size 1 --n_iter 1
--prompt (teenage girl) wearing (white swim shirt and tight pants), normal green eyes, frown, pink straight flipped shiny medium hair, (small breasts) 2girls are back-to-back, anime_screencap (Production I.G, Charlie Bowater), on the poolside, (sharp focus), from below --negative_prompt nsfw, easynegative, ${doing, 2}, pixel_art, halftone, multiple views, monochrome, futanari, futa, yaoi, speech bubble, (low quality, worst quality:1.4), text, blurry, bad autonomy --seed -1 --width 512 --height 704 --steps 30 --cfg_scale 12.5 --sampler_name DPM++ SDE --batch_size 1 --n_iter 1
--prompt (teenage girl) wearing (floral print black long skirt maid uniform with white apron and white hairband), normal grey eyes, excited, light grey straight hair between eyes shiny medium hair, (small breasts) 1girl is falling from sky, super-deformed (kantoku_\(style\), Unfairr), in the jinja shrine, (feathers effect), from side --negative_prompt nsfw, easynegative, ${doing, 2}, pixel_art, halftone, multiple views, monochrome, futanari, futa, yaoi, speech bubble, (low quality, worst quality:1.4), text, blurry, bad autonomy --seed -1 --width 512 --height 704 --steps 30 --cfg_scale 12.5 --sampler_name DPM++ SDE --batch_size 1 --n_iter 1
--prompt (teen cute girl) wearing (geometric pattern helloween dress, GhostWhite rose motif hair ornament), check brown cap, camouflage emerald green chocar, normal emerald green eyes, nose blush, light orange straight single braid shiny short hair, (medium breasts) 6girl+ are dancing, thick outline, black outline (Ufotable, violet_evergarden), in the temple, (spot light) --negative_prompt nsfw, easynegative, ${doing, 2}, pixel_art, halftone, multiple views, monochrome, futanari, futa, yaoi, speech bubble, (low quality, worst quality:1.4), text, blurry, bad autonomy --seed -1 --width 512 --height 704 --steps 30 --cfg_scale 12.5 --sampler_name DPM++ SDE --batch_size 1 --n_iter 1
--prompt (milf wife) wearing (black sweater dress), lemon print green cap, normal pink eyes, light smily, white straight side braid hair over one eye very short hair, (pointy breasts) 1girl opens a door, super-deformed (pixiv, kantoku_\(style\)), in the buddest temple in the day, motion lines, (confetti) --negative_prompt nsfw, easynegative, ${doing, 2}, pixel_art, halftone, multiple views, monochrome, futanari, futa, yaoi, speech bubble, (low quality, worst quality:1.4), text, blurry, bad autonomy --seed -1 --width 512 --height 704 --steps 30 --cfg_scale 12.5 --sampler_name DPM++ SDE --batch_size 1 --n_iter 1
--prompt (teen cute girl) wearing (space print BlueViolet t-shirt and twotone microskirt), normal light blonde, eye reflection eyes, frown, purple straight twin-tail hair over shoulder hair, (medium breasts) 2girls are sweaping, super-deformed (Yuumei, momoco_\(momoco_haru\)), in the office room, trembling, full shot --negative_prompt nsfw, easynegative, ${doing, 2}, pixel_art, halftone, multiple views, monochrome, futanari, futa, yaoi, speech bubble, (low quality, worst quality:1.4), text, blurry, bad autonomy --seed -1 --width 512 --height 704 --steps 30 --cfg_scale 12.5 --sampler_name DPM++ SDE --batch_size 1 --n_iter 1
--prompt (house wife) wearing (morning glory print silver tied shirt and pink pencil skirt on FireBrick jacket), normal brown, closed eyes eyes, jitome, white straight sidelocks twin-tail shiny floating long hair, (flat chests) 1girl is hand in own leg, game_cg (RossDraws, minori), in the school, (faint light), medium shot, from above --negative_prompt nsfw, easynegative, ${doing, 2}, pixel_art, halftone, multiple views, monochrome, futanari, futa, yaoi, speech bubble, (low quality, worst quality:1.4), text, blurry, bad autonomy --seed -1 --width 512 --height 704 --steps 30 --cfg_scale 12.5 --sampler_name DPM++ SDE --batch_size 1 --n_iter 1
--prompt (curte slender girl) wearing (argylec white negligee, hair flower), camouflage gray boots, normal orange, closed one eye eyes, sleepy, blonde straight single hair bun very short hair, (medium breasts) 1girl is v sign, Lego style (egami, pixiv), in row of cherry blossom trees, (sharp focus), (breeze), full shot --negative_prompt nsfw, easynegative, ${doing, 2}, pixel_art, halftone, multiple views, monochrome, futanari, futa, yaoi, speech bubble, (low quality, worst quality:1.4), text, blurry, bad autonomy --seed -1 --width 512 --height 704 --steps 30 --cfg_scale 12.5 --sampler_name DPM++ SDE --batch_size 1 --n_iter 1
--prompt (teenage girl) wearing (white blazer and uniform), normal silver eyes, doyagao, orange straight twin-tail dyed bangs very long hair, (medium breasts) 1girl is standing up, super-deformed (RossDraws, yuzusoft), in Taipei blue sky, wet, dynamic angle, medium shot --negative_prompt nsfw, easynegative, ${doing, 2}, pixel_art, halftone, multiple views, monochrome, futanari, futa, yaoi, speech bubble, (low quality, worst quality:1.4), text, blurry, bad autonomy --seed -1 --width 512 --height 704 --steps 30 --cfg_scale 12.5 --sampler_name DPM++ SDE --batch_size 1 --n_iter 1
```

テキスト形式の出力はWeb UIに貼り付けて使います。

APIを呼び出す場合はJSON形式で出力します。

```
python cp2.py input.yaml --json
```

設定ファイルに直接記述することもできます。

```yaml
options:
  json: true
```

WebUI APIを直接実行できます。

```
python cp2.py input.yaml --api-mode --api-base http://localhost:7860 --api-output-dir ./outputs/text-images --api-filename-pattern [num]-[seed]
```

JSONファイルを実行する場合は、--input-jsonを使います

```
python cp2.py --api-input-json "./outputs/examples.json" --api-output-dir ./outputs/text-images --api-filename-pattern [DATE]-[num]-[seed]
```

# 環境

- Python 3.10以降。
- WebUI、Forge、Forge Neoを使う場合はサーバーを `--api` 付きで起動します。別ホストから接続する場合はリモートアクセスを有効にしてください。
- ComfyUIを使う場合はComfyUI APIと `--comfy` を指定します。

# 使い方

```
usage: cp2.py [-h] [--append-dir APPEND_DIR] [--output OUTPUT] [--json [JSON]] [--escape-filename [ESCAPE_FILENAME]]
              [--api-mode [API_MODE]] [--api-base API_BASE] [--api-userpass API_USERPASS]
              [--api-output-dir API_OUTPUT_DIR] [--api-input-json API_INPUT_JSON]
              [--api-filename-pattern API_FILENAME_PATTERN] [--api-filname-pattern API_FILNAME_PATTERN]
              [--max-number MAX_NUMBER] [--num-length NUM_LENGTH]
              [--api-filename-variable [API_FILENAME_VARIABLE]] [--json-verbose [JSON_VERBOSE]]
              [--num-once [NUM_ONCE]] [--api-set-sd-model API_SET_SD_MODEL]
              [--api-set-sd-vae API_SET_SD_VAE] [--text-encoder TEXT_ENCODER]
              [--override [OVERRIDE ...]] [--info [INFO ...]]
              [--save-extend-meta [SAVE_EXTEND_META]] [--image-type {jpg,png,webp}]
              [--image-quality IMAGE_QUALITY] [--api-type {txt2img,img2img,interrogate}]
              [--interrogate {clip,deepdanbooru}] [--model MODEL] [--alt-image-dir ALT_IMAGE_DIR]
              [--mask-dirs MASK_DIRS] [--mask-blur MASK_BLUR] [--cn-images-dir CN_IMAGES_DIR]
              [--cn-save-pre [CN_SAVE_PRE]] [--profile PROFILE]
              [--api-comfy-save {save,both,ui}] [--api-comfy [API_COMFY]]
              [--comfy [COMFY]] [--comfy-mode {txt2img,img2img,interrogate}]
              [--comfy-family {sd15,sdxl,sd35,flux,anima}] [--comfy-template COMFY_TEMPLATE]
              [--comfy-image COMFY_IMAGE] [--comfy-mask COMFY_MASK]
              [--comfy-controlnet COMFY_CONTROLNET] [--comfy-lora COMFY_LORA] [--comfy-node COMFY_NODE]
              [--debug [DEBUG]] [--verbose [VERBOSE]] [--v1json [V1JSON]]
              [--prompt [PROMPT]] [--json-escape [JSON_ESCAPE]]
              [input]
```

パーサーは変更されることがあります。正確な最新一覧は `python cp2.py --help` を参照してください。
引数はまだ増減しているため、正確な最新一覧は `python cp2.py --help` を参照してください

-h, --help: ヘルプを表示して終了します

--append-dir APPEND_DIR
入力プロンプト追加ファイルのディレクトリ

--output OUTPUT: プロンプトリストの出力先

--json: JSONで出力します（既定はWeb UIのprompt matrix用テキストです）

--v1json: 旧バージョンのJSONで出力します

--profile PROFILE: 設定ファイルのprofileを切り替えます

--debug: デバッグモード

--json-verbose: JSONに詳細情報を出力します

--api-mode: APIを呼び出して自動実行します（--jsonを強制します）
API仕様は https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API を参照してください。

--api-base API_BASE: このスクリプトからAPIを呼び出すベースURL

--api-output-dir API_OUTPUT_DIR
APIで生成した画像の出力ディレクトリ

--api-input-json API_INPUT_JSON
JSONファイルからAPIへ直接入力します

--api-filename-pattern API_FILENAME_PATTERN
API出力のファイル名パターン（既定値: [num]-[seed]）

--max-number MAX_NUMBER
YAMLモードのoption.numberを上書きします

--api-filename-variable
ファイル名で変数を置換します

--api-set-sd-model SD_MODEL
SDモデルを変更します

--api-set-sd-vae VAE_FILE
VAEファイルを指定します（拡張子を含めます）。`Automatic` はWebUIでは有効ですが、ComfyUIではVAE未指定として扱います。


--text-encoder TEXT_ENCODER
Forge/Neoのテキストエンコーダーモジュールを指定します。`Automatic` はサーバーの既定値を維持します。


--override
commandの値を上書きします

--values (-v)
YAMLの値を上書きします
例: "-v prefix=a,face=smile"
filename: "${prefix}-001.json" → filename: "a-001.json"
face: ["\${face} face"] → face: ["smile face"]

--info
情報を追加します

--save-extend-meta
create_promptで使う拡張メタデータを保存します

--image-type
画像形式（jpgまたはpng、既定はpng）

--image-quality
jpgの画質（既定値80）

--debug
デバッグモード
--verbose
詳細モード
--prompt
プロンプトだけを出力します
--json-escape
マルチバイト文字をエスケープしたJSONを出力します

--api-comfy
WebUIの代わりにComfyUI APIを使います
--api-comfy-save: ComfyUI APIの画像保存先を指定します
uiはComfyUIサーバー、saveはローカル、bothは両方に保存します
saveを指定した場合のみメタデータをAutomatic1111互換へ変換します

## 互換性

- V2はV1と互換性がありません

# インストール

- Python 3.10以降が必要です

必要なパッケージをインストールします

```
pip install -r requirements.txt
```

# YAMLモード

yamlモードはyamlファイルからプロンプトリストファイルを作成します

## V1との違い

- 変数モードのみです
- appendsは廃止されました
  - variablesとarrayに変更されました
- multipeとaftermultipeは廃止されました
  - methodsに変更されました
- 連想配列に対応しています
- リストファイルとしてJSONLを読み込めます
- JSONLのカテゴリークエリーに対応しています
- 変数のネストは最大10階層で、定義順は問いません

## メソッド

- randomはランダムなプロンプトを生成します
- multipleは配列から複数のプロンプトを生成します
- cleanupはプロンプトをクリーンアップします
- defaultはrandom: 0です

```yaml
version: 2 # must(必須)
import:
  - ./add_profile.yaml # import add yaml files (yamlインポート 基本profileを分割するのに使う)
options:
  output: ./outputs/v2.json
  json: true
  number: 10 # number of prompt(プロンプトの数) multipleの場合は配列数がかけ算される

methods: # random: 1  or multiple: array
  - preset: model # presets(プリセット) only choice once(最初に一度だけ選択)
  - exclude: date # exclude choice in "random", run random exclude variables will be clear("random"で除外する変数)
  - random: 0 # random 0 is use options.number(0はoptions.numberを使用)
  - multiple: char place # array char と place から複数のプロンプトを生成
  - choice: actions # values choice before run "random" method(randomの実行前に値を選択)
  - random: 0 # random use after multiple must set 0(mutipleの後にrandomを使う場合は0を設定する)
  - creanup: prompt # clean up prompt (promptをクリーンアップ)
variables: # 変数
  model:
    - xd.safetesors
    - sd15.safetesors
  actions:
    - standing
    - sitting
  date: jsonl/date.jsonl[animal] # jsonl file and category query(カテゴリークエリー)

array: # マルチプル用配列
  char: [cat, dog, bird, fish] # make prompt matrix of cat, dog, bird, and fish
  place: [room, garden, park, street] # make prompt matrix of room, garden, park, and street
command: # command  workflow.json <- driect worlkflow.json setting for Comfy UI
  prompt: '${char} is ${actions} in ${place}, ${date}' # prompt command(プロンプトコマンド)
  negative_prompt: 'negative prompt'
  seed: -1 # -1 is random seed(-1はランダムシード)
  width: 640 # width of image(画像の幅)
  height: 448 # height of image(画像の高さ)
  cfg_scale: 7.5 # scale of image(画像のスケール)
  # それ以外はapiのマニュアルを参考にしてください
```

この場合、160のプロンプトが生成されます。multipleモードでcharが4つ、placeが4つ指定されているため10 _ 4 _ 4 = 160になります。

## 配列変数

```yaml
char:
  - 0.1;cat;dog;bird;fish
cat: ${char[1]} # array is start 1, zero is not support(配列は1から始まります)
dog: ${char[2]}
bird: ${char[3]}
fish: ${char[4]}
```

配列変数では配列の先頭に重みを指定できます。

## ネスト変数

```yaml
char:
  - ${animal}
  - ${human}
'animal': [cat, dog, bird, fish]
human: [girl, boy]
```

この場合、\$\{char\}が\$\{animal\}と\$\{human\}に置き換えられます

## 属性と連想配列

次の予約語は直接参照できません: 「W」「C」「V」「weight」「choice」「variable」「query」。

```yaml
char:
  - ${being["V"]} # NG
  - ${being["W"]} # NG
  - ${being["C"]} # NG
  - ${being["weight"]} # NG
  - ${being["choice"]} # NG
  - ${being["variable"]} # NG
  - ${being["query"]} # half OK
  - ${being["animal"]} # OK
  - ${being["size"]} # OK
  - ${=query{"being", "animal"}} # use "query"

being: jsonl/being.jsonl[animal,human]
```

JSONLファイル（beings.jsonl）

```jsonl
{"W":0.1, "C":["animal"], "V":"day", "animal":"cat", "size":"small"}
{"W":0.1, "C":["animal"], "V":"day", "animal":"dog", "size":"big"}
{"W":0.1, "C":["animal"], "V":"night", "animal":"bird", "size":"small"}
{"W":0.1, "C":["animal"], "V":"night", "animal":"fish", "size":"big"}
```

```yaml
being: jsonl/being.jsonl[animal]
'animal': ${being["animal"]}
size: ${being["size"]}
```

issue #1: 入れ子の連想配列には対応していません

## ファイルの読み込み

### テキスト

```yaml
date: text/date.txt
```

この場合、date.txtファイルを読み込みます

```text
0.1;day
0.1;night
```

textではクエリーと連想配列はサポートされていません

### JSONL

```yaml
date: jsonl/date.jsonl[animal]
```

この場合、date.jsonlファイルを読み込み、カテゴリーanimalをクエリします

```jsonl
{"W":0.1, "C":["animal"], "V":"day", "animal":"cat"}
{"W":0.1, "C":["animal"], "V":"day", "animal":"dog"}
{"W":0.1, "C":["animal"], "V":"night", "animal":"bird"}
{"W":0.1, "C":["animal"], "V":"night", "animal":"fish"}
{"W":0.1, "C":["*"], "V":"moonnight", "animal":"bird"} // * is wlde card (*はワイルドカードです)
{"W":0.1, "C":["animal","human"], "V":"night", "animal":"human"} // multiple category(複数のカテゴリー)
{"W":0.1, "C":["insect"], "V":"night", "animal":"ant"} // not query(クエリーされない)
{"weight":0.1, "category":["insect"],  "variable":"night", "animal":"ant"} // same as above(上と同じ)
```

Vは配列または文字列になります

このケースで連想配列がサポートされています

例

```yaml
variables:
  actions:
    - standing
    - sitting
  all: jsonl/all.jsonl # all category(全てのカテゴリー)
  date: jsonl/date.jsonl[animal] # category query(カテゴリークエリー)
  day: ${date} # variable = ${date[1]}
  'animal': ${date["animal"]} # associative array(連想配列)
  beings: jsonl/date.jsonl[animal,human] # multiple category(複数のカテゴリー) saparated by comma(カンマで区切る) not support space(スペースはサポートされません)
```

### JSON

```json
[
  { "W": 0.1, "C": ["animal"], "V": "day", "animal": "cat" },
  { "W": 0.1, "C": ["animal"], "V": "day", "animal": "dog" },
  { "W": 0.1, "C": ["animal"], "V": "night", "animal": "bird" },
  { "W": 0.1, "C": ["animal"], "V": "night", "animal": "fish" },
  { "W": 0.1, "C": ["*"], "V": "moonnight", "animal": "bird" },
  { "W": 0.1, "C": ["animal", "human"], "V": "night", "animal": "human" },
  { "W": 0.1, "C": ["insect"], "V": "night", "animal": "ant" },
  { "weight": 0.1, "choice": ["insect"], "variable": "night", "animal": "ant" }
]
```

- issue: クエリーには対応していません

### DBクエリー

SQLite の DB クエリーをサポートしています

```yaml
database:
  db: sqlite3
  db_connection: db/date.sqlite3 # db connection(データベース接続)
variables:
  date: date_items[category = `animal`]
  cat: date_items[category = `animal` and animal = `cat`]
  named: date_items[__name__ = `animals__eyes`]
```

DB行は次のスキーマを使用します。


```text
name, category, weight, variable, attributes(json)
```

よく使う属性は列にも展開できますが、`attributes` はJSONとして保持されます。


`tools/jsonl2db.py` でJSONLをSQLiteへ取り込めます。ディレクトリも再帰処理できます。


```shell
python tools/jsonl2db.py ./jsonl ./db/items.sqlite3
```

ディレクトリを指定すると、相対パスから `__name__` を生成します。


### クエリーサフィックス（2025/07/06追加）

クエリーサフィックスを有効にする
query suffixiesは、jsonlのカテゴリーをクエリするための接尾語です。modelによって、受け付ける単語が異なる場合にsuffixを使い分岐させることができます

```yaml
options:
  query_suffixies: [-xl] # enable query suffix(クエリーサフィックスを有効にする)
variables:
  date: jsonl/date.jsonl[animal] # query category animal(カテゴリーanimalとanimal-xlをクエリ)
```

## プロファイル

設定ファイルをprofileで上書きします

```yaml
command:
  width: 512
  height: 512
  enable_hr: true
  hr_scale: 2

profiles: # override from default profile(デフォルトプロファイルから上書き)
  xl:
    command:
      width: 1024
      height: 1024
      enable_hr: false
      refiner_switch_at: 0.7
  pory:
    load_profile: [xl] # before Load profile xl(プロファイルxlを先に読み込む)
    command:
      override_settings: # WebUIのSettingを上書きする
        CLIP_stop_at_last_layers: 2 # CLIPの最終層を変更する(推奨 2)
        emphasis: 'No norm' # 強調の設定
        override_settings_restore_afterwards: true # 実行後にオプションを書き戻す
```

プロファイルを実行

```
python cp2.py --profile xl input.yaml
# width = 512, height = 512, enable_hr = true, hr_scale = 2

python cp2.py --profile xl input.yaml
# width = 1024, height = 1024, enable_hr = false, refiner_switch_at = 0.7
```

プロファイルから他のプロファイルを読み込む

```yaml
profile:
  xl:
    load_profile: [animal]
    command:
      width: 1024
      height: 1024
  animal:
    command:
      prompt: 'animal'
      width: 512
      height: 512
```

この場合、デフォルトプロファイル -> animalを先に読み込みます
プロファイルは入れ子にできません

## Forge Neoと条件別プロファイル

Forge NeoはWebUI互換のtxt2img APIとimg2img APIに対応しています。
サーバーを--api付きで起動してください。接続先の既定値は
http://localhost:7860で、--api-baseで変更できます。対応する静止画モデルは
[Forge Neoのモデル一覧](https://github.com/Haoming02/sd-webui-forge-classic/blob/neo/README.md)
に従います。動画モデル、PiD専用アップスケーラー、VAE、テキストエンコーダーは
モデル種別に含めません。NeoではSD2とSD3は対象外ですが、既存のWebUIと
ComfyUI対応は維持します。

### 適用順序

**基本YAML → 通常profile → model_profile（親→子）→ checkpoint_profile → ui_profile → CLI上書き**

model_profile、checkpoint_profile、ui_profileはトップレベルのマッピングです。
各エントリーには通常profileと同じcommand、options、variables、array、
methods、load_profileなどを指定できます。辞書は再帰的にマージし、配列と
スカラーは前の値を置換します。空のエントリーは何もしません。
load_profileはprofilesの既存エントリーを1段先に読み込みます。
base_yamlとimportは従来の順序で処理します。

~~~yaml
version: 2
options:
  ui_type: neo
  model_type: noobai
  json: true
methods: [{ random: 1 }]
command: { prompt: 'a cat' }
model_profile:
  sdxl:
    command: { width: 1024, height: 1024 }
  illustrius:
    command: { cfg_scale: 5 }
  noobai:
    command: { cfg_scale: 4 }
ui_profile:
  neo:
    command: { scheduler: Normal }
~~~

model_profileにはモデル種別・版の共通設定を、checkpoint_profileには選択した
チェックポイント固有の設定を記述します。チェックポイントキーはtitle、
filename、model_name、hash、sha256と照合します。大小文字とパス区切りを
正規化し、Forgeのハッシュサフィックスを吸収します。フルパス、basename、
stem、拡張子を省略したモデル名を指定できます。同じ優先度で複数一致した
場合は曖昧さとしてエラーにします。不明なチェックポイントは何も変更しません。

~~~yaml
options:
  model_type: anima_2.9b
  model: JANIMAAnima_v1029B_bf16.safetensors

model_profile:
  anima:
    options:
      vae: qwen_image_vae.safetensors
      text_encoder: Qwen3-0.6B-Base.Q8_0.gguf
  anima_2.9b:
    command: { steps: 30, cfg_scale: 4 }

checkpoint_profile:
  JANIMAAnima_v1029B_bf16:
    command:
      sampler_name: Euler a
      scheduler: Normal
~~~

options.model_typeまたはoptions.ui_typeを省略すると自動判定します。
--model-typeと--ui-typeはYAMLより優先されます。UI種別はwebui、forge、
neo、comfyです。Neoはui_profile.forgeを継承しません。種別指定だけでは
APIを送信しません。WebUI互換APIには--api-mode、ComfyUIには--comfyを
使います。ComfyUIフラグと異なるUI種別の同時指定はエラーです。

判定と条件別profileの適用は、通常profileの後、変数展開とmethods実行の前に
YAML実行1回につき1度だけ行います。checkpoint_profileも選択済みチェック
ポイントに対して1度だけ解決します。条件別profileでモデルや種別を変更しても
再判定・再適用は行いません。異なるモデル系統は実行を分けてください。

CLIまたはYAMLで明示したチェックポイントを優先し、未指定時はAPIの現在モデルを
使います。メタデータとモデル名・パスから判定し、UIプリセットだけでは断定
しません。不明な場合は警告し、判明した親種別まで適用します。完全に不明なら
model_profileを省略します。オフライン生成ではAPIへ接続せず、手元の情報を
使います。ログには判定結果、根拠、適用したprofileを出力します。

### モデル種別

右列の派生種別は左列の設定を継承します。矢印は適用順を示します。

| 共通キー | 派生キー |
| --- | --- |
| sd15 | SD1.5 |
| sdxl | illustrius → noobai、pony、mugen |
| flux | flux-dev、flux-schnell、flux-krea、flux-kontext |
| flux2-klein | flux2-klein-4b、flux2-klein-9b |
| chroma | chroma-hd |
| lumina | neta-lumina、netayume-lumina |
| qwen-image | qwen-image-edit |
| z-image | z-image-turbo |
| anima | anima_2b、anima_2.9b、anima_3.8b、anima-edit |
| ernie-image | ernie-image-turbo |
| krea2 | krea2-turbo、krea2-raw、krea2-edit |

Animaの版には-edit付きのキーもあります。anima_2.9b-editは
anima → anima_2.9b → anima-edit → anima_2.9b-editの順に適用します。
krea2-turbo-editとkrea2-raw-editも共通Edit設定を含みます。
Animaの版が不明な場合はanimaだけを適用します。

別名はillustrious → illustrius、sd1とsd1.5 → sd15、flux.1とflux1 → flux、
flux.1-kontext → flux-kontext、flux.2-klein → flux2-klein、
chroma1-hd → chroma-hd、lumina-image-2.0 → lumina、krea-2 → krea2、
anima_2.0b → anima_2bです。別名と正規名を重複定義するとエラーになります。
既存バックエンド用にはsd2とsd35（別名sd3、sd3.5）も指定できます。

### 画像入力と追加モジュール

| YAMLのoptions | CLI | 用途 |
| --- | --- | --- |
| image | --image | img2imgの初期画像 |
| mask | --mask | img2imgのマスク |
| reference_images（配列） | --reference-image（繰返し可） | Neoの編集参照画像 |
| reference_max_size | — | 参照画像の最大辺。既定1024 |

相対パスは実行時の作業ディレクトリを基準に解決します。画像はクライアントで
Base64に変換します。command.init_imagesとcommand.maskにはパスまたは既存の
Base64を指定できます。初期画像には--api-type img2imgが必要です。
参照画像はt2iとi2iの両方で使え、指定順にNeoのImageStitch Integratedへ渡します。
同じalwayson_scripts指定との併用はエラーです。従来の画像ファイル・ディレクトリ
入力によるimg2imgも維持しています。

NeoとForgeのVAEはoptions.vae、テキストエンコーダーはoptions.text_encoderで
指定します。配列またはカンマ区切り文字列を使えます。旧設定options.sd_vaeも
下位互換のため使用できます。CLIは--api-set-sd-vaeと--text-encoderです。
command.override_settings.forge_additional_modulesで追加モジュールを直接指定
できます。一覧APIで名前を解決し、不明・曖昧な名前はエラーにします。
Automaticまたは未指定は現在の選択を維持し、空配列[]は明示的に解除します。
override_settings_restore_afterwards: trueで実行後に設定を復元できます。

Anima、Klein、Kreaの通常img2imgでは編集モードを無効にします。参照画像または
Edit種別を指定すると有効になります。明示したoverride_settingsは尊重します。
Anima EditとKrea 2 Editには専用LoRAが必要で、自動取得は行いません。
サーバーに必要な機能がない場合は送信前にエラーにします。

通常生成の例: examples/neo-txt2img.yaml

~~~sh
python cp2.py examples/neo-txt2img.yaml --api-mode
python cp2.py examples/neo-txt2img.yaml --api-mode --api-type img2img --image input.png --mask mask.png
~~~

編集生成の例: examples/neo-edit.yaml

~~~sh
python cp2.py examples/neo-edit.yaml --api-mode --reference-image first.png --reference-image second.png
~~~

例のチェックポイント名と追加モジュール名は環境に合わせて変更してください。
runnerの各profileにもmodel_type、ui_type、image、mask、reference_imagesを指定
できます。img2imgのYAMLはrunner profileのinputで指定します。生成APIの失敗、
画像ゼロ、保存失敗は成功として返しません。

インストール済みチェックポイントの切替確認にはexamples/test_model_switch.pyと
examples/test-model-switch.ps1を使えます。モデル名は環境ごとに異なるため、
各チェックポイントを明示してください。

~~~powershell
pwsh ./examples/test-model-switch.ps1 -AnimaModel "anima_2b.safetensors" -IllustriousModel "illustrious.safetensors" -PonyModel "pony.safetensors" -DryRun
~~~

-DryRunを外すと各モデルを順番に切り替えます。-Generateを追加すると切替後に
各モデルで1枚のt2iを実行します。DryRunは生成せず、引数と順序だけを確認します。
## パーサー

「${ }」内の文は式として解析できます（${= }の中に式を書けます）。

例

```yaml
seed: ${=random_int()} # random seed(ランダムシード)
width: ${=int(${size}) * 2} # width = size * 2(幅 = サイズ * 2)
```

### パーサーテスト

実行できるYAMLサンプルは[examples/formula.yaml](examples/formula.yaml)です。
リポジトリのルートで次を実行すると、式を展開したJSONを保存します。画像生成APIは使用しません。

```sh
python cp2.py examples/formula.yaml --output outputs/formula.json
```

期待する出力は[examples/formula.expected.json](examples/formula.expected.json)です。
四則演算の優先順位、変数、`>=`・`<=`、負数の関数引数、文字列の繰り返し、`split`を確認できます。
YAMLの文字列変数を数値として計算するときは、サンプルの`int(size)`のように変換してください。

回帰テストと、サンプルのCLI実行・JSON保存のテスト:

```sh
python -m pytest tests/test_formula_regressions.py tests/test_formula_sample.py tests/parser_test.py tests/prompt_v2_test.py -q
```

```
> python tools.py parser_test '2 + x * y' 'x=3,y=4'
...
...
...
14.0

> python tools.py parser_test '"test" == str' 'str=test'
...
...
...
1       # true
```

### 関数

ブール型はサポートしていません。結果は0（偽）または1（真）です。

関数では、str1、str2などを文字列、x、yなどを数値として扱います。

- chained("objects", 0.8, 3): 連鎖文字列を作成します。0.8は閾値、3は最大回数です。
  - chained("objects", 0.8, 3) → ${objects}、${objects}, ${object} など
- choice("objects"): objectsから1つ選択します。
  - choice("objects") → ${objects}
- contains(str1, str2, ...): str1に指定した文字列が含まれるか判定します。
  - contains("abc", "a", "b") → 1、contains("abc", "e", "f") → 0
- attribute("objects", str2): 変数objectsの属性を取得します。
  - attribute("objects", "size") → ${objects["size"]}
- choice_index("objects", query, number): query（0.0〜1.0）でインデックスを選択します。
  - choice_index("objects", query, 1) → ${objects[1]}
- choice_attribute("objects", query, attribute): objectsの属性を選択します。
  - choice_attribute("objects", query, "size") → ${objects["size"]}
- value("objects", query): objectsの値を取得します。
  - value("objects", query) → ${objects}
- replace(str1, str2, str3): str1内のstr2をstr3に置換します。
  - replace("abc", "a", "b") → "bbc"
- split(str1, str2): str1をstr2で分割します。
  - split("a,b,c", ",") → ["a", "b", "c"]
- upper(str1): 大文字に変換します。
- lower(str1): 小文字に変換します。
- if(condition, truecase, falsecase): conditionが真ならtruecase、それ以外はfalsecaseを返します。
- pow(x, y): 累乗
- sqrt(x): 平方根
- abs(x): 絶対値
- ceil(x): 切り上げ
- floor(x): 切り捨て
- round(x): 四捨五入
- trunc(x): 切り捨て
- int(str1): 文字列を整数に変換
- float(str1): 文字列を浮動小数点数に変換
- str(x): 数値を文字列に変換
- len(str1): 文字列の長さ
- max(...)、min(...): 最大値、最小値
- not(condition): 0と1を反転
- and(condition1, condition2): 論理積
- or(condition1, condition2): 論理和
- match(str1, str2): 文字列の一致を判定
  - match("abc", "a") → 1、match("abc", "d") → 0
- substring(str1, start, end): 部分文字列を取得
  - substring("abc", 1, 2) → "b"
- random(start, end): 整数または浮動小数点数をランダムに生成
- random_int(): 0〜2^64-1の整数を生成
- random_float(): 0〜1の浮動小数点数を生成
- random_string(len): len文字のランダム文字列を生成
- uuid(): ランダムなUUIDを生成
- time()、date()、datetime()、timestamp(): 現在の時刻・日付・日時・タイムスタンプ
- year()、month()、day()、hour()、minute()、second(): 現在の日時要素
- weekday()、week(): 現在の曜日・週

## ファイル保存

- ファイル保存ではプロンプトリストを保存します。
- 既定のファイル名パターンは [num]-[seed] です。

### ファイル名パターン

- /: フォルダー区切り
- [num]: 画像番号（5桁。--num-lengthで変更できます）
- [seed]: ランダムシード
- [shortdate]: 現在の日付（YYMMDD）
- [DATE]: 現在の日付（YYYYMMDD）
- [date]: 現在の日付（YYYY-MM-DD）
- [datetime]: 現在の日時（YYYYMMDDHHMMSS）
- [shortyear]: 現在の年（YY）
- [year]: 現在の年（YYYY）
- [month]: 現在の月（MM）
- [day]: 現在の日（DD）
- [hour]: 現在の時（HH）
- [min]: 現在の分（MM）
- [sec]: 現在の秒（SS）
- [var:variable]: 変数
- [var:variable:attribute]: 変数の属性
- [var:variable(index)]: 変数のインデックス
- [info:key]: 情報キー

# ComfyUI（ワークフロー）

ComfyUIの引数は更新されています。

- `--comfy` でComfyUI APIを使います。`--api-comfy` は非推奨です。
- ComfyUIでプロンプトを実行するworkflowの作成を試みます。
- txt2imgとimg2imgに対応しています。maskはimg2img + maskとして扱い、hires.fixは自動生成しません。
- 自動workflow生成のfamily: `sd15`、`sdxl`、`sd35`、`flux`、`anima`
- workflowを直接読み込むこともできます。ComfyUIでAPI用workflowを保存するか、`comfyui:` / `workflow:` のYAML DSLを使います。
- ローカル保存では、Automatic1111風のinfotextと `[seed]`、`[var:name]`、`[var:name:attr]` などのファイル名置換を使います。
- WebUIとの互換性維持のためのいくつかの補完機能
- WebSocketを使う場合、SaveImageWebsocketノードのIDは `save_image_websocket_node` にしてください。
  ```json
  "save_image_websocket_node": {
      "inputs": {
        "images": [
          "A66",
          0
        ]
      },
      "class_type": "SaveImageWebsocket",
      "_meta": {
        "title": "画像を保存するWebSocket"
      }
    },
  ```

## ComfyUIオプション

- `--comfy-family`: ワークフローファミリーを選択します。
- `--comfy-mode`: `txt2img`、`img2img`、`interrogate`から選択します。
- `--comfy-template`: workflowビルダー用のテンプレートを指定します。
- `--comfy-image`: img2imgの入力画像
- `--comfy-mask`: img2imgのマスク画像
- `--comfy-controlnet`: ControlNet設定を追加します。JSONまたは `key=value,key=value` を指定できます。
- `--comfy-lora`: LoRAチェーンを追加します。形式は `name[:weight][@positive|negative|both]` です。
- `--comfy-node`: ノード定義を上書きします。形式は `role.field=value` または `role.inputs.key=value` です。

## workflowを直接実行

```shell
python cp2.py --api-output-dir ./outputs/txt2img-images --comfy --api-base http://localhost:8188 --image-type webp --api-input-json ./workflow_api.json
```

## img2imgを直接実行（ComfyUI）

```shell
python cp2.py prompt.yaml --comfy --comfy-mode img2img --comfy-family flux --comfy-image ./inputs/src.png --comfy-mask ./inputs/mask.png --api-base http://localhost:8188
```

## animaテンプレートの例

実用的な `anima` の例は、`UNETLoader -> ModelSamplingAuraFlow -> KSampler` に `CLIPLoader` と `VAELoader` を加えた保存済みworkflowを基にしています。

- YAML例: [examples/anima-template.yaml](examples/anima-template.yaml)
- Workflow JSON例: [examples/anima-template-api.json](examples/anima-template-api.json)

実行例:

```shell
python cp2.py ./examples/anima-template.yaml --comfy --api-base http://localhost:8188 --api-output-dir ./outputs/anima-example
```

`_controlnet_slots` は任意です。定義すると、`controlnet[0].image` などを保存済みworkflowへ注入できます。

## プロンプトの代わりにworkflowを使う

```shell
python cp2.py prompts/prompt.yaml --api-output-dir ./outputs/txt2img-images --comfy --api-base http://localhost:8188 --image-type webp --max-number 1 --api-filename-pattern '[num]-[seed]'
```

```yaml
version: 2
methods:
  - preset: model
  - random: 0
  - cleanup: prompt
variables:
  model:
    - xd.safetesors
    - sd15.safetesors
  seed: ${=random_int()}
  prompt: ['cat is run']
  negative: ['nsfw']
command: ./workflows_apijson
```

```json
{
  "3": {
    "inputs": {
      "seed": "${seed}", // random seed(ランダムシード)
      "steps": 25,
      "cfg": 12.5,
      "sampler_name": "dpmpp_sde",
      "scheduler": "karras",
      "denoise": 1,
      "model": ["82", 2],
      "positive": ["82", 0],
      "negative": ["82", 1],
      "latent_image": ["5", 0]
    },
    "class_type": "KSampler",
    "_meta": {
      "title": "KSampler"
    }
  },
  "19": {
    // positive prompt(ポジティブプロンプト)
    "inputs": {
      "width": 4096,
      "height": 4096,
      "crop_w": 0,
      "crop_h": 0,
      "target_width": 4096,
      "target_height": 4096,
      "text_g": "${prompt}",
      "text_l": "${prompt}",
      "clip": ["23", 0]
    },
    "class_type": "CLIPTextEncodeSDXL",
    "_meta": {
      "title": "positive prompt"
    }
  },
  "20": {
    // negative prompt(ネガティブプロンプト)
    "inputs": {
      "width": 4096,
      "height": 4096,
      "crop_w": 0,
      "crop_h": 0,
      "target_width": 4096,
      "target_height": 4096,
      "text_g": "${prompt}",
      "text_l": "${prompt}",
      "clip": ["23", 0]
    },
    "class_type": "CLIPTextEncodeSDXL",
    "_meta": {
      "title": "negative prompt"
    }
  },
  // ...
  // Can save locally by setting the node id of "save_image_websocket_node" to "save_image_websocket_node"
  // Save image to websocket(画像をwebsocketに保存) の node idを"save_image_websocket_node"にするとローカルに保存可能
  "save_image_websocket_node": {
    "inputs": {
      "images": [
        "8", // node of "image"
        0
      ]
    },
    "class_type": "SaveImageWebsocket",
    "_meta": {
      "title": "SaveImageWebsocket"
    }
  }
}
```

# 既知の問題

- 入れ子の連想配列はサポートされていません
- DBクエリーは現状 SQLite のみ対応です
- 入れ子プロファイルはサポートされていません
- マルチスレッドはサポートされていません
- 配列属性には対応していません。

# V2までのTODO

## 完了

- [x] 新しいcreate prompt
- [x] ComfyUI APIに対応
  - [x] workflowチェッカー
  - [x] WebUI風workflowの作成
- [x] JSONLに対応
- [x] profileに対応
- [x] パーサーを強化
- [x] txt2imgのControlNetに対応
- [x] 属性に対応
- [x] JSONLのカテゴリークエリーに対応
- [x] WebPに対応
- [x] バックグラウンド保存に対応
- [x] サブフォルダーへの画像保存に対応
- [x] ログローテーションを修正

## TODO

- JSON、JSONL、TXT、CSVを変換するツール
- [x] ComfyUI用SD3 workflowの作成
- JSONのカテゴリークエリー
- [x] Forge APIに対応
- 引数を調整（v2.1以降）
- クラスベースのコード（v2.1以降）
- [x] ComfyUI対応を強化（img2img、hires.fix）
- [x] ComfyUI用jpg/WebP workflow保存
- img2imgのControlNetに対応（v2.1以降）
- アップスケーリングに対応（v2.1以降）
- 関数を追加（v2.1以降）
  - value_choice(variable): 変数配列から値を1つ取得

# V3までの予定

- プログラミング言語のようなパーサー
- 設定ツール
- SQLite以外のデータベースに対応
- WebUI拡張
- ComfyUIカスタムノード
- "segment anything"に対応
- civitai/huggingfaceモデルのバックグラウンドダウンロード

# V1

[READMEV1.md](READMEV1.md)を参照してください。

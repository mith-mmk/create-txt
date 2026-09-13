# Create prompt V2

Create prompt V2 is a prompt creator for stable-diffusion-webui and ComfyUI.
The current release targets SD WebUI Forge Neo and ComfyUI.

[Japanese README](README.ja.md)

## New features

- Anima support for ComfyUI
- model_profile: settings selected by model family
- ui_profile: settings selected by UI type
- checkpoint_profile: settings selected by checkpoint name

## Objective

Prompt Creator V2 builds prompt lists for AUTOMATIC1111/stable-diffusion-webui.
You can also automatically generate images by using the API.
The ComfyUI API is also supported; see [ComfyUI](#comfyui).

- A configuration file is required.
- Configuration files use YAML.
- A configuration file defines the prompt list to create.
- It can define methods, the number of prompts, prompt commands and generation settings.
- It can also define variables, arrays, commands and profiles, and can load JSON or text data.
- See the examples for details.

input.yaml

```yaml
version: 2.0 # must
options:
  output: ./outputs/v2/girls.json # output file
  json: true # output json
  number: 50 # number of prompt
methods: # random: 1  or multiple: array
  - random: 0 # random 0 is use options.number randam is generate random prompt
  - cleanup: prompt negative_prompt # clean up prompt

variables: # variables
  negative: ['nsfw, easynegative'] # If you define variables in the config, define them as an array
  actions: $json/actions.jsonl # actions
  outfits: $jsonl/outfits.json # outfits
  place: $jsonl/places.jsonl[places] # place

  eyes: $jsonl/eyes.jsonl[eyes] # ${eyes}
  hair: $jsonl/hairs.jsonl[hair] # ${hair}

command: # prompt command The content that will be output to the file
  prompt: '${eyes} ${hair} girl wearing ${outfits} is ${actions} ${place} ' # prompt command
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
  override_settings: # override settings
    CLIP_stop_at_last_layers: 2 # CLIP stop at last layers
```

jsonl(eyes.jsonl)

```jsonl
/*
  If you want write comment in jsonl, you can it.
*/
// You can write like this
{"W": 0.1, "C": ["eyes"], "V": "blue eyes"} // W C V is upper case
{"W": 0.1, "C": ["eyes"], "V": "green eyes"}
{"W": 0.1, "C": ["eyes"], "V": "black eyes"}
{"W": 0.1, "C": ["eyes"], "V": "brown eyes"}
{"W": 0.1, "C": ["eyes"], "V": ["red eyes"]}  // "V" is string or string array
```

You can write a semicolon-separated text file; categories are not supported in text mode.

eyes.txt

```text
0.1;blue eyes
0.1;green eyes
0.1;black eyes
0.1;brown eyes
0.1;red eyes
```

## How to run

```
python cp2.py input.yaml
```

Add the API options to generate images automatically.
Start WebUI with `--api` and `--listen`.

Use text output with WebUI's "Prompts from file or textbox" and JSON output when calling the API.

Example command

```
python .\cp2.py .\examples\prompts-girls.yaml
```

Example output

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

Text output can be copied and pasted into WebUI.

Use JSON output when calling the API.

```
python cp2.py input.yaml --json
```

You can also set this in the configuration file.

```yaml
options:
  json: true
```

You can run the WebUI API directly.

```
python cp2.py input.yaml --api-mode --api-base http://localhost:7860 --api-output-dir ./outputs/text-images --api-filename-pattern [num]-[seed]
```

Use `--input-json` to run from a JSON file.

```
python cp2.py --api-input-json "./outputs/examples.json" --api-output-dir ./outputs/text-images --api-filename-pattern [DATE]-[num]-[seed]
```

# Environment

- Python 3.10 or later.
- For WebUI, Forge or Forge Neo, start the server with `--api`. Enable remote access when the server is on another host.
- For ComfyUI, use its API endpoint and the `--comfy` option.

# Usage

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

The parser is still evolving. For the exact current option list, run `python cp2.py --help`.

-h, --help show this help message and exit

--append-dir APPEND_DIR
Directory containing prompt files to append.

--output OUTPUT: output directory for the prompt list.

--json: output JSON (the default is text for the WebUI prompt matrix).

--v1json: output the legacy V1 JSON format.

--profile PROFILE: select a profile in the configuration file.

--debug: enable debug mode.

--json-verbose: include verbose values in JSON.

--api-mode: call the API and force JSON output.
See the API documentation at https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API.

--api-base API_BASE: base URL used by this script, for example http://127.0.0.1:7860.

--api-output-dir API_OUTPUT_DIR
Directory for images returned by the API.

--api-input-json API_INPUT_JSON
Read direct API inputs from a JSON file.

--api-filename-pattern API_FILENAME_PATTERN
API output filename pattern (default: [num]-[seed]).

--max-number MAX_NUMBER
Override option.number in YAML mode.

--api-filename-variable
Use variables in the output filename.

--api-set-sd-model SD_MODEL
Change the SD model by filename and hash, for example "wd-v1-3.ckpt [84692140]" or 84692140.

--api-set-sd-vae VAE_FILE
Set the VAE filename, including its extension. `Automatic` is valid for WebUI; ComfyUI treats it as no explicit VAE override.

--text-encoder TEXT_ENCODER
Set the Forge/Neo text encoder module. `Automatic` keeps the server default.

--override
Override command values, for example "width=768, height=1024".

--values (-v)
Override values in YAML.
ex: "-v prefix=a,face=smile"
filename: "${prefix}-001.json" -> filename: "a-001.json"
face: ["\${face} face"] -> face: ["smile face"]

--info
Add metadata, for example "date=2022/08/19, comment=random".

--save-extend-meta
Save extended metadata for create_prompt.

--image-type
Image type: jpg or png (default: png).

--image-quality
JPEG quality (default: 80).

--debug
Debug mode.
--verbose
Verbose output.
--prompt
Output prompts only.
--json-escape
Escape multibyte characters in JSON.

--api-comfy
Use the ComfyUI API instead of the WebUI API.
--api-comfy-save: image destination for the ComfyUI API.
ui saves on the ComfyUI server, save saves locally, and both does both.
Metadata is converted to the Automatic1111 format only when save is selected.

## Compatibility

    - V2 is not compatible with V1

# Installation

    - python 3.10 and later is required

install required packages

```
pip install -r requirements.txt
```

# YAML mode

Text mode is obsolete; YAML mode creates a prompt list from a YAML file.

## Differences from V1

- Variable mode only.
- appends is obsolete; use variables and array.
  - Use variables and array instead.
- multipe and aftermultipe are obsolete.
  - Use methods instead.
- Associative arrays are supported.
- JSONL can be loaded as a list file.
- JSONL category queries are supported.
- Variables can be nested up to 10 levels; definition order does not matter.

## Methods

- random generates random prompts.
- multiple generates prompts from arrays.
- cleanup cleans prompt fields.
- default is random: 0.

```yaml
version: 2 # must
import:
  - ./add_profile.yaml # import add yaml files
options:
  output: ./outputs/v2.json
  json: true
  number: 10 # number of prompt multiple

methods: # random: 1  or multiple: array
  - preset: model # presets only choice once
  - exclude: date # exclude choice in "random", run random exclude variables will be clear
  - random: 0 # random 0 is use options.number
  - multiple: char place # array char  place
  - choice: actions # values choice before run "random" method
  - random: 0 # random use after multiple must set 0
  - creanup: prompt # clean up prompt
variables: #
  model:
    - xd.safetesors
    - sd15.safetesors
  actions:
    - standing
    - sitting
  date: jsonl/date.jsonl[animal] # jsonl file and category query

array: #
  char: [cat, dog, bird, fish] # make prompt matrix of cat, dog, bird, and fish
  place: [room, garden, park, street] # make prompt matrix of room, garden, park, and street
command: # command  workflow.json <- driect worlkflow.json setting for Comfy UI
  prompt: '${char} is ${actions} in ${place}, ${date}' # prompt command
  negative_prompt: 'negative prompt'
  seed: -1 # -1 is random seed
  width: 640 # width of image
  height: 448 # height of image
  cfg_scale: 7.5 # scale of image
  # api
```

This example generates 10 × 4 × 4 = 160 prompts because multiple uses four values from both char and place.

## Array variables

```yaml
char:
  - 0.1;cat;dog;bird;fish
cat: ${char[1]} # array is start 1, zero is not support
dog: ${char[2]}
bird: ${char[3]}
fish: ${char[4]}
```

An array variable can begin with a weight. Here char contains cat, dog, bird and fish with weight 0.1; they replace positions 1 through 4.

## Nested variables

```yaml
char:
  - ${animal}
  - ${human}
'animal': [cat, dog, bird, fish]
human: [girl, boy]
```

In this example, char is replaced by \$\{animal\} and \$\{human\}.

## Attributes and associative arrays

The reserved words "W", "C", "V", "weight", "choice", "variable" and "query" cannot be accessed directly.

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

jsonl file(beings.jsonl)

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

Issue #1: nested associative arrays are not supported.

## Loading input files

### text

```yaml
date: text/date.txt
```

This reads the text file date.txt.

```text
0.1;day
0.1;night
```

Text mode does not support queries or associative arrays.

### jsonl

```yaml
date: jsonl/date.jsonl[animal]
```

This reads date.jsonl and queries the animal category.

```jsonl
{"W":0.1, "C":["animal"], "V":"day", "animal":"cat"}
{"W":0.1, "C":["animal"], "V":"day", "animal":"dog"}
{"W":0.1, "C":["animal"], "V":"night", "animal":"bird"}
{"W":0.1, "C":["animal"], "V":"night", "animal":"fish"}
{"W":0.1, "C":["*"], "V":"moonnight", "animal":"bird"} // * is wlde card
{"W":0.1, "C":["animal","human"], "V":"night", "animal":"human"} // multiple category
{"W":0.1, "C":["insect"], "V":"night", "animal":"ant"} // not query
{"weight":0.1, "category":["insect"],  "variable":"night", "animal":"ant"} // same as above
```

"W", "C" and "V" are shortcuts for "weight", "category" and "variable". V can be an array or a string.

This format supports queries and associative arrays.

Example

```yaml
variables:
  actions:
    - standing
    - sitting
  all: jsonl/all.jsonl # all category
  date: jsonl/date.jsonl[animal] # category query
  day: ${date} # variable = ${date[1]}
  'animal': ${date["animal"]} # associative array
  beings: jsonl/date.jsonl[animal,human] # multiple category saparated by comma not support space
```

### json

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

- issue: query is not supported

### DB query

SQLite database queries are supported.

```yaml
database:
  db: sqlite3
  db_connection: db/date.sqlite3 # db connection
variables:
  date: date_items[category = `animal`]
  cat: date_items[category = `animal` and animal = `cat`]
  named: date_items[__name__ = `animals__eyes`]
```

Database rows use this schema:

```text
name, category, weight, variable, attributes(json)
```

Frequently used attributes can also be expanded into columns; `attributes` remains available as JSON.

`tools/jsonl2db.py` imports `.jsonl` files into SQLite and can recurse through directories.

```shell
python tools/jsonl2db.py ./jsonl ./db/items.sqlite3
```

When a directory is given, `__name__` is generated from its relative path.

### query suffixies add 2025/07/06

Query suffixes can be enabled with the query_suffixies option.
A query suffix selects a JSONL category suffix, so different models can use different terms.

```yaml
options:
  query_suffixies: [-xl] # enable query suffix
variables:
  date: jsonl/date.jsonl[animal] # query category animal
```

## Profiles

A profile overrides the base configuration.

```yaml
command:
  width: 512
  height: 512
  enable_hr: true
  hr_scale: 2

profiles: # override from default profile
  xl:
    command:
      width: 1024
      height: 1024
      enable_hr: false
      refiner_switch_at: 0.7
  pory:
    load_profile: [xl] # before Load profile xl
    command:
      override_settings: # WebUISetting
        CLIP_stop_at_last_layers: 2 # CLIP
        emphasis: 'No norm' #
        override_settings_restore_afterwards: true #
```

Run a profile.

```
python cp2.py --profile xl input.yaml
# width = 512, height = 512, enable_hr = true, hr_scale = 2

python cp2.py --profile xl input.yaml
# width = 1024, height = 1024, enable_hr = false, refiner_switch_at = 0.7
```

load_profile loads another profile from a profile entry.

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

This example loads animal first and applies xl last.
load_profile cannot be nested.

## Forge Neo and conditional profiles

Forge Neo supports the WebUI-compatible txt2img and img2img APIs. Start the
server with --api. The default connection is http://localhost:7860 and can be
changed with --api-base. The supported static-image families follow the
[Forge Neo model list](https://github.com/Haoming02/sd-webui-forge-classic/blob/neo/README.md).
Video models, PiD/upscalers, VAEs and text encoders are not model families.
SD2 and SD3 are unavailable on Neo; existing WebUI and ComfyUI support remains separate.

### Application order

**Base YAML -> regular profile -> model_profile (parent -> child) -> checkpoint_profile -> ui_profile -> CLI overrides**

model_profile, checkpoint_profile and ui_profile are top-level mappings. Each
entry accepts the same fields as a regular profile, including command, options,
variables, array, methods and load_profile. Dictionaries are merged recursively;
arrays and scalars replace previous values. Empty entries do nothing.
load_profile loads an existing entry from profiles one level before the entry.
base_yaml and import are processed in their existing order.

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

Use model_profile for family and version settings, and checkpoint_profile for
settings specific to a selected checkpoint. Checkpoint keys are matched against
title, filename, model_name, hash and sha256. Matching is case-insensitive,
normalizes path separators and Forge hash suffixes, and accepts a full path,
basename, stem, or a model name without its extension. Multiple matches at the
same priority are rejected as ambiguous. An unknown checkpoint has no matching
entry and leaves the profile unchanged.

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

When options.model_type or options.ui_type is omitted, the type is detected
automatically. The --model-type and --ui-type CLI options take precedence over
YAML. UI types are webui, forge, neo and comfy. Neo does not inherit
ui_profile.forge. A type selection alone does not send an API request:
use --api-mode for WebUI-compatible APIs and --comfy for ComfyUI. Conflicting
ComfyUI flags and UI types are errors.

Detection and conditional profile application happen once per YAML run, after
the regular profile and before variable expansion or methods. checkpoint_profile
is resolved once for the selected checkpoint. A type or model changed by a
conditional profile does not trigger another resolution. Run jobs with different
model families separately.

An explicitly selected CLI or YAML checkpoint is preferred. Without one, the
current API model is used. Detection uses available metadata and model names or
paths; a UI preset alone is not evidence. Unknown families produce a warning
and skip model_profile, while known ancestors can still be applied when the
family is only partially identified. Offline generation uses explicit local
information without contacting the API. The log records the detected type,
evidence and applied profiles.

### Model families

Derived families inherit the settings of their parent in the order shown.

| Common key | Derived keys |
| --- | --- |
| sd15 | SD1.5 |
| sdxl | illustrius -> noobai, pony, mugen |
| flux | flux-dev, flux-schnell, flux-krea, flux-kontext |
| flux2-klein | flux2-klein-4b, flux2-klein-9b |
| chroma | chroma-hd |
| lumina | neta-lumina, netayume-lumina |
| qwen-image | qwen-image-edit |
| z-image | z-image-turbo |
| anima | anima_2b, anima_2.9b, anima_3.8b, anima-edit |
| ernie-image | ernie-image-turbo |
| krea2 | krea2-turbo, krea2-raw, krea2-edit |

Anima version keys also have -edit variants. For example,
anima_2.9b-edit applies anima -> anima_2.9b -> anima-edit ->
anima_2.9b-edit. krea2-turbo-edit and krea2-raw-edit similarly include the
common Edit profile. If the Anima version is unknown, only anima is applied.

Aliases include illustrious -> illustrius, sd1 and sd1.5 -> sd15,
flux.1 and flux1 -> flux, flux.1-kontext -> flux-kontext,
flux.2-klein -> flux2-klein, chroma1-hd -> chroma-hd,
lumina-image-2.0 -> lumina, krea-2 -> krea2, and anima_2.0b -> anima_2b.
Defining an alias and its canonical key twice is an error. sd2 and sd35
(aliases sd3 and sd3.5) remain available for existing backends.

### Image inputs and additional modules

| YAML option | CLI | Purpose |
| --- | --- | --- |
| image | --image | Initial img2img image |
| mask | --mask | img2img mask |
| reference_images (list) | --reference-image (repeatable) | Neo edit references |
| reference_max_size | — | Maximum reference edge; default 1024 |

Relative paths are resolved from the working directory. Images are converted
to Base64 by the client. command.init_images and command.mask accept paths or
existing Base64 values. Initial images require --api-type img2img. Reference
images work for both t2i and i2i and are sent in order to Neo's ImageStitch
Integrated script. Combining reference_images with the same alwayson_scripts
entry is an error. Existing file and directory img2img inputs remain supported.

For Neo and Forge, use options.vae and options.text_encoder. Each accepts a
list or comma-separated string. options.sd_vae remains as a compatibility
alias. The CLI names are --api-set-sd-vae and --text-encoder.
command.override_settings.forge_additional_modules can specify modules directly.
Names are resolved through the list API; missing or ambiguous names are errors.
Automatic or omitted modules preserve the current selection, while [] explicitly
clears it. Set override_settings_restore_afterwards: true to restore settings.

Normal Anima, Klein and Krea img2img disables edit mode. Reference images or an
Edit model type enables it. Explicit override_settings are respected. Anima
Edit and Krea 2 Edit require their dedicated LoRA; the tool does not download it.
Missing server capabilities are reported before sending a request.

Normal generation example: examples/neo-txt2img.yaml

~~~sh
python cp2.py examples/neo-txt2img.yaml --api-mode
python cp2.py examples/neo-txt2img.yaml --api-mode --api-type img2img --image input.png --mask mask.png
~~~

Edit generation example: examples/neo-edit.yaml

~~~sh
python cp2.py examples/neo-edit.yaml --api-mode --reference-image first.png --reference-image second.png
~~~

Use checkpoint and module names that exist in your installation. Runner profiles
also accept model_type, ui_type, image, mask and reference_images. An img2img
YAML file is selected with the runner profile input field. API failures, zero
images and save failures are returned as failures.

Use examples/test_model_switch.py and examples/test-model-switch.ps1 to check
installed checkpoint switching. Pass each checkpoint explicitly because names
differ between installations.

~~~powershell
pwsh ./examples/test-model-switch.ps1 -AnimaModel "anima_2b.safetensors" -IllustriousModel "illustrious.safetensors" -PonyModel "pony.safetensors" -DryRun
~~~

Remove -DryRun to switch checkpoints in sequence. Add -Generate to run one
t2i image after each switch. DryRun checks arguments and order without using
the test server.
## Parser

Expressions inside \$\{ \} can be parsed.

Example

```yaml
seed: ${=random_int()} # random seed
width: ${=int(${size}) * 2} # width = size * 2
```

### Parser tester

The runnable YAML sample is [examples/formula.yaml](examples/formula.yaml). From the repository root, run it to save the expanded JSON. This does not call an image-generation API.

~~~sh
python cp2.py examples/formula.yaml --output outputs/formula.json
~~~

The expected output is [examples/formula.expected.json](examples/formula.expected.json). It covers arithmetic precedence, variables, `>=` and `<=`, negative function arguments, string repetition and `split`.

When calculating a YAML string variable as a number, convert it with `int(size)` as shown in the sample.

Regression tests and the sample CLI/JSON output test:

~~~sh
python -m pytest tests/test_formula_regressions.py tests/test_formula_sample.py tests/parser_test.py tests/prompt_v2_test.py -q
~~~

### Functions

Boolean values are not supported; results are 0 (false) or 1 (true).

Function arguments such as str1 and str2 are strings; x, y and similar arguments are numbers.

- chained("objects", 0.8, 3): create a chained string. The first value is the threshold and the last value is the maximum count.
  - ex. chained("objects", 0.8, 3) -> \$\{objects} or \$\{objects}, \$\{object} or \$\{objects},\$\{object},\$\{object}
- choice("objects"): choose one value from objects.
  - choice("objects") -> \$\{objects}
- contains(str1, str2, ...): test whether str1 contains every listed value.
  - contains("abc", "a", "b") -> 1, contain("abc", "e", "f") -> 0
- attribute("objects", str2): get an attribute of the objects variable.
  - attribute("objects", "size") -> \$\{objects["size"]}
- choice_index("objects", query, number): choose an object index using a query value from 0.0 to 1.0.
  - choice_index("objects", query, 1) -> \$\{objects[1]}
- choice_attribute("objects", query, attribute): choose an attribute from objects.
  - choice_attribute("objects", query, "size") -> \$\{objects["size"]}
- value("objects", query): get the value of objects.
  - value("objects", query) -> \$\{objects}
- replace(str1, str2, str3): replace str2 with str3 in str1.
  - replace("abc", "a", "b") -> "bbc"
- split(str1, str2): split str1 at str2.
  - split("a,b,c", ",") -> ["a", "b", "c"]
- upper(str1): convert to uppercase.
  - upper("abc") -> "ABC"
- lower(str1): convert to lowercase.
  - lower("ABC") -> "abc"
- if(condition, truecase, falsecase): return truecase when condition is true, otherwise falsecase.
  - if(1, "true", "false") -> "true", if(0, "true", "false") -> "false"
- pow(x, y): calculate x^y.
- sqrt(x): calculate the square root.
- abs(x): calculate the absolute value.
- ceil(x): round up.
- floor(x): round down.
- round(x): round to the nearest value.
- trunc(x): truncate the value.
- int(str1): convert a string to an integer.
- float(str1): convert a string to a floating-point number.
- str(x): convert a number to a string.
- len(str1): return the string length.
- max(x, y, ...), max(str1, str2, ...): return the maximum value.
- min(x, y, ...), min(str1, str2, ...): return the minimum value.
- not(condition): convert 0 to 1 and 1 to 0.
- and(condition1, condition2): logical AND.
- or(condition1, condition2): logical OR.
- match(str1, str2): test whether str1 matches str2.
  - match("abc", "a") -> 1, match("abc", "d") -> 0
- substring(str1, start, end): return a substring of str1.
  - substring("abc", 1, 2) -> "b"
- random(start, end): generate a random integer or floating-point number.
- random_int(): generate an integer from 0 to 2^64 - 1.
- random_float(): generate a floating-point number from 0 to 1.
- random_string(len): generate a random string of len characters.
- uuid(): generate a random UUID.
- time(): return the current time.
- date(): return the current date.
- datetime(): return the current date and time.
- timestamp(): return the current timestamp.
- year(): return the current year.
- month(): return the current month.
- day(): return the current day.
- hour(): return the current hour.
- minute(): return the current minute.
- second(): return the current second.
- weekday(): return the current weekday.
- week(): return the current week.

## Saving files

- Saving a file writes the prompt list.
- The default filename pattern is [num]-[seed].

### Filename patterns

- /: folder separator.
- [num]: image number (five digits by default; change it with --num-length).
- [seed]: random seed.
- \[shortdate\]: current date YYMMDD
- \[DATE\]: current date YYYYMMDD
- \[date\]: current date YYYY-MM-DD
- \[datetime\]: current datetime YYYYMMDDHHMMSS
- \[shortyear\]: current year YY
- \[year\]: current year YYYY
- \[month\]: current month MM
- \[day\]: current day DD
- \[hour\]: current hour HH
- \[min\]: current minute MM
- \[sec\]: current second SS
- [var:variable]: variable value.
- [var:variable:attribute]: an attribute of a variable.
- [var:variable(index)]: an indexed variable value.
- [info:key]: metadata value.

# ComfyUI

ComfyUI options are described below.

- Use `--comfy` for the ComfyUI API; `--api-comfy` is deprecated.
- The tool can create a workflow for running a prompt in ComfyUI.
- txt2img and img2img are supported. mask is treated as img2img + mask. hires.fix is not auto-generated.

- Auto workflow families: `sd15`, `sdxl`, `sd35`, `flux`, `anima`

- You can also load workflow directly. Save the workflow for the API in ComfyUI, or use YAML DSL with `comfyui:` / `workflow:`.

- Local save converts metadata to Automatic1111-like infotext and filename replacers such as `[seed]`, `[var:name]`, `[var:name:attr]`.

- Compatibility helpers cover WebUI fields such as scheduler and model filenames.
- When using WebSocket, the SaveImageWebsocket node ID must be `save_image_websocket_node`.
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
        "title": "WebSocket"
      }
    },
  ```

## ComfyUI options

- `--comfy-family`: select workflow family `sd15|sdxl|sd35|flux|anima`
- `--comfy-mode`: `txt2img|img2img|interrogate`
- `--comfy-template`: use saved workflow / template file instead of pure auto-generated graph
- `--comfy-image`: img2img input image
- `--comfy-mask`: img2img mask image
- `--comfy-controlnet`: append ControlNet settings. accepts JSON or `key=value,key=value`
- `--comfy-lora`: append LoRA chain. format `name[:weight][@positive|negative|both]`
- `--comfy-node`: override node definitions. format `role.field=value` or `role.inputs.key=value`

## Run a workflow directly

```shell
python cp2.py --api-output-dir ./outputs/txt2img-images --comfy --api-base http://localhost:8188 --image-type webp --api-input-json ./workflow_api.json
```

## Run img2img directly (ComfyUI)

```shell
python cp2.py prompt.yaml --comfy --comfy-mode img2img --comfy-family flux --comfy-image ./inputs/src.png --comfy-mask ./inputs/mask.png --api-base http://localhost:8188
```

## Anima template example

The practical `anima` example is based on a saved workflow like `UNETLoader -> ModelSamplingAuraFlow -> KSampler`, plus `CLIPLoader` and `VAELoader`.

- YAML example: [examples/anima-template.yaml](/c:/Users/misir/OneDrive/source/python/create-txt/examples/anima-template.yaml)
- Workflow JSON example: [examples/anima-template-api.json](/c:/Users/misir/OneDrive/source/python/create-txt/examples/anima-template-api.json)

Example command:

```shell
python cp2.py ./examples/anima-template.yaml --comfy --api-base http://localhost:8188 --api-output-dir ./outputs/anima-example
```

`_controlnet_slots` is optional. If present, `controlnet[0].image` etc. can be injected into the saved workflow.

## Use a workflow instead of a prompt

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
      "seed": "${seed}", // random seed
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
    // positive prompt
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
    // negative prompt
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
  // Save image to websocket  node id"save_image_websocket_node"
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

# Known issues

- issue #1 nseted associative array is not supported
- issue #2 SQLite only for DB query right now
- issue #3 nested profile is not supported
- issue #4 multi thread is not supported
- Array attributes are not supported in all contexts.

# TODO for V2

## Completed

- [x] New prompt creator
- [x] ComfyUI API support
  - [x] Workflow checker
  - [x] WebUI-like workflow creation
- [x] JSONL support
- [x] Profile support
- [x] More powerful parser
- [x] ControlNet support for txt2img
- [x] Attribute support
- [x] JSONL category queries
- [x] WebP support
- [x] Background image saving
- [x] Save images in subfolders
- [x] Fixed log rotation

## todo

- Convert JSON, JSONL, TXT and CSV files
- [x] Create an SD3 workflow for ComfyUI
- JSON category queries
- [x] Forge API support (the API still has known bugs)
- Adjust arguments and profile arguments (v2.1 or later)
- Class-based code (v2.1 or later)
- [x] More ComfyUI support, including img2img and hires.fix (v2.1 or later)
- [x] Save jpg/WebP workflows for ComfyUI (v2.1 or later)
- ControlNet support for img2img (v2.1 or later)
- Upscaling support (v2.1 or later)
- More functions (v2.1 or later)
  - value_choice(variable): get one value from a variable array

# Planned for V3

- A programming-language-like parser
- Configuration tools
- Database backends other than SQLite
- WebUI extension
- ComfyUI custom nodes
- Support for "segment anything"
- Background downloads from Civitai and Hugging Face

# V1

See [READMEV1.md](READMEV1.md).

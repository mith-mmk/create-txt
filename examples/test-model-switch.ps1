param(
    [string]$ApiBase = "http://localhost:7860",
    [string]$AnimaModel = "",
    [string]$IllustriousModel = "",
    [string]$PonyModel = "",
    [string]$Vae = "Automatic",
    [string]$TextEncoder = "Automatic",
    [switch]$Generate,
    [switch]$DryRun
)

$scriptPath = Join-Path $PSScriptRoot "test_model_switch.py"
$arguments = @("--api-base", $ApiBase, "--vae", $Vae, "--text-encoder", $TextEncoder)
if ($AnimaModel) { $arguments += @("--model", "anima=$AnimaModel") }
if ($IllustriousModel) { $arguments += @("--model", "illustrious=$IllustriousModel") }
if ($PonyModel) { $arguments += @("--model", "pony=$PonyModel") }
if ($Generate) { $arguments += "--generate" }
if ($DryRun) { $arguments += "--dry-run" }

& python $scriptPath @arguments
exit $LASTEXITCODE

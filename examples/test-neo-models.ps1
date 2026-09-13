param(
    [string]$Config = "$PSScriptRoot\neo-real-models.yaml",
    [string]$ApiBase = "",
    [string]$OutputDir = "",
    [string[]]$Case = @(),
    [switch]$Generate,
    [switch]$DryRun,
    [switch]$ContinueOnError
)

$scriptPath = Join-Path $PSScriptRoot "test_neo_models.py"
$arguments = @($Config)
if ($ApiBase) { $arguments += @("--api-base", $ApiBase) }
if ($OutputDir) { $arguments += @("--output-dir", $OutputDir) }
foreach ($name in $Case) { $arguments += @("--case", $name) }
if ($Generate) { $arguments += "--generate" }
if ($DryRun) { $arguments += "--dry-run" }
if ($ContinueOnError) { $arguments += "--continue-on-error" }

& python $scriptPath @arguments
exit $LASTEXITCODE

param([switch]$CheckOnly, [string]$Message = 'Update NAU88C22 APM demo')
$ErrorActionPreference = 'Stop'
$arguments = @('-B', (Join-Path $PSScriptRoot 'github_push.py'), '--message', $Message)
if ($CheckOnly) { $arguments += '--check-only' }
& python @arguments
exit $LASTEXITCODE

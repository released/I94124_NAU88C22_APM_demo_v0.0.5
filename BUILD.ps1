param(
    [ValidateSet('All', 'I2C', 'USB')]
    [string]$Target = 'All',
    [string]$UV4 = 'C:\Keil_v5\UV4\UV4.exe'
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'scripts\verify_source_encoding.ps1')
if (-not (Test-Path -LiteralPath $UV4 -PathType Leaf)) { throw "Keil not found: $UV4" }
$folders = @()
if ($Target -in @('All', 'I2C')) { $folders += 'Colsonic_16k_I2S_I2C' }
if ($Target -in @('All', 'USB')) { $folders += 'Colsonic_16k_USB_UAC' }
foreach ($folder in $folders) {
    $dir = Join-Path $PSScriptRoot "SampleCode\Template\$folder\KEIL"
    $projects = @(Get-ChildItem -LiteralPath $dir -File -Filter '*.uvprojx')
    if ($projects.Count -ne 1) { throw "Expected one project in $dir" }
    $log = Join-Path $dir 'build.log'
    $args = @('-r', ('"' + $projects[0].FullName + '"'), '-j0', '-sg', '-o', ('"' + $log + '"'))
    $process = Start-Process -FilePath $UV4 -ArgumentList $args -WindowStyle Hidden -PassThru -Wait
    Get-Content -LiteralPath $log
    if ($process.ExitCode -ne 0) { throw "Keil exit code $($process.ExitCode): $log" }
    # Some device/pack failures return zero without producing a firmware image.
    if ([IO.File]::ReadAllText($log) -notmatch '0 Error\(s\), 0 Warning\(s\)') {
        throw "Keil did not report a successful target build: $log"
    }
}
& (Join-Path $PSScriptRoot 'VERIFY.ps1') -Target $Target

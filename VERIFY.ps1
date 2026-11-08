param(
    [ValidateSet('All', 'I2C', 'USB')]
    [string]$Target = 'All'
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'scripts\verify_source_encoding.ps1')
$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot) + '\'
$libHash = '4505A89E1D13D924057DCD8C660337C7AC8BAE8DD9F07BCDD10057308DC9342E'
$dataHash = 'EC533A82819A0940C44B879BD0A16485A5D4699065F9781F192600DAD2B62AF6'
$folders = @()
if ($Target -in @('All', 'I2C')) { $folders += 'Colsonic_16k_I2S_I2C' }
if ($Target -in @('All', 'USB')) { $folders += 'Colsonic_16k_USB_UAC' }
foreach ($folder in $folders) {
    $source = Join-Path $PSScriptRoot "SampleCode\Template\$folder"
    $keil = Join-Path $source 'KEIL'
    $project = @(Get-ChildItem -LiteralPath $keil -File -Filter '*.uvprojx')
    if ($project.Count -ne 1) { throw "Expected one Keil project: $folder" }
    [xml]$xml = Get-Content -LiteralPath $project[0].FullName
    foreach ($node in $xml.SelectNodes('//FilePath')) {
        $path = [IO.Path]::GetFullPath((Join-Path $keil $node.InnerText))
        if (-not $path.StartsWith($projectRoot, [StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Source reference is missing or outside this project: $path"
        }
    }
    foreach ($node in $xml.SelectNodes('//IncludePath')) {
        foreach ($inc in ($node.InnerText -split ';' | Where-Object { $_ })) {
            $path = [IO.Path]::GetFullPath((Join-Path $keil $inc))
            if (-not $path.StartsWith($projectRoot, [StringComparison]::OrdinalIgnoreCase) -or
                -not (Test-Path -LiteralPath $path -PathType Container)) {
                throw "Invalid include directory: $path"
            }
        }
    }
    $lib = Join-Path $source 'Colsonic\colsonic_apm_v0.0.5_20260213_0_0.lib'
    $data = Join-Path $source 'Colsonic\colsonicdata.bin'
    if ((Get-FileHash -LiteralPath $lib -Algorithm SHA256).Hash -ne $libHash) { throw 'Library hash mismatch' }
    if ((Get-FileHash -LiteralPath $data -Algorithm SHA256).Hash -ne $dataHash) { throw 'Parameter data hash mismatch' }
    $output = $xml.Project.Targets.Target.TargetOption.TargetCommonOption.OutputName
    $bin = Join-Path $keil "obj\$output.bin"
    $hex = Join-Path $keil "obj\$output.hex"
    $map = [IO.File]::ReadAllText((Join-Path $keil "lst\$output.map"))
    $log = [IO.File]::ReadAllText((Join-Path $keil 'build.log'))
    if ($log -notmatch '0 Error\(s\), 0 Warning\(s\)') { throw "Build has errors/warnings: $folder" }
    if (-not (Test-Path -LiteralPath $bin -PathType Leaf)) { throw "Expected a single BIN file: $bin" }
    $binary = Get-Item -LiteralPath $bin
    if ($binary.Length -le 0 -or $binary.Length -gt 0x80000) { throw 'BIN exceeds 512 KB flash' }
    if ($map -notmatch 'APM_MemPool\s+0x[0-9a-fA-F]+\s+Data\s+87040\b') { throw 'Incorrect APM pool size' }
    if ($map -notmatch 'Colsonic_ns_set\s+0x[0-9a-fA-F]+\s+Thumb Code') { throw 'NS API is not linked' }
    if ([regex]::Matches($map, 'Load Region ').Count -ne 1) { throw 'Expected one flash load region' }
    foreach ($region in [regex]::Matches($map, 'Execution Region ([^\r\n]+)\(Exec base: 0x([0-9a-fA-F]+), Load base: 0x[0-9a-fA-F]+, Size: 0x([0-9a-fA-F]+)')) {
        $address = [Convert]::ToUInt64($region.Groups[2].Value, 16)
        $size = [Convert]::ToUInt64($region.Groups[3].Value, 16)
        if ($address -ge 0x20000000 -and ($address + $size) -gt 0x20030000) { throw 'SRAM region exceeds 192 KB' }
        if ($address -lt 0x20000000 -and ($address + $size) -gt 0x80000) { throw 'Flash region exceeds 512 KB' }
    }
    # Verify Intel HEX checksums and reject any payload outside APROM.
    $upper = [uint64]0
    $payloadBytes = 0
    $eofSeen = $false
    foreach ($line in Get-Content -LiteralPath $hex) {
        if ($line -notmatch '^:[0-9a-fA-F]+$') { throw 'Invalid HEX record' }
        $bytes = @()
        for ($i = 1; $i -lt $line.Length; $i += 2) { $bytes += [Convert]::ToInt32($line.Substring($i, 2), 16) }
        if ($bytes.Count -ne $bytes[0] + 5 -or (($bytes | Measure-Object -Sum).Sum % 256) -ne 0) { throw 'HEX length/checksum failure' }
        $type = $bytes[3]
        if ($type -eq 4) { $upper = [uint64](($bytes[4] * 256 + $bytes[5]) * 65536) }
        elseif ($type -eq 2) { $upper = [uint64](($bytes[4] * 256 + $bytes[5]) * 16) }
        elseif ($type -eq 0) {
            $address = $upper + $bytes[1] * 256 + $bytes[2]
            if (($address + $bytes[0]) -gt 0x80000) { throw 'HEX payload outside APROM' }
            $payloadBytes += $bytes[0]
        }
        elseif ($type -eq 1) { $eofSeen = $true }
        elseif ($type -notin @(3, 5)) { throw "Unsupported HEX record type: $type" }
    }
    if (-not $eofSeen -or $payloadBytes -eq 0) { throw 'HEX is empty or incomplete' }
    [PSCustomObject]@{
        Target = $output
        BINBytes = $binary.Length
        HEXPayloadBytes = $payloadBytes
        BINSHA256 = (Get-FileHash -LiteralPath $bin -Algorithm SHA256).Hash
        Result = 'PASS'
    }
}
& python -B (Join-Path $PSScriptRoot 'scripts\verify_apm_settings.py') -Target $Target
if ($LASTEXITCODE -ne 0) { throw 'NS preset or linked stack verification failed.' }

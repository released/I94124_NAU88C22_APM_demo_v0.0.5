param([Parameter(Mandatory=$true)][string]$ManifestPath, [switch]$Apply)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd('\')
function Assert-LocalPath([string]$path, [string]$boundary) {
    $full = [IO.Path]::GetFullPath($path)
    if (-not $full.StartsWith(($boundary.TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Cleanup path escaped the selected project boundary.'
    }
    $cursor = $full
    while ($cursor) {
        if ((Test-Path -LiteralPath $cursor) -and
            ((Get-Item -Force -LiteralPath $cursor).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Cleanup refuses reparse paths.'
        }
        $cursor = [IO.Path]::GetDirectoryName($cursor)
    }
    return $full
}
$manifestFile = Assert-LocalPath ([IO.Path]::GetFullPath($ManifestPath)) (Join-Path $root 'verification\docs_review')
$manifest = [IO.File]::ReadAllText($manifestFile) | ConvertFrom-Json
if ($manifest.schema -ne 1 -or $manifest.project_root -ine $root -or
    $manifest.producer -ne 'Keil UV4 rebuild / Arm Compiler 6.22') { throw 'Unexpected cleanup manifest identity.' }
$allowed = @{}
foreach ($folder in @('Colsonic_16k_USB_UAC','Colsonic_16k_I2S_I2C')) {
    $keil = Join-Path $root ('SampleCode\Template\' + $folder + '\KEIL')
    $project = @(Get-ChildItem -LiteralPath $keil -Filter '*.uvprojx' -File)
    if ($project.Count -ne 1) { throw 'Ambiguous Keil project.' }
    [xml]$xml = [IO.File]::ReadAllText($project[0].FullName)
    $target = $xml.Project.Targets.Target
    $output = [string]$target.TargetOption.TargetCommonOption.OutputName
    foreach ($entry in $target.Groups.Group.Files.File) {
        if ([string]$entry.FileType -in @('1','2')) {
            $stem = [IO.Path]::GetFileNameWithoutExtension([string]$entry.FileName)
            foreach ($extension in @('.o','.d','.crf')) { $allowed[(Join-Path $keil ('obj\'+$stem+$extension)).ToLowerInvariant()] = 'compiler' }
        }
    }
    $allowed[(Join-Path $keil ('obj\'+$project[0].BaseName+'_'+[string]$target.TargetName+'.dep')).ToLowerInvariant()] = 'compiler'
    # Only the exact dump produced by this rebuild is eligible as disposable evidence.
    $allowed[(Join-Path $keil ('obj\'+$output+'.txt')).ToLowerInvariant()] = 'post-build-disassembly'
}
foreach ($process in @(Get-CimInstance Win32_Process -Filter "Name='armclang.exe' OR Name='armlink.exe' OR Name='fromelf.exe'")) {
    if (-not $process.CommandLine -or $process.CommandLine.IndexOf($root,[StringComparison]::OrdinalIgnoreCase) -ge 0) {
        throw 'A possibly active compiler/inspection worker requires review.'
    }
}
$seen = @{}
[long]$bytes = 0
foreach ($entry in @($manifest.files) + @($manifest.preserve)) {
    $path = Assert-LocalPath (Join-Path $root $entry.path) $root
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
        (Get-Item -LiteralPath $path).Length -ne $entry.bytes -or
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ine $entry.sha256) { throw 'Manifest file identity changed.' }
}
foreach ($entry in $manifest.files) {
    $path = [IO.Path]::GetFullPath((Join-Path $root $entry.path))
    $key = $path.ToLowerInvariant()
    if (-not $allowed.ContainsKey($key) -or $allowed[$key] -cne $entry.kind -or $seen.ContainsKey($key)) { throw 'Unapproved or duplicate cleanup candidate.' }
    $seen[$key] = $true
    $bytes += $entry.bytes
}
if ($Apply) {
    foreach ($entry in $manifest.files) {
        $path = Assert-LocalPath (Join-Path $root $entry.path) $root
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ine $entry.sha256) { throw 'Candidate changed after preflight.' }
        Remove-Item -LiteralPath $path -ErrorAction Stop
        if (Test-Path -LiteralPath $path) { throw 'Candidate removal incomplete.' }
    }
}
[pscustomobject]@{ Files=$manifest.files.Count; Bytes=$bytes; Removed=[bool]$Apply; Manifest=$manifestFile }

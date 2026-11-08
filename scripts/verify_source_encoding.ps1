param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\', '/')
if (-not (Test-Path -LiteralPath $root -PathType Container)) {
    throw "Project directory not found: $root"
}
$extensions = @('.c', '.h', '.s', '.sct', '.inc')
$files = @(Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object {
    $relative = $_.FullName.Substring($root.Length + 1).Replace('\', '/')
    $_.Extension.ToLowerInvariant() -in $extensions -and
        $relative -notmatch '(^|/)(verification|obj|lst|Objects|Listings|node_modules|\.git)(/|$)'
})
if ($files.Count -eq 0) { throw 'No source files found for the ASCII encoding check.' }
$ascii = [Text.Encoding]::GetEncoding(
    'us-ascii', [Text.EncoderFallback]::ExceptionFallback,
    [Text.DecoderFallback]::ExceptionFallback)
$failures = New-Object 'System.Collections.Generic.List[string]'
foreach ($file in $files) {
    $relative = $file.FullName.Substring($root.Length + 1)
    $bytes = [IO.File]::ReadAllBytes($file.FullName)
    if ([Array]::IndexOf($bytes, [byte]0) -ge 0) {
        $failures.Add("$relative : NUL byte found; use ASCII source without a BOM.")
        continue
    }
    try { $null = $ascii.GetCharCount($bytes) }
    catch {
        $failures.Add("$relative : non-ASCII bytes found; use English ASCII comments without a BOM.")
    }
}
if ($failures.Count -ne 0) {
    throw ('Source encoding check failed:' + [Environment]::NewLine +
        ($failures -join [Environment]::NewLine))
}
Write-Host ("PASS: ASCII source encoding, {0} files; no editor code page required." -f $files.Count)

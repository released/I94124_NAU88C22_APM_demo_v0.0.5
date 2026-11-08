param()
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$vswhere = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path -LiteralPath $vswhere)) { throw 'MSVC Build Tools / vswhere is required for this host test.' }
$compiler = @(& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find 'VC\Tools\MSVC\**\bin\Hostx64\x64\cl.exe')[0]
if (-not $compiler) { throw 'MSVC C compiler not found.' }
$vcRoot = (Get-Item -LiteralPath $compiler).Directory.Parent.Parent.Parent.FullName
$sdkRoot = 'C:\Program Files (x86)\Windows Kits\10'
$sdkVersion = (Get-ChildItem -LiteralPath (Join-Path $sdkRoot 'Include') -Directory | Sort-Object Name -Descending | Select-Object -First 1).Name
$scratch = Join-Path $projectRoot 'verification\channel_tests'
New-Item -ItemType Directory -Path $scratch -Force | Out-Null
function Get-WorkFunction([string]$file, [string]$name) {
    $source = [IO.File]::ReadAllText($file)
    $match = [regex]::Match($source, 'void Colsonic_Work_Handle\s*\(void\)\s*\{')
    if (-not $match.Success) { throw "Processing function not found: $file" }
    $depth = 0
    $stop = -1
    for ($i = $source.IndexOf('{', $match.Index); $i -lt $source.Length; $i++) {
        if ($source[$i] -eq '{') { $depth++ }
        if ($source[$i] -eq '}') { $depth--; if ($depth -eq 0) { $stop = $i + 1; break } }
    }
    if ($stop -lt 0) { throw "Unbalanced processing function: $file" }
    $source.Substring($match.Index, $stop - $match.Index).Replace('Colsonic_Work_Handle', $name)
}
$i2c = Join-Path $projectRoot 'SampleCode\Template\Colsonic_16k_I2S_I2C\Util\misc.c'
$usb = Join-Path $projectRoot 'SampleCode\Template\Colsonic_16k_USB_UAC\Util\misc.c'
[IO.File]::WriteAllText((Join-Path $scratch 'work_i2c.inc'), (Get-WorkFunction $i2c 'WorkI2C'))
[IO.File]::WriteAllText((Join-Path $scratch 'work_usb.inc'), (Get-WorkFunction $usb 'WorkUSB'))
$usbStruct = [IO.File]::ReadAllText((Join-Path $projectRoot 'SampleCode\Template\Colsonic_16k_USB_UAC\Util\data_handler.h'))
if ([IO.File]::ReadAllText($usb) -match 'bAlgByPass' -or $usbStruct -match 'bAlgByPass') { throw 'USB bypass code/field must be absent.' }
$exe = Join-Path $scratch 'channel_test.exe'
$compileArgs = @('/nologo', '/TC', '/W4', '/WX', '/MT',
    ('/I' + (Join-Path $projectRoot 'SampleCode\Template')), ('/I' + $scratch),
    ('/I' + (Join-Path $vcRoot 'include')),
    ('/I' + (Join-Path $sdkRoot "Include\$sdkVersion\ucrt")),
    ('/I' + (Join-Path $sdkRoot "Include\$sdkVersion\shared")),
    ('/I' + (Join-Path $sdkRoot "Include\$sdkVersion\um")),
    ('/Fo' + (Join-Path $scratch 'channel_test.obj')), ('/Fe' + $exe),
    (Join-Path $PSScriptRoot 'channel_test.c'), '/link',
    ('/LIBPATH:' + (Join-Path $vcRoot 'lib\x64')),
    ('/LIBPATH:' + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x64")),
    ('/LIBPATH:' + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x64")))
& $compiler @compileArgs
if ($LASTEXITCODE -ne 0) { throw "Host C test compilation failed: $LASTEXITCODE" }
& $exe
if ($LASTEXITCODE -ne 0) { throw "Host C packing test failed: $LASTEXITCODE" }

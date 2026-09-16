# Builds src-tauri\python-<arch>\: python.org embeddable CPython, backend .py files, ffmpeg, app-local VC++ runtime,
# and wheels for that arch (pip download --platform, no PyInstaller). Run from any directory.
param([Parameter(Mandatory = $true)][ValidateSet('arm64', 'x64')][string]$Arch)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'  # PS 5.1 progress bars make Invoke-WebRequest / Expand-Archive very slow
$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root "src-tauri\python-$Arch"
$cache = Join-Path $root "src-tauri\target\python-cache"
$version = '3.12.10'
$platform = @{ arm64 = 'win_arm64'; x64 = 'win_amd64' }[$Arch]
$embed = @{ arm64 = 'arm64'; x64 = 'amd64' }[$Arch]
$hostPython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $hostPython)) { throw 'Run setup.cmd first (the build uses .venv''s pip).' }
if (-not (Test-Path (Join-Path $root 'tools\ffmpeg.exe'))) { throw 'tools\ffmpeg.exe is missing: run setup.cmd first.' }

New-Item -ItemType Directory -Force $cache | Out-Null
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force $out | Out-Null

$zip = Join-Path $cache "python-$version-embed-$embed.zip"
if (-not (Test-Path $zip)) {
    Invoke-WebRequest "https://www.python.org/ftp/python/$version/python-$version-embed-$embed.zip" -OutFile "$zip.part"
    Move-Item "$zip.part" $zip
}
Expand-Archive -LiteralPath $zip -DestinationPath $out
# '.' puts the backend modules on sys.path (an embeddable build ignores the script dir and PYTHONPATH).
[IO.File]::WriteAllText((Join-Path $out 'python312._pth'), "python312.zip`r`n.`r`nLib\site-packages`r`n")

function Add-Packages([string]$requirements, [string]$target) {
    $name = [IO.Path]::GetFileNameWithoutExtension($requirements)
    $wheels = Join-Path $cache "wheels-$Arch-$name"
    $common = @('--only-binary=:all:', '--platform', $platform, '--python-version', '3.12', '--implementation', 'cp')
    & $hostPython -m pip download @common -r (Join-Path $root $requirements) -d $wheels --quiet --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) { throw "pip download failed for $requirements" }
    & $hostPython -m pip install @common --no-index --find-links $wheels --target $target --no-compile --quiet --disable-pip-version-check -r (Join-Path $root $requirements)
    if ($LASTEXITCODE -ne 0) { throw "pip install --target failed for $requirements" }
    Remove-Item -Recurse -Force (Join-Path $target 'bin') -ErrorAction SilentlyContinue
}
Add-Packages "requirements-$Arch.txt" (Join-Path $out 'Lib\site-packages')
if ($Arch -eq 'arm64') { Add-Packages 'requirements-whisper-gpu.txt' (Join-Path $out 'Lib\gpu-packages') }

foreach ($file in 'server.py', 'engine.py', 'jobs.py', 'diarize.py', 'library.py', 'setup_assets.py', 'loopback.py') {
    Copy-Item (Join-Path $root $file) $out
}
New-Item -ItemType Directory (Join-Path $out 'tools') | Out-Null
Copy-Item (Join-Path $root 'tools\ffmpeg.exe'), (Join-Path $root 'tools\LICENSE') (Join-Path $out 'tools')

# onnxruntime needs msvcp140 / vcruntime140_1; ship them app-locally instead of requiring the VC++ redistributable.
$vs = & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -latest -property installationPath
$crt = Get-ChildItem "$vs\VC\Redist\MSVC\*\$Arch\Microsoft.VC*.CRT" -Directory | Sort-Object FullName | Select-Object -Last 1
if (-not $crt) { throw "No $Arch VC++ runtime under $vs\VC\Redist\MSVC" }
Copy-Item (Join-Path $crt.FullName 'msvcp140*.dll'), (Join-Path $crt.FullName 'vcruntime140*.dll') $out -Force

$bytes = (Get-ChildItem $out -Recurse -File | Measure-Object Length -Sum).Sum
foreach ($dir in 'Lib\site-packages', 'Lib\gpu-packages') {
    $path = Join-Path $out $dir
    if (Test-Path $path) { '{0,-18} {1,8:N0} MB' -f $dir, ((Get-ChildItem $path -Recurse -File | Measure-Object Length -Sum).Sum / 1MB) }
}
'python-{0} total    {1,8:N0} MB' -f $Arch, ($bytes / 1MB)

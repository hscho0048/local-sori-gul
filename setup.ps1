$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$x64 = $env:PROCESSOR_ARCHITECTURE -eq 'AMD64'
$suffix = if ($x64) { '' } else { '-arm64' }
$pythonCandidates = '312', '311', '313' | ForEach-Object { "$env:LOCALAPPDATA\Programs\Python\Python$_$suffix\python.exe" }
$basePython = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$machine = if ($x64) { 'AMD64' } else { 'ARM64' }

function Ensure-Venv($name, $requirements) {
    if (-not (Test-Path "$name\Scripts\python.exe")) {
        if (-not $basePython) { throw "Install native Windows $machine Python 3.12 from python.org, then run setup again." }
        & $basePython -m venv $name
        if ($LASTEXITCODE -ne 0) { throw "Could not create $name." }
    }
    $arch = & "$name\Scripts\python.exe" -c "import platform; print(platform.machine())"
    if ($arch -ne $machine) { throw "$name must use native $machine Python." }
    & "$name\Scripts\python.exe" -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed for $name." }
}

if ($x64) {
    Ensure-Venv '.venv' 'backend\requirements-x64.txt'
    $gpuPython = '.\.venv\Scripts\python.exe'
} else {
    Ensure-Venv '.venv' 'backend\requirements-arm64.txt'
    Ensure-Venv '.venv-whisper-gpu' 'backend\requirements-whisper-gpu.txt'
    $gpuPython = '.\.venv-whisper-gpu\Scripts\python.exe'
}
& .\.venv\Scripts\python.exe backend\setup_assets.py
if ($LASTEXITCODE -ne 0) { throw 'Asset download failed. Run setup again to retry.' }
& $gpuPython backend\setup_assets.py --whisper-gpu
if ($LASTEXITCODE -ne 0) { throw 'GPU asset setup failed. Run setup again to retry.' }
Write-Host 'Ready. Run: npm install; npm run tauri:dev'

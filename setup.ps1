$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonCandidates = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312-arm64\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311-arm64\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313-arm64\python.exe"
)
$armPython = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

function Ensure-Venv($name, $requirements) {
    if (-not (Test-Path "$name\Scripts\python.exe")) {
        if (-not $armPython) { throw 'Install native Windows ARM64 Python 3.12 from python.org, then run setup again.' }
        & $armPython -m venv $name
        if ($LASTEXITCODE -ne 0) { throw "Could not create $name." }
    }
    $arch = & "$name\Scripts\python.exe" -c "import platform; print(platform.machine())"
    if ($arch -ne 'ARM64') { throw "$name must use native ARM64 Python." }
    & "$name\Scripts\python.exe" -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed for $name." }
}

Ensure-Venv '.venv' 'requirements.txt'
Ensure-Venv '.venv-whisper-gpu' 'requirements-whisper-gpu.txt'
& .\.venv\Scripts\python.exe setup_assets.py
if ($LASTEXITCODE -ne 0) { throw 'Asset download failed. Run setup again to retry.' }
& .\.venv-whisper-gpu\Scripts\python.exe setup_assets.py --whisper-gpu
if ($LASTEXITCODE -ne 0) { throw 'GPU asset setup failed. Run setup again to retry.' }
Write-Host 'Ready. Run: npm install; npm run tauri:dev'

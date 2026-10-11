$ErrorActionPreference = 'Stop'
$petBuildPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $petBuildPython)) { throw 'Run setup.ps1 first.' }
Push-Location $PSScriptRoot
try {
    & $petBuildPython -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Build dependencies could not be installed.' }
    & $petBuildPython -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; no release was built.' }
    & $petBuildPython -m PyInstaller --clean --noconfirm --distpath release --workpath work/build DesktopPet.spec
    if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
    Write-Output (Join-Path $PSScriptRoot 'release\DesktopPet-v0.1.0.exe')
} finally {
    Pop-Location
}

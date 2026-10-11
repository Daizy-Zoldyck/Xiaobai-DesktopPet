param([string]$PythonPath = '')
$ErrorActionPreference = 'Stop'
$petRoot = $PSScriptRoot
$petPython = Join-Path $petRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $petPython)) {
    $petCandidates = @()
    if ($PythonPath) { $petCandidates += $PythonPath }
    $petCandidates += (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
    $petCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($petCommand) { $petCandidates += $petCommand.Source }
    $petBase = $null
    foreach ($petCandidate in $petCandidates) {
        if (Test-Path -LiteralPath $petCandidate) {
            & $petCandidate -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'
            if ($LASTEXITCODE -eq 0) { $petBase = $petCandidate; break }
        }
    }
    if (-not $petBase) { throw 'Python 3.10 or later is required. Pass -PythonPath with its full executable path.' }
    & $petBase -m venv (Join-Path $petRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment.' }
}
& $petPython -m pip install -r (Join-Path $petRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Output 'Ready. Double-click DesktopPet.vbs to start.'

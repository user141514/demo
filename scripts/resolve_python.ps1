param([string]$PythonPath = $env:MEITAI_PYTHON)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
if ($PythonPath -and !(Test-Path -LiteralPath $PythonPath)) { throw 'MEITAI_PYTHON does not point to an existing interpreter.' }
$candidates = [System.Collections.Generic.List[string]]::new()
if ($PythonPath) { $candidates.Add($PythonPath) }
$candidates.Add((Join-Path $projectRoot '.venv\Scripts\python.exe'))
$condaCommand = Get-Command conda.exe -ErrorAction SilentlyContinue
$condaExecutable = if ($env:CONDA_EXE) { $env:CONDA_EXE } elseif ($condaCommand) { $condaCommand.Source }
if ($condaExecutable -and (Test-Path -LiteralPath $condaExecutable)) {
    try {
        $environments = (& $condaExecutable env list --json | ConvertFrom-Json).envs
        foreach ($environmentName in @('meitai-project', 'rag-env')) {
            foreach ($environmentPath in $environments) {
                if ((Split-Path $environmentPath -Leaf) -eq $environmentName) {
                    $candidates.Add((Join-Path $environmentPath 'python.exe'))
                }
            }
        }
    } catch { Write-Verbose 'Conda environment discovery failed.' }
}
foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if (!(Test-Path -LiteralPath $candidate)) { continue }
    & $candidate -c 'import fastapi, sqlalchemy, uvicorn, pydantic, bcrypt, jose, pypdf, docx; import sys; assert sys.version_info >= (3, 11)' 2>$null
    if ($LASTEXITCODE -eq 0) { (Resolve-Path -LiteralPath $candidate).Path; exit 0 }
    if ($PythonPath -and $candidate -eq $PythonPath) { throw 'MEITAI_PYTHON does not have the required backend dependencies.' }
}
throw 'No project Python environment found. Create .venv or set MEITAI_PYTHON to a prepared environment.'

param(
    [switch]$SkipInstall,
    [switch]$SkipIngestion,
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [string]$PythonCommand = "python"
)

$ErrorActionPreference = "Stop"
$backendPath = Join-Path $PSScriptRoot "backend"
$venvPython = Join-Path $backendPath ".venv\Scripts\python.exe"

function Invoke-CheckedPython {
    param([string[]]$Arguments)
    & $venvPython @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python step failed (exit code $LASTEXITCODE): $($Arguments -join ' ')"
    }
}

Push-Location -LiteralPath $backendPath
try {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host "Creating backend/.venv (Python 3.14+ required)..."
        & $PythonCommand -c "import sys; sys.exit(0 if sys.version_info >= (3, 14) else 'Python 3.14 or later is required.')"
        if ($LASTEXITCODE -ne 0) { throw "Choose Python 3.14+ with -PythonCommand." }
        & $PythonCommand -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment." }
    }

    Invoke-CheckedPython -Arguments @("-c", "import sys; sys.exit(0 if sys.version_info >= (3, 14) else 'The existing virtual environment needs Python 3.14+.')")

    if (-not $SkipInstall) {
        Write-Host "Installing project dependencies..."
        Invoke-CheckedPython -Arguments @("-m", "pip", "install", "-e", ".")
    }

    # Validate without printing the credential or changing existing .env files.
    Invoke-CheckedPython -Arguments @("-c", "from llm import get_api_key; get_api_key()")

    if (-not $SkipIngestion) {
        Write-Host "Indexing SEC and CSR PDFs locally (first run downloads the embedding model)..."
        Invoke-CheckedPython -Arguments @("ingest_sec.py")
        Invoke-CheckedPython -Arguments @("ingest_csr.py")
    }

    Write-Host "API documentation: http://127.0.0.1:$Port/docs"
    Write-Host "Press Ctrl+C to stop the server."
    Invoke-CheckedPython -Arguments @("-m", "uvicorn", "main:app", "--reload", "--host", "127.0.0.1", "--port", "$Port")
}
finally {
    Pop-Location
}

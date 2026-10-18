param(
    [switch]$SkipInstall,
    [switch]$SkipIngestion,
    [switch]$SkipSourceFetch,
    [switch]$RefreshSources,
    [switch]$Reload,
    [switch]$CheckOnly,
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
    $appUrl = "http://127.0.0.1:$Port"
    $runningApp = $null
    try {
        $runningApp = Invoke-RestMethod -Uri "$appUrl/health" -TimeoutSec 2 -ErrorAction Stop
    } catch {
        # No healthy consulting server at this port; check whether it can be bound.
    }
    if ($runningApp.message -eq "Management Consulting Platform is running") {
        Write-Host "The consulting app is already running: $appUrl"
        Write-Host "Open that address in your browser. No second server was started."
        Write-Host "To apply .env changes, stop the existing server first, then run this command again."
        return
    }
    $portProbe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    $portProbe.Server.ExclusiveAddressUse = $true
    try {
        $portProbe.Start()
    } catch {
        throw "Cannot use local port $Port. It is occupied or blocked by Windows. Try -Port $($Port + 1)."
    } finally {
        $portProbe.Stop()
    }
    if ($CheckOnly) {
        Write-Host "Port $Port is available for the consulting app. No setup or server startup was performed."
        return
    }
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
        if (-not $SkipSourceFetch) {
            Write-Host "Reading professor reference lists and fetching public documentation (successful downloads are cached)..."
            $sourceArguments = @("fetch_technology.py", "--all")
            if ($RefreshSources) { $sourceArguments += "--refresh" }
            Invoke-CheckedPython -Arguments $sourceArguments
            Invoke-CheckedPython -Arguments @("fetch_sec.py")
        }
        Write-Host "Indexing SEC, CSR, clinical and technology documents locally (first run downloads the embedding model)..."
        Invoke-CheckedPython -Arguments @("ingest_sec.py")
        Invoke-CheckedPython -Arguments @("ingest_csr.py")
        Invoke-CheckedPython -Arguments @("ingest_domains.py")
    }

    Write-Host "Consulting chat: $appUrl/"
    Write-Host "API documentation: $appUrl/docs"
    Write-Host "Press Ctrl+C to stop the server."
    $serverArguments = @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$Port")
    if ($Reload) { $serverArguments += "--reload" }
    Invoke-CheckedPython -Arguments $serverArguments
}
finally {
    Pop-Location
}


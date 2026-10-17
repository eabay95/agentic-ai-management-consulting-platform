# One-command Windows setup and launch. Never prints or overwrites existing keys.
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)][int]$Port = 8501,
    [switch]$FetchPublic,
    [switch]$Reinstall,
    [switch]$SetupOnly,
    [switch]$NoBrowser,
    [switch]$Plan
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$environmentPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Executable $($Arguments -join ' ')"
    }
}

if ($Plan) {
    Write-Host "Project: $projectRoot"
    Write-Host '1. Check Python 3.11+ and create .venv if missing.'
    Write-Host '2. Install requirements when new or changed (or with -Reinstall).'
    Write-Host '3. Create .env only if missing; preserve all existing settings and keys.'
    Write-Host '4. Safely extract professor archives when new or changed.'
    if ($FetchPublic) { Write-Host '5. Fetch professor-approved public sources.' }
    Write-Host '6. Index documents using the configured embedding backend; reuse unchanged chunks.'
    if (-not $SetupOnly) { Write-Host "7. Start Streamlit at http://localhost:$Port (Ctrl+C to stop)." }
    exit 0
}

Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath $environmentPython)) {
        Write-Host 'Creating Python virtual environment...'
        $pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
        if (-not $pythonLauncher) { $pythonLauncher = Get-Command python -ErrorAction SilentlyContinue }
        if (-not $pythonLauncher) { throw 'Install Python 3.11 or newer, enable its PATH option, and run this script again.' }
        Invoke-Checked -Executable $pythonLauncher.Source -Arguments @('-c', 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)')
        Invoke-Checked -Executable $pythonLauncher.Source -Arguments @('-m', 'venv', (Join-Path $projectRoot '.venv'))
    }
    Invoke-Checked -Executable $environmentPython -Arguments @('-c', 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)')
    $requirements = Join-Path $projectRoot 'requirements.txt'
    $requirementsHash = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash
    $dependencyStamp = Join-Path $projectRoot '.venv\requirements.sha256'
    $installedHash = if (Test-Path -LiteralPath $dependencyStamp) { (Get-Content -LiteralPath $dependencyStamp -Raw).Trim() } else { '' }
    if ($Reinstall -or $installedHash -ne $requirementsHash) {
        Write-Host 'Installing application dependencies (first run may take several minutes)...'
        Invoke-Checked -Executable $environmentPython -Arguments @('-m', 'pip', '--disable-pip-version-check', 'install', '-r', $requirements)
        Set-Content -LiteralPath $dependencyStamp -Value $requirementsHash
    }
    $envFile = Join-Path $projectRoot '.env'
    if (-not (Test-Path -LiteralPath $envFile)) {
        Copy-Item -LiteralPath (Join-Path $projectRoot '.env.example') -Destination $envFile
        Write-Host 'Created .env. Add GEMINI_API_KEY there and restart for generated answers; evidence-only mode works now.'
    }
    $archiveNames = @('Clinical.zip', 'FoodSecurity.zip', 'Retail.zip', 'UnitedStatesSecuritiesandExchangeCommission(SEC).zip')
    $archiveHashes = foreach ($name in $archiveNames) {
        $archive = Join-Path $projectRoot "professor_resources\$name"
        if (-not (Test-Path -LiteralPath $archive)) { throw "Missing professor resource: $name" }
        (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
    }
    $archiveSignature = $archiveHashes -join ':'
    $archiveStamp = Join-Path $projectRoot 'data\launcher_archives.sha256'
    $previousArchives = if (Test-Path -LiteralPath $archiveStamp) { (Get-Content -LiteralPath $archiveStamp -Raw).Trim() } else { '' }
    $missingDomain = @('clinical', 'sec', 'csr', 'retail') | Where-Object { -not (Test-Path -LiteralPath (Join-Path $projectRoot "data\$_")) }
    if ($previousArchives -ne $archiveSignature -or $missingDomain) {
        Write-Host 'Extracting the professor archives safely...'
        Invoke-Checked -Executable $environmentPython -Arguments @('-m', 'rag.ingestion', '--extract')
        Set-Content -LiteralPath $archiveStamp -Value $archiveSignature
    }
    if ($FetchPublic) {
        Write-Host 'Fetching professor-approved Cisco, Google Cloud and Agilent sources...'
        Invoke-Checked -Executable $environmentPython -Arguments @('-m', 'rag.public_sources')
    }
    Write-Host 'Updating the knowledge index; unchanged chunks are reused...'
    Invoke-Checked -Executable $environmentPython -Arguments @('-m', 'rag.ingestion', '--index')
    if ($SetupOnly) {
        Write-Host 'Setup complete. Run .\run.ps1 to start the app.'
    } else {
        Write-Host "Starting http://localhost:$Port - press Ctrl+C to stop."
        $launchArguments = @('-m', 'streamlit', 'run', 'app.py', '--server.address', '127.0.0.1', '--server.port', "$Port", '--server.headless', "$($NoBrowser.IsPresent.ToString().ToLower())")
        Invoke-Checked -Executable $environmentPython -Arguments $launchArguments
    }
} catch {
    Write-Host "Setup or launch failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Fix the error and run again. Existing .env, customer histories and source files are preserved.'
    exit 1
} finally {
    Pop-Location
}

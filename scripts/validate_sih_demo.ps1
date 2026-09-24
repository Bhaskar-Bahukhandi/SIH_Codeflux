param(
    [switch]$SkipFlutter
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogRoot = Join-Path $RepoRoot ("tmp\sih-demo-validation\" + $Timestamp)
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

function Resolve-CommandPath {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$FallbackPath = ""
    )

    if ($FallbackPath -and (Test-Path $FallbackPath)) { return $FallbackPath }
    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $Command) { throw "$Name was not found on PATH." }
    return $Command.Source
}

function Invoke-ValidationCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $LogPath = Join-Path $LogRoot ($Name + ".log")
    Write-Host ""
    Write-Host "==> $Name"
    Write-Host "    Working directory: $WorkingDirectory"
    Write-Host "    Log: $LogPath"

    Push-Location $WorkingDirectory
    try {
        & $Executable @Arguments 2>&1 | Tee-Object -FilePath $LogPath
        $ExitCode = $LASTEXITCODE
    }
    finally { Pop-Location }

    if ($ExitCode -ne 0) { throw "$Name failed with exit code $ExitCode. See $LogPath" }
}

$ApiDirectory = Join-Path $RepoRoot "services\api"
$DashboardDirectory = Join-Path $RepoRoot "apps\dashboard"
$MobileDirectory = Join-Path $RepoRoot "apps\mobile"
$RepoPython = Join-Path $ApiDirectory ".venv\Scripts\python.exe"
$Python = Resolve-CommandPath -Name "python" -FallbackPath $RepoPython
$Npm = Resolve-CommandPath -Name "npm"

Write-Host "CODEFLUX SIH demo automated validation"
Write-Host "Repository: $RepoRoot"
Write-Host "Logs: $LogRoot"

Invoke-ValidationCommand -Name "api-migrate-up" -WorkingDirectory $ApiDirectory -Executable $Python -Arguments @("-m", "alembic", "upgrade", "head")
Invoke-ValidationCommand -Name "api-migrate-down" -WorkingDirectory $ApiDirectory -Executable $Python -Arguments @("-m", "alembic", "downgrade", "base")
Invoke-ValidationCommand -Name "api-migrate-up-again" -WorkingDirectory $ApiDirectory -Executable $Python -Arguments @("-m", "alembic", "upgrade", "head")
Invoke-ValidationCommand -Name "api-regression" -WorkingDirectory $ApiDirectory -Executable $Python -Arguments @("-m", "pytest", "-q")
Invoke-ValidationCommand -Name "dashboard-install" -WorkingDirectory $DashboardDirectory -Executable $Npm -Arguments @("install", "--no-audit", "--no-fund")
Invoke-ValidationCommand -Name "dashboard-tests" -WorkingDirectory $DashboardDirectory -Executable $Npm -Arguments @("test")
Invoke-ValidationCommand -Name "dashboard-build" -WorkingDirectory $DashboardDirectory -Executable $Npm -Arguments @("run", "build")

$FlutterStatus = "BLOCKED / SKIPPED"
if (-not $SkipFlutter) {
    $Flutter = Resolve-CommandPath -Name "flutter"
    Invoke-ValidationCommand -Name "flutter-version" -WorkingDirectory $MobileDirectory -Executable $Flutter -Arguments @("--version")
    Invoke-ValidationCommand -Name "flutter-pub-get" -WorkingDirectory $MobileDirectory -Executable $Flutter -Arguments @("pub", "get")
    Invoke-ValidationCommand -Name "flutter-analyze" -WorkingDirectory $MobileDirectory -Executable $Flutter -Arguments @("analyze")
    Invoke-ValidationCommand -Name "flutter-tests" -WorkingDirectory $MobileDirectory -Executable $Flutter -Arguments @("test")
    $FlutterStatus = "PASS"
}

$SummaryPath = Join-Path $LogRoot "SUMMARY.txt"
@(
    "CODEFLUX SIH demo automated validation completed."
    "Timestamp: $Timestamp"
    "API migration chain: PASS"
    "API regression: PASS"
    "Dashboard tests: PASS"
    "Dashboard production build: PASS"
    "Flutter automated validation: $FlutterStatus"
    ""
    "External evidence status:"
    "Real-package quality/geometry: EXTERNAL EVIDENCE REQUIRED"
    "Real-package OCR: EXTERNAL EVIDENCE REQUIRED"
    "Real-package declaration extraction: EXTERNAL EVIDENCE REQUIRED"
    "Physical-device offline/reconnect: EXTERNAL EVIDENCE REQUIRED"
    "Production-like Flutter-to-FastAPI run: EXTERNAL EVIDENCE REQUIRED"
    "Mobile OCR runtime spike: EXTERNAL EVIDENCE REQUIRED"
    "Physical font-size/calibration validation: EXTERNAL EVIDENCE REQUIRED"
    "Hosting provider: DEFERRED / OPEN DECISION"
) | Set-Content -Path $SummaryPath -Encoding UTF8

Write-Host ""
Write-Host "Automated validation completed."
Write-Host "Evidence logs: $LogRoot"
Write-Host "External/runtime gates remain unverified; see docs/validation/README.md."

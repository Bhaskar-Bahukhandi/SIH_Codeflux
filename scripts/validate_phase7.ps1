$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogRoot = Join-Path $RepoRoot ("tmp\\phase7-validation\\" + $Timestamp)
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

function Resolve-Python {
    $RepoPython = Join-Path $RepoRoot "services\\api\\.venv\\Scripts\\python.exe"
    if (Test-Path $RepoPython) {
        return $RepoPython
    }

    $Command = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $Command) {
        return $Command.Source
    }

    throw "Python was not found. Create/activate the API environment before validation."
}

function Resolve-Flutter {
    $Command = Get-Command flutter -ErrorAction SilentlyContinue
    if ($null -eq $Command) {
        throw "Flutter was not found on PATH. Install/configure Flutter before validation."
    }
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
    finally {
        Pop-Location
    }

    if ($ExitCode -ne 0) {
        throw "$Name failed with exit code $ExitCode. See $LogPath"
    }
}

$Python = Resolve-Python
$Flutter = Resolve-Flutter
$ApiDirectory = Join-Path $RepoRoot "services\\api"
$MobileDirectory = Join-Path $RepoRoot "apps\\mobile"

Write-Host "CODEFLUX Phase 7 local validation"
Write-Host "Repository: $RepoRoot"
Write-Host "Python: $Python"
Write-Host "Flutter: $Flutter"
Write-Host "Logs: $LogRoot"

Invoke-ValidationCommand `
    -Name "api-focused-sync-idempotency" `
    -WorkingDirectory $ApiDirectory `
    -Executable $Python `
    -Arguments @("-m", "pytest", "tests/test_sync_idempotency.py", "-q")

Invoke-ValidationCommand `
    -Name "api-full-regression" `
    -WorkingDirectory $ApiDirectory `
    -Executable $Python `
    -Arguments @("-m", "pytest", "-q")

Invoke-ValidationCommand `
    -Name "flutter-version" `
    -WorkingDirectory $MobileDirectory `
    -Executable $Flutter `
    -Arguments @("--version")

Invoke-ValidationCommand `
    -Name "flutter-pub-get" `
    -WorkingDirectory $MobileDirectory `
    -Executable $Flutter `
    -Arguments @("pub", "get")

Invoke-ValidationCommand `
    -Name "flutter-analyze" `
    -WorkingDirectory $MobileDirectory `
    -Executable $Flutter `
    -Arguments @("analyze")

Invoke-ValidationCommand `
    -Name "flutter-test" `
    -WorkingDirectory $MobileDirectory `
    -Executable $Flutter `
    -Arguments @("test")

$SummaryPath = Join-Path $LogRoot "PASS.txt"
@(
    "CODEFLUX Phase 7 local validation passed."
    "Timestamp: $Timestamp"
    "Focused backend replay tests: PASS"
    "Full backend regression suite: PASS"
    "Flutter dependency resolution: PASS"
    "Flutter analyzer: PASS"
    "Flutter tests: PASS"
) | Set-Content -Path $SummaryPath -Encoding UTF8

Write-Host ""
Write-Host "Phase 7 local validation PASSED."
Write-Host "Evidence logs: $LogRoot"

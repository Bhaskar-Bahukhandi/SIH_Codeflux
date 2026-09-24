param(
    [string]$Organization = "org.sih.codeflux"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$MobileDir = Join-Path $RepoRoot "apps\mobile"
$AndroidDir = Join-Path $MobileDir "android"
$IosDir = Join-Path $MobileDir "ios"

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    throw "Flutter was not found on PATH."
}

if ((Test-Path $AndroidDir) -or (Test-Path $IosDir)) {
    throw "Android or iOS platform directories already exist."
}

$BackupDir = Join-Path $RepoRoot "tmp\mobile-platform-setup"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$Pubspec = Join-Path $MobileDir "pubspec.yaml"
$Main = Join-Path $MobileDir "lib\main.dart"
Copy-Item $Pubspec (Join-Path $BackupDir "pubspec.yaml") -Force
Copy-Item $Main (Join-Path $BackupDir "main.dart") -Force

Push-Location $MobileDir
try {
    flutter create --platforms=android,ios --org $Organization .
}
finally {
    Pop-Location
}

Copy-Item (Join-Path $BackupDir "pubspec.yaml") $Pubspec -Force
Copy-Item (Join-Path $BackupDir "main.dart") $Main -Force

$GradleKts = Join-Path $MobileDir "android\app\build.gradle.kts"
$GradleGroovy = Join-Path $MobileDir "android\app\build.gradle"
if (Test-Path $GradleKts) {
    $Text = Get-Content $GradleKts -Raw
    $Text = $Text -replace "minSdk\s*=\s*flutter\.minSdkVersion", "minSdk = 24"
    Set-Content -Path $GradleKts -Value $Text -Encoding UTF8
}
elseif (Test-Path $GradleGroovy) {
    $Text = Get-Content $GradleGroovy -Raw
    $Text = $Text -replace "minSdkVersion\s+flutter\.minSdkVersion", "minSdkVersion 24"
    Set-Content -Path $GradleGroovy -Value $Text -Encoding UTF8
}

$InfoPlist = Join-Path $MobileDir "ios\Runner\Info.plist"
if (Test-Path $InfoPlist) {
    $Plist = Get-Content $InfoPlist -Raw
    if ($Plist -notmatch "NSCameraUsageDescription") {
        $Insert = @'
    <key>NSCameraUsageDescription</key>
    <string>CODEFLUX uses the camera to capture package evidence.</string>
    <key>NSPhotoLibraryUsageDescription</key>
    <string>CODEFLUX uses selected package images as inspection evidence.</string>
'@
        $Plist = $Plist -replace "<dict>", ("<dict>`r`n" + $Insert)
        Set-Content -Path $InfoPlist -Value $Plist -Encoding UTF8
    }
}

Push-Location $MobileDir
try {
    flutter pub get
    if ($LASTEXITCODE -ne 0) { throw "flutter pub get failed." }

    flutter analyze
    if ($LASTEXITCODE -ne 0) { throw "flutter analyze failed." }
}
finally {
    Pop-Location
}

Write-Host "Mobile platform setup complete."
Write-Host "Run with:"
Write-Host "flutter run --dart-define=CODEFLUX_API_URL=https://your-api.example/"

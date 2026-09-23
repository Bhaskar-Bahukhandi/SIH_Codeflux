param(
    [string]$Organization = "in.sih.codeflux"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$MobileDir = Join-Path $RepoRoot "apps\mobile"
$AndroidDir = Join-Path $MobileDir "android"
$IosDir = Join-Path $MobileDir "ios"

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    throw "Flutter was not found on PATH."
}

Push-Location $RepoRoot
try {
    $Dirty = git status --porcelain
    if ($Dirty) {
        throw "Working tree is not clean. Commit/stash changes before platform bootstrap."
    }
}
finally {
    Pop-Location
}

if ((Test-Path $AndroidDir) -or (Test-Path $IosDir)) {
    throw "Android or iOS platform directories already exist. Review them instead of regenerating automatically."
}

$BackupDir = Join-Path $RepoRoot "tmp\mobile-platform-bootstrap"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$Pubspec = Join-Path $MobileDir "pubspec.yaml"
$Main = Join-Path $MobileDir "lib\main.dart"
$PubspecBackup = Join-Path $BackupDir "pubspec.yaml"
$MainBackup = Join-Path $BackupDir "main.dart"
Copy-Item $Pubspec $PubspecBackup -Force
Copy-Item $Main $MainBackup -Force

Write-Host "Flutter version:"
flutter --version

Push-Location $MobileDir
try {
    flutter create --platforms=android,ios --org $Organization .
}
finally {
    Pop-Location
}

# Preserve the hand-written dependency and application entrypoint files.
Copy-Item $PubspecBackup $Pubspec -Force
Copy-Item $MainBackup $Main -Force

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
else {
    throw "Could not find the generated Android app Gradle file."
}

$InfoPlist = Join-Path $MobileDir "ios\Runner\Info.plist"
if (-not (Test-Path $InfoPlist)) {
    throw "Generated iOS Info.plist was not found."
}
$Plist = Get-Content $InfoPlist -Raw
if ($Plist -notmatch "NSCameraUsageDescription") {
    $Insert = @'
    <key>NSCameraUsageDescription</key>
    <string>CODEFLUX uses the camera to capture packaged-commodity evidence during an inspection.</string>
    <key>NSPhotoLibraryUsageDescription</key>
    <string>CODEFLUX uses selected package images as inspection evidence.</string>
'@
    $Plist = $Plist -replace "<dict>", ("<dict>`r`n" + $Insert)
    Set-Content -Path $InfoPlist -Value $Plist -Encoding UTF8
}

$Podfile = Join-Path $MobileDir "ios\Podfile"
if (Test-Path $Podfile) {
    $PodText = Get-Content $Podfile -Raw
    if ($PodText -match "(?m)^#?\s*platform :ios,\s*'[^']+'") {
        $PodText = [regex]::Replace(
            $PodText,
            "(?m)^#?\s*platform :ios,\s*'[^']+'",
            "platform :ios, '13.0'"
        )
    }
    else {
        $PodText = "platform :ios, '13.0'`r`n" + $PodText
    }
    Set-Content -Path $Podfile -Value $PodText -Encoding UTF8
}

Push-Location $MobileDir
try {
    flutter pub get
    if ($LASTEXITCODE -ne 0) { throw "flutter pub get failed." }

    flutter analyze
    if ($LASTEXITCODE -ne 0) { throw "flutter analyze failed." }

    flutter test
    if ($LASTEXITCODE -ne 0) { throw "flutter test failed." }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Mobile platform bootstrap completed and validation passed."
Write-Host "Review the generated android/ and ios/ changes before committing them."
Write-Host "Run the app with:"
Write-Host "flutter run --dart-define=CODEFLUX_API_URL=https://your-api.example/"

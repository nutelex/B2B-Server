$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$localCloudflared = Join-Path $root "cloudflared.exe"
if (Test-Path $localCloudflared) {
    $cloudflared = $localCloudflared
} else {
    $cloudflared = (Get-Command cloudflared.exe -ErrorAction Stop).Source
}
$pythonDir = Split-Path -Parent (Get-Command python.exe -ErrorAction Stop).Source
$tclRoot = Join-Path $pythonDir "tcl"
$distDir = Join-Path $root "dist"
$buildDir = Join-Path $root "build"

if (Test-Path $distDir) {
    Remove-Item -Recurse -Force $distDir
}

if (Test-Path $buildDir) {
    Remove-Item -Recurse -Force $buildDir
}

$args = @(
    "--noconfirm",
    "--windowed",
    "--name", "B2B Serv",
    "--icon", "app-icon.ico",
    "--add-binary", "$cloudflared;.",
    "main.py"
)

if (Test-Path $tclRoot) {
    $args += @("--add-data", "$tclRoot;tcl")
}

pyinstaller @args

Write-Host ""
Write-Host "Export termine dans:" (Join-Path $distDir "B2B Serv")

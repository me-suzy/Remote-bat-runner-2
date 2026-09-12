# Safe one-time setup for Windows automatic logon after a restart.
# This intentionally DOES NOT accept or store a password in this repository.
# It downloads Microsoft's Sysinternals Autologon utility and opens its local GUI,
# where the password is entered directly on the laptop and stored as an LSA secret.
$ErrorActionPreference = 'Stop'

$workDir = Join-Path $env:LOCALAPPDATA 'RemoteBatRunner\SysinternalsAutologon'
$zipPath = Join-Path $workDir 'Autologon.zip'
$exePath = Join-Path $workDir 'Autologon64.exe'
$url = 'https://download.sysinternals.com/files/Autologon.zip'

New-Item -ItemType Directory -Force -Path $workDir | Out-Null

if (-not (Test-Path $exePath)) {
    Write-Host 'Downloading Microsoft Sysinternals Autologon...'
    Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing
    Expand-Archive -Path $zipPath -DestinationPath $workDir -Force
}

if (-not (Test-Path $exePath)) {
    throw "Autologon64.exe was not found in $workDir"
}

$signature = Get-AuthenticodeSignature -LiteralPath $exePath
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
    throw 'Autologon signature is not a valid Microsoft signature.'
}

Write-Host ''
Write-Host 'A Microsoft Sysinternals window will open.' -ForegroundColor Cyan
Write-Host 'Enter the Windows account/password DIRECTLY in that window and click Enable.' -ForegroundColor Yellow
Write-Host 'Do not put the password in config.py, GitHub, this script, or the mobile page.' -ForegroundColor Yellow
Write-Host ''
Start-Process -FilePath $exePath -Verb RunAs -Wait
Write-Host 'Autologon setup window closed. Reboot once while you are near the laptop to verify it.' -ForegroundColor Green

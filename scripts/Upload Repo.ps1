# Descarcă scriptul
$scriptPath = "$env:TEMP\copy_to_github.ps1"

# Creează scriptul local
@"
# Script pentru copierea conținutului remote-bat-runner în GitHub

`$ErrorActionPreference = "Stop"

`$sourceDir = "d:\Teste cursor\remote-bat-runner"
`$tempDir = "`$env:TEMP\remote-bat-runner-upload"
`$repoUrl = "https://github.com/me-suzy/Remote-bat-runner-2.git"

Write-Host "🚀 Starting upload to GitHub..." -ForegroundColor Cyan

# Verifică dacă directorul sursă există
if (-not (Test-Path `$sourceDir)) {
    Write-Host "❌ ERROR: Source directory not found: `$sourceDir" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Source directory found" -ForegroundColor Green

# Curăță directorul temporar
if (Test-Path `$tempDir) {
    Remove-Item -Path `$tempDir -Recurse -Force
}

# Creează director temporar
New-Item -ItemType Directory -Path `$tempDir -Force | Out-Null

# Clonează repository-ul
Write-Host "📥 Cloning repository..." -ForegroundColor Cyan
Set-Location `$tempDir
git clone `$repoUrl .

# Copiază toate fișierele
Write-Host "📋 Copying files..." -ForegroundColor Cyan
Get-ChildItem -Path `$tempDir -Exclude ".git" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item -Path "`$sourceDir\*" -Destination `$tempDir -Recurse -Force

# Git config
git config user.name "Suzy" 2>`$null
git config user.email "ioan.fantanaru@gmail.com" 2>`$null

# Add și commit
Write-Host "💾 Committing files..." -ForegroundColor Cyan
git add .
git commit -m "Initial commit: Complete remote-bat-runner setup

Copied all files from d:\Teste cursor\remote-bat-runner

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Cg3V6SfDxCYMdG8Hy1HffY"

# Push
Write-Host "📤 Pushing to GitHub..." -ForegroundColor Cyan
git push -u origin main

if (`$LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "🎉 SUCCESS! Files uploaded!" -ForegroundColor Green
    Write-Host "   https://github.com/me-suzy/Remote-bat-runner-2" -ForegroundColor Cyan
} else {
    Write-Host "⚠️  Trying master branch..." -ForegroundColor Yellow
    git push -u origin master
}

Write-Host ""
Read-Host "Press Enter to exit"
"@ | Out-File -FilePath $scriptPath -Encoding UTF8

# Rulează scriptul
& $scriptPath
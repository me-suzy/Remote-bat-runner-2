# Opens the ChatGPT Windows app for the currently logged-in user.
# If ChatGPT already has a window, try to bring it to the foreground instead
# of starting a second instance.
$ErrorActionPreference = 'Stop'

$startApp = Get-StartApps | Where-Object { $_.Name -eq 'ChatGPT' } | Select-Object -First 1
$package = if ($startApp) { Get-AppxPackage | Where-Object { $startApp.AppID.StartsWith($_.PackageFamilyName + '!') } | Select-Object -First 1 }
$mutex = New-Object System.Threading.Mutex($false, 'Local\RemoteBatRunner-OpenChatGPT')
if (-not $mutex.WaitOne(0)) { Write-Output 'ChatGPT launch is already in progress.'; exit 0 }
try {
function Try-ActivateChatGPT {
    $candidates = Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $_.ProcessName -eq 'ChatGPT' -or ($package -and $_.Path -and $_.Path.StartsWith($package.InstallLocation + '\', [StringComparison]::OrdinalIgnoreCase))
    }

    foreach ($p in $candidates) {
        if ($p.MainWindowHandle -ne 0 -and $p.MainWindowTitle) {
            try {
                $wshell = New-Object -ComObject WScript.Shell
                if ($wshell.AppActivate($p.Id)) {
                    return $true
                }
            } catch { }
        }
    }
    return $false
}

if (Try-ActivateChatGPT) {
    Write-Output 'ChatGPT is already open; activated its window.'
    exit 0
}

# An existing Win32 process without an activatable window must not be duplicated.
if (Get-Process -Name ChatGPT -ErrorAction SilentlyContinue) {
    Write-Output 'ChatGPT is running; Windows did not allow foreground activation.'
    exit 0
}

# Microsoft Store / packaged app: resolve the installed AppUserModelID dynamically.
$startApp = Get-StartApps | Where-Object { $_.Name -eq 'ChatGPT' } | Select-Object -First 1
if (-not $startApp) {
    $startApp = Get-StartApps | Where-Object { $_.Name -match 'ChatGPT' } | Select-Object -First 1
}
if ($startApp) {
    Start-Process -WindowStyle Hidden explorer.exe "shell:AppsFolder\$($startApp.AppID)"
    Start-Sleep -Seconds 2
    Try-ActivateChatGPT | Out-Null
    Write-Output "Started ChatGPT via AppUserModelID: $($startApp.AppID)"
    exit 0
}

# Win32 fallback locations, if ChatGPT was installed outside the Store package.
$possible = @(
    "$env:LOCALAPPDATA\Programs\ChatGPT\ChatGPT.exe",
    "$env:LOCALAPPDATA\ChatGPT\ChatGPT.exe",
    "$env:ProgramFiles\ChatGPT\ChatGPT.exe",
    "${env:ProgramFiles(x86)}\ChatGPT\ChatGPT.exe"
) | Where-Object { $_ -and (Test-Path $_) }

if ($possible.Count -gt 0) {
    Start-Process -WindowStyle Hidden $possible[0]
    Write-Output "Started ChatGPT: $($possible[0])"
    exit 0
}

throw 'ChatGPT could not be found. Open it once manually, then run this script again.'

} finally { $mutex.ReleaseMutex(); $mutex.Dispose() }

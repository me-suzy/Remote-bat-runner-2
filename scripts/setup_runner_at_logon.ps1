# Register an interactive logon task without storing a Windows password.
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python.exe -ErrorAction Stop).Source
$venvPython = Join-Path $projectDir '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython) { $python = $venvPython }
foreach ($name in @('app.py','config.py','secret.txt')) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectDir $name))) { throw "Missing $name; configure the runner first." }
}
$taskName = 'RemoteBatRunner-AtLogon'
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $python -Argument ('"' + (Join-Path $projectDir 'app.py') + '"') -WorkingDirectory $projectDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$trigger.Delay = 'PT30S'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "Registered $taskName. Starts the Arcanum control server and ngrok at logon."

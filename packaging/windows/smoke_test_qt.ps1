<#
.SYNOPSIS
    Start the Qt window (--smoke) from a Windows build and check it quits cleanly.

.DESCRIPTION
    Runs the executable with --smoke: the window loads, shows and
    quits, exit code 1 on any QML warning (chordnotepad_desktop/main.py).
    Works for the onefile exe and for the onedir folder the MSIX is made of
    (run outside the package: the same files, without package identity).

    The Qt Quick scene graph may get no GPU on a CI runner. If the plain run
    fails, it runs again with QT_QUICK_BACKEND=software and only warns when
    that one passes. On failure it prints the newest app log.
#>
param(
    [Parameter(Mandatory)] [string] $Exe,
    [int] $TimeoutSeconds = 120
)

$ErrorActionPreference = 'Stop'
$Exe = (Resolve-Path $Exe).Path

# The app keeps its config and logs in %USERPROFILE%\AppData\Roaming\ChordNotepad.
# If this run creates that folder it removes it again at the end: it must not
# exist when the Store package's smoke test runs, or the package writes into
# it instead of its own redirected copy.
$appData = Join-Path $HOME 'AppData\Roaming\ChordNotepad'
$hadAppData = Test-Path $appData
function Remove-OwnAppData {
    if (-not $hadAppData -and (Test-Path $appData)) { Remove-Item -Recurse -Force $appData }
}

function Invoke-Smoke([bool] $Software) {
    if ($Software) { $env:QT_QUICK_BACKEND = 'software' } else { Remove-Item Env:QT_QUICK_BACKEND -ErrorAction SilentlyContinue }
    $proc = Start-Process -FilePath $Exe -ArgumentList '--smoke' -PassThru
    $null = $proc.Handle  # keeps ExitCode readable after the process exits
    if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
        $proc.Kill()
        Write-Host "::warning::--smoke was still running after ${TimeoutSeconds}s"
        return 124
    }
    return $proc.ExitCode
}

$code = Invoke-Smoke $false
if ($code -eq 0) {
    Write-Host "The Qt window started and quit cleanly ($Exe)"
    Remove-OwnAppData
    exit 0
}
Write-Host "::warning::--smoke exited with $code; trying QT_QUICK_BACKEND=software"
$code = Invoke-Smoke $true
Remove-Item Env:QT_QUICK_BACKEND -ErrorAction SilentlyContinue
if ($code -eq 0) {
    Write-Host "::warning::The Qt window only starts with software rendering on this runner ($Exe)"
    Remove-OwnAppData
    exit 0
}

Write-Host "::error::The Qt window (--smoke) didn't start from $Exe (exit code $code)"
$logs = Join-Path $appData 'logs'
$log = Get-ChildItem -Path $logs -Filter '*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($log) {
    Write-Host "----- $($log.FullName) -----"
    Get-Content $log.FullName -Tail 80
}
Remove-OwnAppData
exit 1

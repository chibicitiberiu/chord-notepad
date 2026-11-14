<#
.SYNOPSIS
    Start the Qt window (--ui qt --smoke) from a Windows build and check it quits cleanly.

.DESCRIPTION
    Runs the executable with --ui qt --smoke: the window loads, shows and
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

function Invoke-Smoke([bool] $Software) {
    if ($Software) { $env:QT_QUICK_BACKEND = 'software' } else { Remove-Item Env:QT_QUICK_BACKEND -ErrorAction SilentlyContinue }
    $proc = Start-Process -FilePath $Exe -ArgumentList '--ui', 'qt', '--smoke' -PassThru
    $null = $proc.Handle  # keeps ExitCode readable after the process exits
    if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
        $proc.Kill()
        Write-Host "::warning::--ui qt --smoke was still running after ${TimeoutSeconds}s"
        return 124
    }
    return $proc.ExitCode
}

$code = Invoke-Smoke $false
if ($code -eq 0) {
    Write-Host "The Qt window started and quit cleanly ($Exe)"
    exit 0
}
Write-Host "::warning::--ui qt --smoke exited with $code; trying QT_QUICK_BACKEND=software"
$code = Invoke-Smoke $true
Remove-Item Env:QT_QUICK_BACKEND -ErrorAction SilentlyContinue
if ($code -eq 0) {
    Write-Host "::warning::The Qt window only starts with software rendering on this runner ($Exe)"
    exit 0
}

Write-Host "::error::The Qt window (--ui qt --smoke) didn't start from $Exe (exit code $code)"
$logs = Join-Path $env:APPDATA 'ChordNotepad\logs'
$log = Get-ChildItem -Path $logs -Filter '*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($log) {
    Write-Host "----- $($log.FullName) -----"
    Get-Content $log.FullName -Tail 80
}
exit 1

<#
.SYNOPSIS
    Install an unsigned Chord Notepad MSIX and check the app starts inside it.

.DESCRIPTION
    Meant for a throwaway CI runner: it trusts a freshly made self-signed
    certificate machine-wide (needs admin) and leaves the app installed.

    Signs a copy of the package with that certificate, installs it, launches
    the app through its package identity and passes when:
      - the startup banner appears in the log, which must be written under the
        package's private AppData (proves file-system redirection works), and
      - the process is still alive after the log appears.
    A missing "Loaded soundfont" line is only a warning, because CI runners
    have no audio device and FluidSynth may fail to open one.
#>
param(
    [Parameter(Mandatory)] [string] $Package,
    [Parameter(Mandatory)] [string] $IdentityName,
    [Parameter(Mandatory)] [string] $Publisher,
    [int] $TimeoutSeconds = 60,
    [int] $AliveSeconds = 10
)

$ErrorActionPreference = 'Stop'

$kits = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
$signtool = Get-ChildItem -Path $kits -Filter 'signtool.exe' -Recurse -Depth 2 -ErrorAction SilentlyContinue |
    Where-Object { $_.Directory.Name -eq 'x64' -and $_.Directory.Parent.Name -match '^\d+(\.\d+)+$' } |
    Sort-Object { [version]$_.Directory.Parent.Name } -Descending |
    Select-Object -First 1
if (-not $signtool) { throw "signtool.exe not found under $kits" }

$work = Join-Path ([IO.Path]::GetTempPath()) ("chord-notepad-smoke-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $work | Out-Null
$signed = Join-Path $work (Split-Path $Package -Leaf)
Copy-Item $Package $signed

Write-Host "Signing a test copy as $Publisher"
$cert = New-SelfSignedCertificate -Type Custom -Subject $Publisher `
    -KeyUsage DigitalSignature -CertStoreLocation Cert:\CurrentUser\My `
    -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3', '2.5.29.19={text}')
$password = ConvertTo-SecureString -String 'smoke-test' -Force -AsPlainText
$pfx = Join-Path $work 'test.pfx'
$cer = Join-Path $work 'test.cer'
Export-PfxCertificate -Cert $cert -FilePath $pfx -Password $password | Out-Null
Export-Certificate -Cert $cert -FilePath $cer | Out-Null
& $signtool.FullName sign /fd SHA256 /f $pfx /p 'smoke-test' $signed
if ($LASTEXITCODE -ne 0) { throw "signtool failed with exit code $LASTEXITCODE" }
Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople | Out-Null

Write-Host "Installing $signed"
Add-AppxPackage -Path $signed
$installed = Get-AppxPackage -Name $IdentityName
if (-not $installed) { throw "Package $IdentityName not found after install" }
Write-Host "Installed $($installed.PackageFullName) at $($installed.InstallLocation)"

$packageData = Join-Path $env:LOCALAPPDATA "Packages\$($installed.PackageFamilyName)"
$realLogs = Join-Path $env:APPDATA 'ChordNotepad\logs'

Write-Host "Launching shell:AppsFolder\$($installed.PackageFamilyName)!ChordNotepad"
Start-Process "shell:AppsFolder\$($installed.PackageFamilyName)!ChordNotepad"

$log = $null
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    $log = Get-ChildItem -Path $packageData -Filter '*.log' -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -like '*ChordNotepad*' } |
        Select-Object -First 1
    if ($log -and (Select-String -Path $log.FullName -Pattern 'Version:' -Quiet)) { break }
}

$failed = $false
if (-not $log) {
    $failed = $true
    Write-Host "::error::No log file appeared under $packageData within ${TimeoutSeconds}s"
    if (Test-Path $realLogs) {
        Write-Host "::error::A log exists in the real AppData ($realLogs): writes were NOT redirected"
        Get-ChildItem $realLogs | ForEach-Object { Get-Content $_.FullName -Tail 50 }
    }
    Get-Process | Where-Object { $_.ProcessName -like '*ChordNotepad*' } | Format-Table Id, ProcessName, StartTime
}
else {
    Write-Host "Log written to $($log.FullName)"
    Start-Sleep -Seconds $AliveSeconds
    $proc = Get-Process -Name 'ChordNotepad' -ErrorAction SilentlyContinue
    if (-not $proc) {
        $failed = $true
        Write-Host "::error::ChordNotepad exited within ${AliveSeconds}s of starting"
    }
    else {
        Write-Host "ChordNotepad still running (pid $($proc.Id -join ', '))"
    }

    if (-not (Select-String -Path $log.FullName -Pattern 'Loaded soundfont' -Quiet)) {
        Write-Host "::warning::Soundfont not loaded (expected on runners without an audio device)"
    }
    if (Select-String -Path $log.FullName -Pattern 'Traceback' -Quiet) {
        Write-Host "::warning::Log contains a Python traceback"
    }

    Write-Host '----- app log -----'
    Get-Content $log.FullName
    Write-Host '-------------------'
}

Get-Process -Name 'ChordNotepad' -ErrorAction SilentlyContinue | Stop-Process -Force
if ($failed) { exit 1 }
Write-Host 'Smoke test passed'

<#
.SYNOPSIS
    Package the onedir PyInstaller build as an MSIX for the Microsoft Store.

.DESCRIPTION
    Stages the app folder, generates the tile/logo assets from the SVG icon,
    indexes them into resources.pri, fills in AppxManifest.xml and runs
    makeappx. The package is left unsigned: the Store re-signs it on ingestion.
    To sideload it for local testing, sign it yourself with a self-signed cert
    whose subject equals -Publisher (see docs/RELEASE.md).

    Needs the Windows SDK (makeappx.exe, makepri.exe) and ImageMagick (magick).

.EXAMPLE
    $env:CHORD_NOTEPAD_ONEDIR = '1'
    pipenv run pyinstaller --clean --distpath dist-store --workpath build-store chord-notepad.spec
    ./packaging/msix/build_msix.ps1 -AppDir dist-store/ChordNotepad -OutFile dist-store/ChordNotepad.msix `
        -Version 0.3.2 -IdentityName 12345Tibi.ChordNotepad -Publisher 'CN=XXXXXXXX-...' `
        -PublisherDisplayName 'Tiberiu Chibici'
#>
param(
    [Parameter(Mandatory)] [string] $AppDir,
    [Parameter(Mandatory)] [string] $OutFile,
    # Base version (e.g. 0.3.2). The Store reserves the 4th field, so it is
    # always packaged as MAJOR.MINOR.PATCH.0.
    [Parameter(Mandatory)] [string] $Version,
    [Parameter(Mandatory)] [string] $IdentityName,
    [Parameter(Mandatory)] [string] $Publisher,
    [Parameter(Mandatory)] [string] $PublisherDisplayName,
    [string] $DisplayName = 'Chord Notepad',
    [string] $IconSvg = (Join-Path $PSScriptRoot '../../resources/chord-notepad-icon.svg')
)

$ErrorActionPreference = 'Stop'

function Find-SdkTool([string] $Name) {
    $kits = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
    $tool = Get-ChildItem -Path $kits -Filter $Name -Recurse -Depth 2 -ErrorAction SilentlyContinue |
        Where-Object { $_.Directory.Name -eq 'x64' -and $_.Directory.Parent.Name -match '^\d+(\.\d+)+$' } |
        Sort-Object { [version]$_.Directory.Parent.Name } -Descending |
        Select-Object -First 1
    if (-not $tool) { throw "$Name not found under $kits. Install the Windows 10/11 SDK." }
    return $tool.FullName
}

function Invoke-Native([string] $Exe, [string[]] $Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$(Split-Path $Exe -Leaf) failed with exit code $LASTEXITCODE" }
}

$parts = @($Version.Split('.') | ForEach-Object { [int]$_ })
while ($parts.Count -lt 3) { $parts += 0 }
$packageVersion = '{0}.{1}.{2}.0' -f $parts[0], $parts[1], $parts[2]

$makeappx = Find-SdkTool 'makeappx.exe'
$makepri = Find-SdkTool 'makepri.exe'
Write-Host "makeappx: $makeappx"
Write-Host "makepri:  $makepri"

$work = Join-Path ([IO.Path]::GetTempPath()) ("chord-notepad-msix-" + [guid]::NewGuid())
$stage = Join-Path $work 'stage'
$priRoot = Join-Path $work 'pri'
New-Item -ItemType Directory -Path $stage, $priRoot | Out-Null

try {
    Write-Host "Staging $AppDir"
    Copy-Item -Path (Join-Path $AppDir '*') -Destination $stage -Recurse

    # Name, width, height, icon size inside the canvas. Qualified file names
    # (scale-*, targetsize-*) are resolved through resources.pri, which is why
    # the manifest can refer to plain Assets\Square44x44Logo.png.
    $assets = @(
        @('StoreLogo.scale-100', 50, 50, 50),
        @('StoreLogo.scale-200', 100, 100, 100),
        @('Square44x44Logo.scale-100', 44, 44, 44),
        @('Square44x44Logo.scale-200', 88, 88, 88),
        @('Square150x150Logo.scale-100', 150, 150, 100),
        @('Square150x150Logo.scale-200', 300, 300, 200),
        @('Wide310x150Logo.scale-100', 310, 150, 100),
        @('Wide310x150Logo.scale-200', 620, 300, 200)
    )
    # Taskbar / Start list icons. The unplated variants stop Windows drawing
    # the icon small on an accent-colored square.
    foreach ($size in 16, 24, 32, 48, 256) {
        $assets += , @("Square44x44Logo.targetsize-$size", $size, $size, $size)
        $assets += , @("Square44x44Logo.targetsize-${size}_altform-unplated", $size, $size, $size)
    }

    $assetDir = Join-Path $priRoot 'Assets'
    New-Item -ItemType Directory -Path $assetDir | Out-Null
    foreach ($a in $assets) {
        $name, $w, $h, $icon = $a
        Invoke-Native 'magick' @(
            '-background', 'none', '-density', '600', $IconSvg,
            '-resize', "${icon}x${icon}", '-gravity', 'center', '-extent', "${w}x${h}",
            (Join-Path $assetDir "$name.png"))
    }

    $manifest = Get-Content -Raw (Join-Path $PSScriptRoot 'AppxManifest.xml.in')
    $tokens = @{
        IDENTITY_NAME          = $IdentityName
        PUBLISHER              = $Publisher
        PUBLISHER_DISPLAY_NAME = $PublisherDisplayName
        DISPLAY_NAME           = $DisplayName
        VERSION                = $packageVersion
    }
    foreach ($key in $tokens.Keys) {
        $manifest = $manifest.Replace("{{$key}}", [Security.SecurityElement]::Escape($tokens[$key]))
    }
    if ($manifest -match '\{\{\w+\}\}') { throw "Unreplaced token in manifest: $($Matches[0])" }
    $manifestPath = Join-Path $stage 'AppxManifest.xml'
    Set-Content -Path $manifestPath -Value $manifest -Encoding utf8

    # Index only the assets. Pointing makepri at the whole stage would also
    # scan the thousands of files PyInstaller puts in _internal.
    $priConfig = Join-Path $work 'priconfig.xml'
    Invoke-Native $makepri @('createconfig', '/cf', $priConfig, '/dq', 'en-US', '/pv', '10.0.0', '/o')
    # The default config splits scale/language variants into separate .pri
    # files meant for resource packs. This is a single package, so keep every
    # variant in resources.pri or Windows never sees the scale-200 assets.
    $priXml = [xml](Get-Content -Raw $priConfig)
    $packaging = $priXml.SelectSingleNode('//packaging')
    if ($packaging) { [void]$packaging.ParentNode.RemoveChild($packaging) }
    $priXml.Save($priConfig)
    Invoke-Native $makepri @('new', '/pr', $priRoot, '/cf', $priConfig, '/mn', $manifestPath,
        '/of', (Join-Path $stage 'resources.pri'), '/o')
    Copy-Item -Path $assetDir -Destination $stage -Recurse

    $outDir = Split-Path -Parent $OutFile
    if ($outDir) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }
    Invoke-Native $makeappx @('pack', '/d', $stage, '/p', $OutFile, '/o')
    Write-Host "Built $OutFile (version $packageVersion)"
}
finally {
    Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}

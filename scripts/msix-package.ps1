param(
    [Parameter(Mandatory=$true)]
    [string]$InstallerPath,

    [Parameter(Mandatory=$true)]
    [string]$Version,

    [Parameter(Mandatory=$true)]
    [string]$OutputDir,

    [Parameter(Mandatory=$false)]
    [string]$IconsDir = ""
)

$ErrorActionPreference = "Stop"

$PackageName = "OrdoERP"
$Architecture = "x64"
$Publisher = "CN=Ordo ERP"
$PublisherDisplayName = "Ordo ERP"
$DisplayName = "Ordo ERP - Sistema de Gestión"
$Description = "Sistema de gestión ERP completo con facturación electrónica ARCA/AFIP"

# --- Find MakeAppx.exe ---
$MakeAppx = Get-ChildItem -Path "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse -Filter "makeappx.exe" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "\\x64\\" } |
    Select-Object -First 1 -ExpandProperty FullName

if (-not $MakeAppx) {
    # Try PATH
    $MakeAppx = (Get-Command "makeappx.exe" -ErrorAction SilentlyContinue).Source
}
if (-not $MakeAppx) {
    Write-Error "MakeAppx.exe not found. Install Windows SDK."
    exit 1
}
Write-Host "Using MakeAppx: $MakeAppx"

# --- Create temp directories ---
$ExtractDir = Join-Path $OutputDir "extracted"
$StagingDir = Join-Path $OutputDir "msix-staging"

foreach ($d in @($ExtractDir, $StagingDir)) {
    Remove-Item -Path $d -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $d -Force | Out-Null
}

New-Item -ItemType Directory -Path (Join-Path $StagingDir "App") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $StagingDir "Assets") -Force | Out-Null

# --- Step 1: Extract NSIS installer ---
Write-Host "Extracting: $InstallerPath"

# Try 7-Zip first (works with NSIS LZMA archives)
$7zPath = (Get-Command "7z.exe" -ErrorAction SilentlyContinue).Source
if (-not $7zPath) {
    $7zExe = Get-ChildItem -Path "C:\Program Files\7-Zip" -Filter "7z.exe" -Recurse | Select-Object -First 1
    if ($7zExe) { $7zPath = $7zExe.FullName }
}

if ($7zPath) {
    Write-Host "Using 7-Zip: $7zPath"
    $extractLog = Join-Path $OutputDir "7z-extract.log"
    & $7zPath x "$InstallerPath" -o"$ExtractDir" -y > $extractLog 2>&1
} else {
    Write-Host "7-Zip not found, trying NSIS silent install..."
    $proc = Start-Process -FilePath $InstallerPath -ArgumentList "/S /D=$ExtractDir" -Wait -PassThru -NoNewWindow
    if ($proc.ExitCode -ne 0) {
        Write-Error "Installer exited with code $($proc.ExitCode)"
        exit 1
    }
}

# Verify extraction
$files = Get-ChildItem -Path $ExtractDir -Recurse -File
if (-not $files) {
    Write-Error "No files extracted - aborting"
    exit 1
}
Write-Host "Extracted $($files.Count) files"

# --- Step 2: Clean up NSIS junk ---
Write-Host "Cleaning up NSIS installer junk..."
# Remove NSIS-specific directories (these begin with $)
Get-ChildItem -Path $ExtractDir -Directory | Where-Object { $_.Name -like '$*' } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
# Remove NSIS installer helper files
Get-ChildItem -Path $ExtractDir -File | Where-Object { $_.Name -like 'uninstall*' -or $_.Name -like 'installer-hooks*' } |
    Remove-Item -Force -ErrorAction SilentlyContinue
# Remove any auto-generated MSIX files from source (MakeAppx regenerates them)
Get-ChildItem -Path $ExtractDir -File | Where-Object { $_.Name -eq '[Content_Types].xml' -or $_.Name -eq 'AppxBlockMap.xml' -or $_.Name -eq 'AppxManifest.xml' } |
    Remove-Item -Force -ErrorAction SilentlyContinue

# --- Step 3: Copy files to App/ ---
Write-Host "Copying files to MSIX staging..."
Copy-Item -Path "$ExtractDir\*" -Destination (Join-Path $StagingDir "App") -Recurse -Force

# --- Step 4: Generate AppxManifest.xml ---
Write-Host "Creating AppxManifest.xml..."

# Find main executable: it's the .exe that is NOT the backend
$MainExe = Get-ChildItem -Path (Join-Path $StagingDir "App") -Filter "*.exe" -Recurse |
    Where-Object { $_.Name -notlike '*ga-erp-backend*' -and $_.Name -notlike '*backend*' } |
    Sort-Object Length -Descending | Select-Object -First 1

if (-not $MainExe) {
    # Fallback: any exe
    $MainExe = Get-ChildItem -Path (Join-Path $StagingDir "App") -Filter "*.exe" -Recurse | Select-Object -First 1
}
if (-not $MainExe) {
    Write-Error "No executable found in extracted files"
    exit 1
}
$RelativeExePath = "App\$($MainExe.Name)"
Write-Host "Entry point: $RelativeExePath ($($MainExe.Length) bytes)"

$Manifest = [System.Text.StringBuilder]::new()
[void]$Manifest.AppendLine('<?xml version="1.0" encoding="utf-8"?>')
[void]$Manifest.AppendLine('<Package')
[void]$Manifest.AppendLine('  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"')
[void]$Manifest.AppendLine('  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"')
[void]$Manifest.AppendLine('  xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"')
[void]$Manifest.AppendLine('  IgnorableNamespaces="uap rescap">')
[void]$Manifest.AppendLine('')
[void]$Manifest.AppendLine("  <Identity Name=`"$PackageName`" Publisher=`"$Publisher`" Version=`"$Version`" />")
[void]$Manifest.AppendLine('')
[void]$Manifest.AppendLine('  <Properties>')
[void]$Manifest.AppendLine("    <DisplayName>$DisplayName</DisplayName>")
[void]$Manifest.AppendLine("    <PublisherDisplayName>$PublisherDisplayName</PublisherDisplayName>")
[void]$Manifest.AppendLine("    <Description>$Description</Description>")
[void]$Manifest.AppendLine('    <Logo>Assets\StoreLogo.png</Logo>')
[void]$Manifest.AppendLine('  </Properties>')
[void]$Manifest.AppendLine('')
[void]$Manifest.AppendLine('  <Resources>')
[void]$Manifest.AppendLine('    <Resource Language="es-es" />')
[void]$Manifest.AppendLine('  </Resources>')
[void]$Manifest.AppendLine('')
[void]$Manifest.AppendLine('  <Dependencies>')
[void]$Manifest.AppendLine('    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.22621.0" />')
[void]$Manifest.AppendLine('  </Dependencies>')
[void]$Manifest.AppendLine('')
[void]$Manifest.AppendLine('  <Capabilities>')
[void]$Manifest.AppendLine('    <rescap:Capability Name="runFullTrust" />')
[void]$Manifest.AppendLine('  </Capabilities>')
[void]$Manifest.AppendLine('')
[void]$Manifest.AppendLine('  <Applications>')
[void]$Manifest.AppendLine("    <Application Id=`"$PackageName`" Executable=`"$RelativeExePath`" EntryPoint=`"Windows.FullTrustApplication`">")
[void]$Manifest.AppendLine('      <uap:VisualElements')
[void]$Manifest.AppendLine("        DisplayName=`"$DisplayName`"")
[void]$Manifest.AppendLine("        Description=`"$Description`"")
[void]$Manifest.AppendLine('        Square150x150Logo="Assets\Square150x150Logo.png"')
[void]$Manifest.AppendLine('        Square44x44Logo="Assets\Square44x44Logo.png"')
[void]$Manifest.AppendLine('        BackgroundColor="transparent" />')
[void]$Manifest.AppendLine('    </Application>')
[void]$Manifest.AppendLine('  </Applications>')
[void]$Manifest.AppendLine('')
[void]$Manifest.AppendLine('</Package>')

$ManifestPath = Join-Path $StagingDir "AppxManifest.xml"
Set-Content -Path $ManifestPath -Value $Manifest.ToString() -Encoding UTF8
Write-Host "AppxManifest.xml created"

# --- Step 5: Create store assets ---
Write-Host "Creating assets..."
$AssetSizes = @{
    "StoreLogo.png" = 50
    "Square44x44Logo.png" = 44
    "Square150x150Logo.png" = 150
}

# Try to use existing icons first
if ($IconsDir -and (Test-Path $IconsDir)) {
    $iconFiles = Get-ChildItem -Path $IconsDir -File
    Write-Host "Found $($iconFiles.Count) icon files in $IconsDir"
    # Copy icon files as-is, MakeAppx is lenient about asset requirements for desktop apps
    foreach ($icon in $iconFiles) {
        Copy-Item -Path $icon.FullName -Destination (Join-Path $StagingDir "Assets") -Force -ErrorAction SilentlyContinue
    }
}

# Generate placeholder PNG assets for required Store images (1px transparent)
# MakeAppx requires at least StoreLogo.png
$AssetsDir = Join-Path $StagingDir "Assets"
if (-not (Test-Path (Join-Path $AssetsDir "StoreLogo.png"))) {
    Write-Host "Warning: No StoreLogo.png found. Creating minimal placeholder."
    # A minimal 50x50 transparent PNG (base64)
    $minimalPng = [Convert]::FromBase64String("iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAYAAAAeP4ixAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAAZdEVYdFNvZnR3YXJlAHBhaW50Lm5ldCA0LjAuMjHxIGmVAAAAI0lEQVRIS+3RAQ0AAAjDMO3f9EADKsMAAAAAAAAAAAAAAH8DB1oAAfqoZAMAAAAASUVORK5CYII=")
    Set-Content -Path (Join-Path $AssetsDir "StoreLogo.png") -Value $minimalPng -Encoding Byte
    Copy-Item (Join-Path $AssetsDir "StoreLogo.png") (Join-Path $AssetsDir "Square44x44Logo.png") -Force
    Copy-Item (Join-Path $AssetsDir "StoreLogo.png") (Join-Path $AssetsDir "Square150x150Logo.png") -Force
}

# --- Step 6: Create MSIX with MakeAppx.exe ---
$MsixOutput = Join-Path $OutputDir "${PackageName}_${Version}_${Architecture}.msix"
Write-Host "Creating MSIX: $MsixOutput"

& $MakeAppx pack /d $StagingDir /p $MsixOutput /l

if ($LASTEXITCODE -ne 0) {
    Write-Error "MakeAppx.exe failed with exit code $LASTEXITCODE"
    # Show output for debugging
    Write-Host "--- Staging dir contents ---"
    Get-ChildItem -Path $StagingDir -Recurse | Select-Object FullName, Length | Format-Table -AutoSize
    exit 1
}

Write-Host "MSIX package created successfully!"
Write-Host "Output: $MsixOutput"

# Clean up temp
Remove-Item -Path $ExtractDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $StagingDir -Recurse -Force -ErrorAction SilentlyContinue

return $MsixOutput

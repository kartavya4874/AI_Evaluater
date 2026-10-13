# setup_poppler.ps1
$popplerVersion = "24.08.0-0"
$downloadUrl = "https://github.com/oschwartz10612/poppler-windows/releases/download/v$popplerVersion/Release-$popplerVersion.zip"
$tempZip = Join-Path $PSScriptRoot "poppler.zip"
$extractPath = Join-Path $PSScriptRoot "bin\poppler"

if (-not (Test-Path "bin")) {
    New-Item -ItemType Directory -Path "bin" | Out-Null
}

if (Test-Path $extractPath) {
    Write-Host "Poppler already exists at $extractPath. Skipping download." -ForegroundColor Green
} else {
    Write-Host "Downloading Poppler $popplerVersion..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $downloadUrl -OutFile $tempZip
    
    Write-Host "Extracting Poppler..." -ForegroundColor Cyan
    Expand-Archive -Path $tempZip -DestinationPath $extractPath
    
    Write-Host "Cleaning up..." -ForegroundColor Cyan
    Remove-Item $tempZip
}

# Find the bin directory inside the extracted poppler folder
$binPath = Get-ChildItem -Path $extractPath -Recurse -Filter "bin" | Select-Object -ExpandProperty FullName | Where-Object { $_ -like "*Library\bin*" } | Select-Object -First 1

if ($binPath) {
    Write-Host "Poppler bin found at: $binPath" -ForegroundColor Green
    
    # Update .env file
    $envFile = Join-Path $PSScriptRoot "backend\.env"
    if (Test-Path $envFile) {
        $content = Get-Content $envFile
        if ($content -match "POPPLER_PATH=") {
            $content = $content -replace "POPPLER_PATH=.*", "POPPLER_PATH=$binPath"
        } else {
            $content += "`nPOPPLER_PATH=$binPath"
        }
        $content | Set-Content $envFile
        Write-Host "Updated .env with POPPLER_PATH" -ForegroundColor Green
    } else {
        Write-Host "Notice: .env file not found at $envFile. Please update it manually." -ForegroundColor Yellow
    }
} else {
    Write-Warning "Could not find 'bin' directory in extracted Poppler files."
}

Write-Host "Poppler setup complete!" -ForegroundColor Green

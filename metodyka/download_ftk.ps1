# Pobiera z GitHub release v15 FinOps toolkit (Microsoft, licencja MIT) pliki używane przez skrypty demo.
# Pliki trafiają do metodyka\ftk-v15\, który jest w .gitignore.
# Źródło: https://github.com/microsoft/finops-toolkit/releases/tag/v15
param(
    [string[]]$Assets = @(
        'finops-hub-v15.zip',
        'finops-hub-dashboard.json',
        'finops-hub-fabric-setup-Hub.kql',
        'finops-hub-fabric-setup-Ingestion.kql',
        'PowerBI-kql.zip'
    )
)
$ErrorActionPreference = 'Stop'
$dest = Join-Path $PSScriptRoot 'ftk-v15'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
foreach ($a in $Assets) {
    $url = "https://github.com/microsoft/finops-toolkit/releases/download/v15/$a"
    Write-Host "Pobieram $url"
    Invoke-WebRequest -Uri $url -OutFile (Join-Path $dest $a)
}
$hubZip = Join-Path $dest 'finops-hub-v15.zip'
if (Test-Path $hubZip) {
    Expand-Archive -Path $hubZip -DestinationPath (Join-Path $dest 'hub') -Force
}
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/microsoft/finops-toolkit/main/LICENSE' -OutFile (Join-Path $dest 'LICENSE')
Write-Host "Gotowe: $dest"

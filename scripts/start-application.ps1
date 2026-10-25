param(
    [string]$Python = 'python',
    [string]$Data = (Join-Path $env:USERPROFILE '.hpc-forest/application'),
    [ValidateRange(1, 65535)][int]$Port = 8767,
    [string[]]$Campaign = @()
)

$ErrorActionPreference = 'Stop'
$appArguments = @('-m', 'hpc_forest.webapp', '--data', $Data, '--port', [string]$Port)
foreach ($campaignPath in $Campaign) {
    $appArguments += @('--campaign', $campaignPath)
}
Write-Host "Application Forest : http://127.0.0.1:$Port"
Write-Host 'Ctrl+C pour arrêter le serveur. Les projets restent sauvegardés.'
& $Python @appArguments
exit $LASTEXITCODE

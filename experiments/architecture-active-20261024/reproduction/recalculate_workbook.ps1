$ErrorActionPreference = 'Stop'
$forestWorkbookPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../outputs/architecture-active/COMPARAISON-ROMEO.xlsx'))
if (-not (Test-Path -LiteralPath $forestWorkbookPath -PathType Leaf)) { throw 'Generated workbook missing' }
$forestExcel = $null
$forestWorkbook = $null
try {
    $forestExcel = New-Object -ComObject Excel.Application
    $forestExcel.Visible = $false
    $forestExcel.DisplayAlerts = $false
    $forestExcel.AskToUpdateLinks = $false
    $forestExcel.AutomationSecurity = 3
    $forestWorkbook = $forestExcel.Workbooks.Open($forestWorkbookPath, 0, $false)
    $forestExcel.CalculateFullRebuild()
    $forestWorkbook.Save()
    @{engine='Microsoft Excel';version=$forestExcel.Version;recalculated=$true;path=$forestWorkbookPath} | ConvertTo-Json -Compress
}
finally {
    if ($null -ne $forestWorkbook) {
        $forestWorkbook.Close($false)
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($forestWorkbook)
    }
    if ($null -ne $forestExcel) {
        $forestExcel.Quit()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($forestExcel)
    }
}

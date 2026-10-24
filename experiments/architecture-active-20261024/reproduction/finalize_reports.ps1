$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$forestPython = 'C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/work/hpc-forest-mcp-venv/Scripts/python.exe'
$forestDocumentPython = 'C:/Users/nicol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$forestPlotPython = Join-Path $PSScriptRoot 'plot-venv/Scripts/python.exe'

function Invoke-ForestReport {
    param([string]$Interpreter, [string]$Script, [string[]]$Parameters = @())
    & $Interpreter (Join-Path $PSScriptRoot $Script) @Parameters
    if ($LASTEXITCODE -ne 0) { throw "Report step failed: $Script ($LASTEXITCODE)" }
}

Invoke-ForestReport $forestPython 'audit_campaigns.py' @('--require-complete')
Invoke-ForestReport $forestPython 'validate_volume_controls.py'
Invoke-ForestReport $forestPython 'analyze.py' @('--require-complete')
Invoke-ForestReport $forestPython 'resources_report.py'
Invoke-ForestReport $forestPython 'report.py'
Invoke-ForestReport $forestPython 'synthesis.py'
Invoke-ForestReport $forestPlotPython 'plot_results.py'
Invoke-ForestReport $forestPlotPython 'plot_allocations.py'
Invoke-ForestReport $forestDocumentPython 'workbook.py'
& (Join-Path $PSScriptRoot 'recalculate_workbook.ps1')
Invoke-ForestReport $forestDocumentPython 'workbook.py' @('--verify')
Invoke-ForestReport $forestPython 'validate_outputs.py'
Invoke-ForestReport $forestPython 'publication_preflight.py'
Invoke-ForestReport $forestPython 'scan_private_tokens.py'

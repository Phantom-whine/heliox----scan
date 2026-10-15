# HELIOX Services Launcher for PowerShell
Set-Location -Path $PSScriptRoot
Write-Host "Starting HELIOX Web API and Services..." -ForegroundColor Cyan
python start_services.py $args

@echo off
title HELIOX SaaS Terminal ^& Services
cd /d "%~dp0"
echo Starting HELIOX Web API and Services...
python start_services.py %*
pause

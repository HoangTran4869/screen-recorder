@echo off
set "D=%~dp0app"
set "TCL_LIBRARY=%D%\tcl\tcl8.6"
set "TK_LIBRARY=%D%\tcl\tk8.6"
start "" "%D%\pythonw.exe" "%D%\app.pyw"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
& "$ScriptDir\.venv\Scripts\python.exe" main.py $args

@echo off
rem Stop what start_demo.bat started: backend (:8000), frontend (:3000) and the GPU tunnel (:8001).
rem The LLM service on the GPU server keeps running (stop it there with: pkill -f serve_openai.py).
powershell -NoProfile -Command "foreach ($port in 8000, 3000, 8001) { $ids = (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue).OwningProcess | Sort-Object -Unique; foreach ($id in $ids) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue; Write-Output ('stopped port ' + $port + ' (pid ' + $id + ')') } }"
echo Done.

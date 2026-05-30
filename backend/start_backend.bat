@echo off
cd /d "C:\Users\Giuliano\Desktop\GA_ERP_FIXED\backend"
set PYTHONPATH=C:\Users\Giuliano\Desktop\GA_ERP_FIXED\backend
call venv\Scripts\activate.bat
python -m uvicorn main:app --reload --port 8000
pause
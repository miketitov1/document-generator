@echo off
cd /d "%~dp0"
REM Start FastAPI backend (uvicorn)
start "FastAPI Backend" cmd /k "".venv\Scripts\python.exe" -m uvicorn --app-dir . src.web.api.main_api:app --reload --host 0.0.0.0 --port 8000"

REM Wait a moment for the backend to start (optional)
timeout /t 2 /nobreak >nul

REM Start Streamlit frontend
start "Streamlit Frontend" cmd /k "".venv\Scripts\python.exe" -m streamlit run src\web\frontend\app.py --server.port 8501"
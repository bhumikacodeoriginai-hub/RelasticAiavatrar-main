@echo off
echo ============================================
echo   AI Avatar Receptionist - Starting...
echo ============================================
echo.

REM Check if Python virtual environment exists
if not exist "backend\venv" (
    echo [1/4] Creating Python virtual environment...
    cd backend
    python -m venv venv
    cd ..
)

REM Activate venv and install dependencies
echo [2/4] Installing Python dependencies...
cd backend
call venv\Scripts\activate.bat
pip install -r requirements-windows.txt --quiet 2>nul
cd ..

REM Check if Node modules exist
if not exist "frontend\node_modules" (
    echo [3/4] Installing frontend dependencies...
    cd frontend
    call npm install --silent
    cd ..
) else (
    echo [3/4] Frontend dependencies already installed.
)

echo [4/4] Starting servers...
echo.
echo ============================================
echo   STARTING BACKEND (port 8000)
echo   STARTING FRONTEND (port 5173)
echo ============================================
echo.
echo   Backend API:  http://localhost:8000
echo   API Docs:     http://localhost:8000/docs
echo   Frontend:     http://localhost:5173
echo.
echo   Press Ctrl+C to stop both servers.
echo ============================================
echo.

REM Start backend in background
cd backend
start "AI-Backend" cmd /k "call venv\Scripts\activate.bat && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
cd ..

REM Start frontend
cd frontend
start "AI-Frontend" cmd /k "npm run dev"
cd ..

echo.
echo Both servers are starting in separate windows.
echo Open http://localhost:5173 in your browser.
echo.
pause

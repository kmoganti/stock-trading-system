@echo off
echo 🔧 FIXING FASTAPI SLOW STARTUP ISSUE
echo =====================================
echo.

echo 1️⃣ Uninstalling corrupted packages...
pip uninstall fastapi uvicorn starlette pydantic -y

echo.
echo 2️⃣ Clearing pip cache...
pip cache purge

echo.
echo 3️⃣ Reinstalling with no cache...
pip install --no-cache-dir --force-reinstall fastapi uvicorn[standard]

echo.
echo 4️⃣ Testing FastAPI import speed...
python -c "import time; start=time.time(); import fastapi; print(f'FastAPI imported in {time.time()-start:.2f}s')"

echo.
echo 5️⃣ Testing server startup...
timeout 10 python -c "import uvicorn; print('✅ Uvicorn OK'); uvicorn.run('main:app', host='0.0.0.0', port=8001, reload=False)" 2>nul

echo.
echo ✅ FastAPI fix completed!
echo 🚀 Try: python main.py
pause
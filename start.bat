@echo off
REM ============================================
REM  多平台智能托管 SaaS + vMall 一键启动 (Win)
REM  前提: Python 3.10+, Node 18+, MySQL, Redis
REM ============================================

echo.
echo ========================================
echo  多平台智能托管 SaaS + vMall
echo ========================================
echo.

set SAAS_BE=backend
set SAAS_FE=frontend
set VMALL_BE=vmall_system\backend

REM --- 1. 验证环境 ---
echo [1/4] 验证环境...
cd %SAAS_BE%
python verify.py
if %ERRORLEVEL% NEQ 0 (
    echo 环境验证未通过，请修复后重试
    pause
    exit /b 1
)
cd ..

REM --- 2. 初始化数据 ---
echo.
echo [2/4] 初始化数据...
cd %SAAS_BE%
python seed.py --backfill --full 2>nul
echo   SaaS 种子数据已就绪
cd ..

cd %VMALL_BE%
python seed_vmall.py 2>nul
echo   vMall 种子数据已就绪
cd ..\..

REM --- 3. 启动后端 ---
echo.
echo [3/4] 启动后端服务...
start "SaaS Backend :8012" cmd /c "cd %SAAS_BE% && uvicorn main:app --host 0.0.0.0 --port 8012"
start "vMall Backend :8020" cmd /c "cd %VMALL_BE% && uvicorn main:app --host 0.0.0.0 --port 8020"
echo   SaaS Backend :8012 (等待就绪...)
echo   vMall Backend :8020 (等待就绪...)
timeout /t 5 /nobreak >nul

REM --- 4. 启动前端 ---
echo.
echo [4/4] 启动前端...
cd %SAAS_FE%
start "Admin :8093" cmd /c "npm run dev:admin"
start "Merchant :8094" cmd /c "npm run dev:merchant"
start "Service :8095" cmd /c "npm run dev:service"
echo   管理后台   http://localhost:8093
echo   商户工作台 http://localhost:8094
echo   客服工作台 http://localhost:8095
cd ..

echo.
echo ========================================
echo  全部服务已启动！
echo.
echo  登录信息:
echo    :8093  super_admin / 123456
echo    :8094  admin / 123456
echo    :8095  service / 123456
echo ========================================
pause

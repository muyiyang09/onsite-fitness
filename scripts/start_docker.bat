@echo off
setlocal EnableDelayedExpansion
REM ============================================================
REM  �������� �� Docker һ��������Windows��
REM  ˫������ �� ������ִ��: scripts\start_docker.bat
REM ============================================================

cd /d "%~dp0\.."
echo === �������� �� Docker һ������ ===
echo.

REM ---- 1. ��� Docker ----
where docker >nul 2>nul
if errorlevel 1 (
    echo [ERROR] δ��⵽ docker�����Ȱ�װ������ Docker Desktop��
    pause
    exit /b 1
)
docker compose version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] δ��⵽ docker compose v2�������� Docker Desktop��
    pause
    exit /b 1
)
docker info >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Docker �ػ�����δ���У������� Docker Desktop �����ԡ�
    pause
    exit /b 1
)

REM ---- 2. ��� .env ----
if not exist .env (
    echo [WARN] δ�ҵ� .env���Ѵ� .env.example ����ģ�塣
    copy /y .env.example .env >nul
    echo ���ȱ༭ .env ��д�����MySQL/Redis/MinIO ���롢JWT/AES ��Կ����Ȼ���������б��ű���
    echo ��Կ����: openssl rand -hex 32
    pause
    exit /b 1
)

REM ---- 3. У���������ǿգ�docker-compose �б�� ?required ���----
set "MISSING="
for %%V in (MYSQL_ROOT_PASSWORD MYSQL_APP_PASSWORD REDIS_PASSWORD MILVUS_MINIO_ACCESS_KEY MILVUS_MINIO_SECRET_KEY) do (
    findstr /b /c:"%%V=" .env ^| findstr /r /c:"=." >nul ^|^| set "MISSING=!MISSING! %%V"
)
if not "!MISSING!"=="" (
    echo [ERROR] .env �����±�����Ϊ��:!MISSING!
    echo ��д���������б��ű���
    pause
    exit /b 1
)

REM ---- 4. ���������� ----
echo ^>^> docker compose up -d --build
docker compose up -d --build
if errorlevel 1 (
    echo [ERROR] ����ʧ�ܣ���ִ�� docker compose logs -f �鿴��־��
    pause
    exit /b 1
)

REM ---- 5. �ȴ����ķ��񽡿����Լ 3 ���ӣ�Milvus �״�����������----
echo ^>^> �ȴ��������...
set /a TRIES=0
:wait_loop
set /a TRIES+=1
if !TRIES! gtr 36 goto wait_done
docker inspect --format "{{.State.Health.Status}}" sports-backend 2>nul ^| findstr /c:"healthy" >nul ^|^| goto wait_retry
docker inspect --format "{{.State.Health.Status}}" sports-ai 2>nul ^| findstr /c:"healthy" >nul ^|^| goto wait_retry
goto wait_done
:wait_retry
ping 127.0.0.1 -n 6 >nul
goto wait_loop
:wait_done

REM ---- 6. ��ӡ������� ----
echo.
echo === ������ɣ�������� ===
echo   ������ǰ��  : http://localhost:5173
echo   ��� API    : http://localhost:8080
echo   AI ΢����   : http://localhost:18000/healthz
echo   Attu Milvus : http://localhost:8001
echo   Grafana     : http://localhost:3000  (admin / admin)
echo   Prometheus  : http://localhost:9090
echo.
echo ��������:
echo   �鿴��־ : docker compose logs -f ������
echo   ֹͣ���� : docker compose down
echo   ð�̲��� : bash scripts/smoke_test.sh
pause

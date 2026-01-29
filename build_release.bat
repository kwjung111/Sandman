@echo off
echo ==============================================
echo NCP Server Manager - Docker Build & Export Tool
echo ==============================================
echo.

echo [1/2] Building Docker Image... (ncp-server-manager)
docker build -t ncp-server-manager .
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build failed! Please make sure Docker Desktop is running.
    pause
    exit /b
)

echo.
echo [2/2] Saving Image to file... (ncp-server-manager.tar)
docker save -o ncp-server-manager.tar ncp-server-manager
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to save file!
    pause
    exit /b
)

echo.
echo ==============================================
echo [SUCCESS] File created: ncp-server-manager.tar
echo ==============================================
echo.
echo [How to Deploy]
echo 1. Copy 'ncp-server-manager.tar' and '.env' to your server.
echo 2. Run the following commands on the server:
echo.
echo    docker load -i ncp-server-manager.tar
echo    docker run -d --name ncp-manager --env-file .env -p 8000:8000 --restart unless-stopped ncp-server-manager
echo.
pause
@echo off
setlocal
set "STUDIO_ROOT=%~dp0.."
if not defined STUDIO_PYTHON set "STUDIO_PYTHON=python"
pushd "%STUDIO_ROOT%"
"%STUDIO_PYTHON%" -m studio %*
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%

@echo off
rem MTK Unbrick - Windows launcher (double-click or run from cmd)
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

where py >nul 2>nul
if not errorlevel 1 goto :run_py
where python >nul 2>nul
if not errorlevel 1 goto :run_python

echo [!] Python 3 not found.
echo     Install from https://www.python.org/downloads/ and check
echo     "Add python.exe to PATH", then run this script again.
set RC=1
goto :done

:run_py
py -3 mtk_unbrick.py %*
set RC=%ERRORLEVEL%
goto :done

:run_python
python mtk_unbrick.py %*
set RC=%ERRORLEVEL%
goto :done

:done
if not "%RC%"=="0" pause
exit /b %RC%

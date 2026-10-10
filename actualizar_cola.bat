@echo off
rem Rellena la cola hasta 30 dias y la sube a GitHub. Lo lanza el Programador de tareas cada lunes.
cd /d "%~dp0generador"
set PYTHONIOENCODING=utf-8
python generar_cola.py --dias 30 --subir >> "%~dp0salida\actualizar_cola.log" 2>&1

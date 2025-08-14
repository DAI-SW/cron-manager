#!/bin/bash
# cron-manager-wrapper.sh
# Wrapper für Cron Manager mit virtualenv Support

# Pfad zur virtuellen Umgebung anpassen
VENV_PATH="/home/dai/python_env/cron_stuff"
SCRIPT_PATH="$VENV_PATH/cron-manager/cron-manager.py"

# Aktiviere virtualenv und führe Script aus
if [ "$EUID" -eq 0 ]; then
    # Als Root: Verwende die virtualenv Python-Umgebung direkt
    "$VENV_PATH/bin/python" "$SCRIPT_PATH" "$@"
else
    # Als normaler User
    source "$VENV_PATH/bin/activate"
    python "$SCRIPT_PATH" "$@"
fi

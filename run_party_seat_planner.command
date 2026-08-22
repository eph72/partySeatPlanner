#!/bin/bash

set -euo pipefail

PLANNER_DIR="$(cd "$(dirname "$0")" && pwd)"
PLANNER_VENV="$PLANNER_DIR/.venv"
PLANNER_VENV_PYTHON="$PLANNER_VENV/bin/python"

pause_after_error() {
    PLANNER_STATUS=$?
    echo
    echo "Party Seat Planner could not start. Review the message above."
    read -r -p "Press Return to close this window..." || true
    exit "$PLANNER_STATUS"
}
trap pause_after_error ERR

compatible_python() {
    "$1" -c 'import sys, tkinter; raise SystemExit(0 if sys.version_info >= (3, 9) and tkinter.TkVersion >= 8.6 else 1)' >/dev/null 2>&1
}

PLANNER_PYTHON=""
for PLANNER_CANDIDATE in \
    /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 \
    /usr/local/bin/python3.13 \
    /opt/homebrew/bin/python3.13 \
    python3.13 python3.14 python3.12 python3.11 python3.10 python3.9 python3
do
    if command -v "$PLANNER_CANDIDATE" >/dev/null 2>&1 && compatible_python "$PLANNER_CANDIDATE"; then
        PLANNER_PYTHON="$(command -v "$PLANNER_CANDIDATE")"
        break
    fi
done

if [[ -z "$PLANNER_PYTHON" ]]; then
    echo "Party Seat Planner needs Python 3.9+ with Tk 8.6+."
    echo "Install Python 3.13 from: https://www.python.org/downloads/macos/"
    echo "Then double-click this file again."
    false
fi

cd "$PLANNER_DIR"

if [[ ! -x "$PLANNER_VENV_PYTHON" ]] || ! compatible_python "$PLANNER_VENV_PYTHON"; then
    echo "Preparing Party Seat Planner for first use..."
    "$PLANNER_PYTHON" -m venv --clear "$PLANNER_VENV"
fi

if ! "$PLANNER_VENV_PYTHON" -c 'import gender_guesser.detector, reportlab' >/dev/null 2>&1; then
    echo "Installing the offline name database and PDF exporter..."
    "$PLANNER_VENV_PYTHON" -m pip install -r "$PLANNER_DIR/requirements.txt"
fi

echo "Starting Party Seat Planner..."
"$PLANNER_VENV_PYTHON" "$PLANNER_DIR/party_seat_planner.py"

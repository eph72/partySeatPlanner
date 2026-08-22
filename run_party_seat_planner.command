#!/bin/bash

set -euo pipefail

PLANNER_DIR="$(cd "$(dirname "$0")" && pwd)"
PLANNER_VENV="$PLANNER_DIR/.venv"
PLANNER_VENV_PYTHON="$PLANNER_VENV/bin/python"
PLANNER_TERMINAL_TTY=""

if [[ "$(uname -s)" == "Darwin" && "${TERM_PROGRAM:-}" == "Apple_Terminal" ]]; then
    PLANNER_TERMINAL_TTY="$(tty 2>/dev/null || true)"
    if [[ "$PLANNER_TERMINAL_TTY" == "not a tty" ]]; then
        PLANNER_TERMINAL_TTY=""
    fi
fi

terminal_window_action() {
    if [[ -z "$PLANNER_TERMINAL_TTY" ]]; then
        return
    fi
    osascript - "$PLANNER_TERMINAL_TTY" "$1" >/dev/null 2>&1 <<'APPLESCRIPT' || true
on run arguments
    set targetTTY to item 1 of arguments
    set requestedAction to item 2 of arguments
    tell application "Terminal"
        repeat with terminalWindow in windows
            repeat with terminalTab in tabs of terminalWindow
                if (tty of terminalTab) is targetTTY then
                    if requestedAction is "hide" then
                        set miniaturized of terminalWindow to true
                    else if requestedAction is "show" then
                        set miniaturized of terminalWindow to false
                        activate
                    end if
                    return
                end if
            end repeat
        end repeat
    end tell
end run
APPLESCRIPT
}

schedule_terminal_close() {
    if [[ -z "$PLANNER_TERMINAL_TTY" ]]; then
        return
    fi
    nohup osascript - "$PLANNER_TERMINAL_TTY" >/dev/null 2>&1 <<'APPLESCRIPT' &
on run arguments
    set targetTTY to item 1 of arguments
    delay 0.4
    tell application "Terminal"
        repeat with terminalWindow in windows
            repeat with terminalTab in tabs of terminalWindow
                if (tty of terminalTab) is targetTTY then
                    close terminalWindow
                    return
                end if
            end repeat
        end repeat
    end tell
end run
APPLESCRIPT
}

pause_after_error() {
    PLANNER_STATUS=$?
    terminal_window_action show
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
terminal_window_action hide
"$PLANNER_VENV_PYTHON" "$PLANNER_DIR/party_seat_planner.py"
schedule_terminal_close
exit 0

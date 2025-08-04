#!/bin/bash

# === CONFIGURATION ===
SCRIPT_DIR="/var/www/cromwell"
VENV_DIR="$SCRIPT_DIR/cw_venv"
ERROR_LOG_FILE="$SCRIPT_DIR/cromwell_error.log"
# EMAIL="followcrom@gmail.com"
EMAIL="hello@followcrom.com"

# === FUNCTION TO HANDLE FAILURES ===
handle_failure() {
    local error_message="$1"
    local timestamp
    timestamp=$(date)

    local full_report="❌ Fitbit2Influx Job Failed ❌
--------------------------------------------------
This is an automated report from the Fitbit2Influx job script.
Error occurred at: $timestamp
Hostname: $(hostname)
Sent to: $EMAIL
--------------------------------------------------
$error_message
--------------------------------------------------
"
    echo "$full_report" > "$ERROR_LOG_FILE"
    echo "$full_report" | mail -s "Fitbit2Influx Job Failed" "$EMAIL"
    echo "[ERROR] $error_message"
    exit 1
}

# === SCRIPT EXECUTION ===

echo "[INFO] Changing to script directory: $SCRIPT_DIR"
cd "$SCRIPT_DIR" || handle_failure "Fatal Error: Could not change directory to $SCRIPT_DIR."

echo "[INFO] Checking for virtual environment at $VENV_DIR"
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    handle_failure "Fatal Error: Virtual environment not found at $VENV_DIR."
fi

echo "[INFO] Activating virtual environment"
source "$VENV_DIR/bin/activate"

echo "[INFO] Running fitbit2influx.py"
PYTHON_OUTPUT=$(python "$SCRIPT_DIR/fitbit2influx.py" 2>&1)
EXIT_CODE=$?
deactivate

if [ $EXIT_CODE -ne 0 ]; then
    handle_failure "Python script failed with exit code $EXIT_CODE.

Output was:
$PYTHON_OUTPUT"
fi

echo "[INFO] Script completed successfully."

SUCCESS_REPORT="Timestamp: $(date)
Hostname: $(hostname)
Status: ✅ Fitbit2Influx Job Succeeded
Sent to: $EMAIL
--------------------------------------------------
✅ The fitbit2influx.py script ran successfully.
--------------------------------------------------
"
echo "$SUCCESS_REPORT" | mail -s "Fitbit2Influx Job Succeeded" "$EMAIL"

exit 0
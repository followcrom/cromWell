#!/bin/bash

# === CONFIG ===
SCRIPT_DIR="/var/www/cromwell"
VENV_DIR="$SCRIPT_DIR/cw_venv"
LOG_FILE="$SCRIPT_DIR/cromwell_cron.log"
EMAIL="hello@followcrom.com"

# === LOG START ===
echo "$(date)" >> "$LOG_FILE"
echo "=== Running fitbit2influx.py ===" >> "$LOG_FILE"

# === CHECK DIRECTORY ===
cd "$SCRIPT_DIR" || {
    echo "[$(date)] ❌ Failed to cd into $SCRIPT_DIR" >> "$LOG_FILE"
    exit 1
}

# === CHECK VENV ===
if [ ! -d "$VENV_DIR" ]; then
    echo "[$(date)] ❌ Virtual environment not found at $VENV_DIR" >> "$LOG_FILE"
    exit 1
fi

# === ACTIVATE ===
source "$VENV_DIR/bin/activate"
echo "[$(date)] ✅ Virtual environment activated" >> "$LOG_FILE"

# === RUN SCRIPT ===
echo "[$(date)] ▶️ Running fitbit2influx.py..." >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
python "$SCRIPT_DIR/fitbit2influx.py" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

# === ERROR HANDLING ===
if [ $EXIT_CODE -ne 0 ]; then
    TIMESTAMP=$(date)
    echo "[$TIMESTAMP] ❌ Script failed with exit code $EXIT_CODE" >> "$LOG_FILE"

    email_body="$TIMESTAMP - Fitbit2Influx job failed on $(hostname)
The cron job failed with exit code $EXIT_CODE.
Check the log file at $LOG_FILE for details."

    echo "$email_body" | mail -s "❌ Fitbit2Influx Job Failed" "$EMAIL"
    echo "[$(date)] 📧 Notification email sent to $EMAIL" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
else
    echo "✅ Script executed successfully" >> "$LOG_FILE"
fi

# === CLEANUP ===
deactivate
echo "🔚 fitbit2influx.py execution completed" >> "$LOG_FILE"

# === LOG END ===
echo "[$(date)] === End of fitbit2influx.py run ===" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
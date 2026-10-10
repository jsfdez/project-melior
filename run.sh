#!/bin/bash
# run.sh - Melior Sandbox Runner

set -e
set -o pipefail

# 1. Create logs directory if it doesn't exist
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/run_$(date +%Y%m%d_%H%M%S).log"

# 2. Determine the script to run (default to main.py)
if [ $# -eq 0 ]; then
    SCRIPT_PATH="main.py"
else
    SCRIPT_PATH=$1
    shift # Remove the script path from the arguments list
fi

# 3. Ensure dependencies are met
if [ ! -d "venv" ] || [ requirements.txt -nt venv/bin/python ]; then
    echo "🔄 Checking/Updating dependencies..."
    if [ -f "setup.sh" ]; then
        # We run setup.sh and pipe its output to the log too
        ./setup.sh 2>&1 | tee -a "$LOG_FILE"
    else
        echo "❌ Error: setup.sh not found!" | tee -a "$LOG_FILE"
        exit 1
    fi
fi

# 4. Check if script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ Error: Script '$SCRIPT_PATH' not found." | tee -a "$LOG_FILE"
    exit 1
fi

# 5. Run the script and capture all output
echo "🚀 Running: $SCRIPT_PATH" | tee -a "$LOG_FILE"
echo "📝 Logging to: $LOG_FILE" | tee -a "$LOG_FILE"

# Execute the script, redirecting stdout and stderr to tee, which writes to the log file
QT_QPA_PLATFORM=xcb ./venv/bin/python "$SCRIPT_PATH" "$@" 2>&1 | tee -a "$LOG_FILE"

# Capture the exit status of the python script (not the tee command)
EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Execution finished successfully." | tee -a "$LOG_FILE"
else
    echo "❌ Execution failed with exit code $EXIT_CODE. Check $LOG_FILE for details." | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

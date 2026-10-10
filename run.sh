#!/bin/bash
# run.sh - Melior Sandbox Runner

set -e

# 1. Determine the script to run (default to main.py)
if [ $# -eq 0 ]; then
    SCRIPT_PATH="main.py"
else
    SCRIPT_PATH=$1
    shift
fi

# 2. Ensure dependencies are met
# We check if venv exists, OR if requirements.txt is newer than the python executable in venv
if [ ! -d "venv" ] || [ requirements.txt -nt venv/bin/python ]; then
    echo "🔄 Checking/Updating dependencies..."
    if [ -f "setup.sh" ]; then
        ./setup.sh
    else
        echo "❌ Error: setup.sh not found!"
        exit 1
    fi
fi

# 3. Check if script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ Error: Script '$SCRIPT_PATH' not found."
    exit 1
fi

# 4. Run the script
echo "🚀 Running: $SCRIPT_PATH"
./venv/bin/python "$SCRIPT_PATH" "$@"

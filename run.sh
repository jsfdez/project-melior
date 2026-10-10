#!/bin/bash
# run.sh - Melior Sandbox Runner

set -e

# 1. Check if a script was provided
if [ $# -eq 0 ]; then
    echo "❌ Error: No script provided."
    echo "Usage: ./run.sh <path_to_script.py> [args...]"
    exit 1
fi

SCRIPT_PATH=$1
shift # Remove the script path from the arguments list

# 2. Check if venv exists, if not, run setup.sh
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Running setup.sh..."
    if [ -f "setup.sh" ]; then
        ./setup.sh
    else
        echo "❌ Error: setup.sh not found. Please run it manually or ensure it exists."
        exit 1
    fi
fi

# 3. Run the script using the venv python
echo "🚀 Running: $SCRIPT_PATH"
./venv/bin/python "$SCRIPT_PATH" "$@"

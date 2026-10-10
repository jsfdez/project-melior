#!/bin/bash
# setup.sh - Melior Sandbox Initializer

set -e

echo "🚀 Initializing Melior Sandbox..."

# 1. Create Virtual Environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment (venv)..."
    python3 -m venv venv
fi

# 2. Activate Environment
echo "🔌 Activating environment..."
source venv/bin/activate

# 3. Upgrade Pip
echo "🆙 Upgrading pip..."
pip install --upgrade pip

# 4. Install/Update Dependencies
if [ -f "requirements.txt" ]; then
    echo "📥 Installing/Updating dependencies from requirements.txt..."
    pip install -r requirements.txt
else
    echo "❌ Error: requirements.txt not found!"
    exit 1
fi

echo "--------------------------------------------------"
echo "✨ Sandbox setup complete!"
echo "👉 To enter the sandbox, run: source venv/bin/activate"
echo "👉 To run the app, run: ./run.sh"
echo "--------------------------------------------------"

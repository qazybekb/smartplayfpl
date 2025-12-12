#!/bin/bash

# SmartPlayFPL Backend Startup Script

echo "🚀 Starting SmartPlayFPL Backend..."

# Navigate to backend directory
cd "$(dirname "$0")"

# Activate virtual environment
if [ -d "ml_venv" ]; then
    echo "📦 Activating virtual environment..."
    source ml_venv/bin/activate
else
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv ml_venv
    source ml_venv/bin/activate
fi

# Install/update dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Start the server
echo "🌐 Starting backend server on http://localhost:8000"
echo "   Press CTRL+C to stop the server"
echo ""
uvicorn main:app --reload --port 8000




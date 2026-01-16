#!/bin/bash
# Start Franchise Radar Web UI

echo "🚀 Starting Franchise Radar Web UI..."
echo "📊 UI will be available at: http://localhost:8000"
echo ""

# Activate virtual environment and set PYTHONPATH
source venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Start Uvicorn server
uvicorn franchise_radar.api.app:app --host 0.0.0.0 --port 8000 --reload

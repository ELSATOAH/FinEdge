#!/bin/bash
# FinEdge Setup Script
# AI-Powered Stock/Crypto Edge Predictor

set -e

echo "================================================"
echo "  FinEdge - AI Edge Predictor Setup"
echo "================================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python
echo "[1/5] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found. Please install Python 3.9 or newer from https://www.python.org/downloads/"
    exit 1
fi
PYVER=$(python3 --version)
echo "  Found: $PYVER"

# Create virtual environment
echo "[2/5] Setting up virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  Created virtual environment"
else
    echo "  Virtual environment already exists"
fi
source venv/bin/activate

# Install dependencies
echo "[3/5] Installing dependencies..."
pip install --upgrade pip setuptools wheel -q
pip install -r requirements.txt -q

# Download TextBlob data
echo "[4/5] Downloading NLP data..."
python3 -c "import textblob; textblob.download_corpora.download_all()" 2>/dev/null || \
python3 -m textblob.download_corpora 2>/dev/null || \
echo "  Note: TextBlob corpora download may require: python3 -m textblob.download_corpora"

# Create directories
echo "[5/5] Initializing data directories..."
mkdir -p data models

echo ""
echo "================================================"
echo "  Setup Complete!"
echo "================================================"
echo ""
echo "  To start FinEdge:"
echo "    cd $SCRIPT_DIR"
echo "    source venv/bin/activate"
echo "    python3 app.py"
echo ""
echo "  Then open in your browser:"
echo "    http://localhost:5000"
echo ""
echo "  Optional: Set up Telegram alerts:"
echo "    export FINEDGE_TG_TOKEN='your-bot-token'"
echo "    export FINEDGE_TG_CHAT='your-chat-id'"
echo ""
echo "  Optional: Run as a systemd service:"
echo "    sudo cp finedge.service /etc/systemd/system/"
echo "    sudo systemctl enable finedge"
echo "    sudo systemctl start finedge"
echo ""

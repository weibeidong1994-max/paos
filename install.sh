#!/usr/bin/env bash
set -e

echo "🚀 Installing PAOS (Personal AI OS)..."

# Create data directories (user data, not tracked by git)
mkdir -p data/raw data/processed data/output data/fallback_queue

echo "📁 Data directories created under ./data/"

# Install dependencies
if command -v uv &> /dev/null; then
    echo "📦 Using uv to install dependencies..."
    uv pip install -e ".[dev]"
else
    echo "⚠️  uv not found, falling back to pip..."
    pip install -e ".[dev]"
fi

echo "✅ Dependencies installed."

# Check OPENAI_API_KEY
if [ -z "$OPENAI_API_KEY" ]; then
    echo ""
    echo "⚠️  WARNING: OPENAI_API_KEY is not set."
    echo "   Please set it before running the server:"
    echo "   export OPENAI_API_KEY='your-key-here'"
    echo ""
fi

echo "🎉 PAOS installation complete!"
echo "   Start the server with: uvicorn paos.main:app --reload"

#!/bin/bash
# Railway startup script for TELOS Observatory
# Models are pre-downloaded during build phase (see railway.toml)

echo "=== TELOS Observatory Startup ==="
echo "Starting Streamlit..."
streamlit run telos_observatory_v3/main.py --server.port $PORT --server.address 0.0.0.0

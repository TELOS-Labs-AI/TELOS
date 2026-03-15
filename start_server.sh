#!/bin/bash
cd /Users/brunnerjf/Desktop/TELOS_Master
export PYTHONPATH=/Users/brunnerjf/Desktop/TELOS_Master
source .env 2>/dev/null || export MISTRAL_API_KEY=$(cat .env 2>/dev/null | grep MISTRAL_API_KEY | cut -d'=' -f2)
/Users/brunnerjf/Library/Python/3.9/bin/streamlit run telos_observatory_v3/main.py --server.port 8501

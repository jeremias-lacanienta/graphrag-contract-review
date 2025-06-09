#!/bin/bash
# GraphRAG Contract Review Streamlit Script
# This script runs the Streamlit web interface for the GraphRAG contract review system

# Color codes
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Define a separator for readability
SEPARATOR="─────────────────────────────────────────────────────────────────"

# Make sure we're in the right directory
cd "$(dirname "$0")"

# Activate the virtual environment
if [ -d ".venv_graphrag" ]; then
    source .venv_graphrag/bin/activate
    
    echo -e "${GREEN}Starting Streamlit server...${NC}"
    echo -e "${SEPARATOR}"
    echo -e "${BLUE}GraphRAG Contract Review Streamlit Interface${NC}"
    echo -e "${BLUE}Access the web interface at ${GREEN}http://localhost:8501${NC}"
    echo -e "${SEPARATOR}"
    
    # Run the Streamlit app (change directory to src first)
    cd src
    streamlit run app_streamlit.py
    cd ..
    
    # Deactivate the virtual environment when done
    deactivate
else
    echo -e "${RED}Virtual environment .venv_graphrag not found!${NC}"
    echo -e "${RED}Please run setup_and_run_graphrag.sh first to create the environment.${NC}"
    exit 1
fi

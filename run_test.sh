#!/bin/bash
# GraphRAG Contract Review Test Script
# This script runs tests for the dynamic agreement detection in the GraphRAG contract review system

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

# Activate the correct virtual environment
if [ -d ".venv_graphrag" ]; then
    source .venv_graphrag/bin/activate
    
    echo -e "${GREEN}Running test script...${NC}"
    echo -e "${SEPARATOR}"
    echo -e "${BLUE}GraphRAG Contract Review Test${NC}"
    echo -e "${SEPARATOR}"
    
    # Run the test
    python test_service.py
    
    # Print a message when done
    echo -e "${SEPARATOR}"
    echo -e "${GREEN}Test complete. Deactivating virtual environment.${NC}"
    
    # Deactivate the virtual environment
    deactivate
else
    echo -e "${RED}Error: .venv_graphrag environment not found${NC}"
    echo -e "Please run setup.sh first to create the environment"
    exit 1
fi

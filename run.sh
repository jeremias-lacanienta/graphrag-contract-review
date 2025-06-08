#!/bin/bash
# GraphRAG Contract Review Script
# This script runs all available commands in the app_graphrag.py application sequentially
# with proper color formatting and detailed output

# Color codes
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to run a command and display its output with proper formatting
run_command() {
    local title="$1"
    local command="$2"
    local args="$3"
    
    echo -e "${YELLOW}${title}${NC}"
    echo -e "${BLUE}Command:${NC} python src/app_graphrag.py ${command} ${args}"
    echo -e "${BLUE}Running...${NC}\n"
    
    # Run the command and capture its output, preserving the exit code
    # Use eval to ensure quotes are properly interpreted
    result=$(eval "python src/app_graphrag.py ${command} ${args}" 2>&1)
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${result}"  # Default terminal white text
    else
        echo -e "${RED}ERROR: ${result}${NC}"
    fi
}

# Make sure we're in the right directory
cd "$(dirname "$0")"

# Activate the virtual environment
if [ -d ".venv_graphrag" ]; then
    source .venv_graphrag/bin/activate
else
    echo -e "${RED}Virtual environment .venv_graphrag not found!${NC}"
    echo -e "${RED}Please run setup_and_run_graphrag.sh first to create the environment.${NC}"
    exit 1
fi

# Run each command in sequence
# 1. Get a specific contract by ID
run_command "Getting Contract by ID" "get_contract" "3"
# 2. Get contracts for a specific organization
run_command "Getting Contracts for Organization" "get_contracts_by_party" "'Birch First Global Investments Inc.'"
# 3. Get contracts with a specific clause type
run_command "Getting Contracts with IP Ownership Assignment Clause" "get_contracts_with_clause_type" "'IP Ownership Assignment'"
# 4. Get contracts without a specific clause type
run_command "Getting Contracts without Arbitration Clause" "get_contracts_without_clause" "'Arbitration'"
# 5. Get contracts with similar text
run_command "Finding Contracts Similar to 'payment terms'" "get_contracts_similar_text" "'payment terms'"
# 6. Get excerpts from a specific contract
run_command "Getting Excerpts from Contract ID 3" "get_contract_excerpts" "3"
# 7. Answer an aggregation question
run_command "Answering Aggregation Question" "answer_aggregation_question" "'What are the incorporation states for parties in the Master Franchise Agreement?'"
# 8. Demonstrate default behavior with unrecognized command
run_command "Demonstrating Default Search Behavior" "search" "'confidentiality'"

# Deactivate the virtual environment
deactivate
echo -e "Environment deactivated."
#!/bin/zsh
# filepath: /Users/jlacanienta/Projects/graphrag-contract-review/log_viewer.sh

# Script to run the standalone log viewer app

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit

# Define the path to the virtual environment activation script
VENV_PATH=".venv_graphrag/bin/activate"

# Check if the virtual environment exists and activate it
if [ -f "$VENV_PATH" ]; then
    echo "Activating virtual environment: $VENV_PATH"
    source "$VENV_PATH"
else
    echo "Error: Virtual environment not found at $VENV_PATH"
    echo "Please ensure the virtual environment '.venv_graphrag' exists in the current directory."
    exit 1
fi

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "Streamlit is not installed. Installing..."
    python -m pip install streamlit python-dotenv --quiet
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies."
        deactivate
        exit 1
    fi
fi

# Make log_viewer.py executable
chmod +x src/log_viewer.py

# Run the log viewer on a different port than the main app
echo "Starting Log Viewer in a new window..."
streamlit run src/log_viewer.py --server.port=8502 --server.headless=true

# Deactivate virtual environment when done
# This will only happen after the user closes the Streamlit app
echo "Log Viewer closed. Deactivating virtual environment."
deactivate

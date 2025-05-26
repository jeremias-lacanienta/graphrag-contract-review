#!/bin/bash
# Install dependencies if not already installed
pip install -r requirements_graphrag.txt

# Run the command
python app_graphrag.py "$@"

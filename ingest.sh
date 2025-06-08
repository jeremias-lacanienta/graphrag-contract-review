#!/bin/bash
set -e

# Ensure we're in the right directory
cd "$(dirname "$0")"

# Activate the virtual environment
source .venv_graphrag/bin/activate

# Install Azure OpenAI and required packages
echo "Installing required packages..."
pip install --upgrade openai python-dotenv PyPDF2

# Ensure environment variables are loaded
if [ ! -f .env ]; then
  echo "Error: .env file not found"
  echo "Please run setup.sh first and configure your .env file"
  exit 1
fi

# Load environment variables from .env file
echo "Loading environment variables from .env file..."
export $(grep -v '^#' .env | xargs)

# Check if Azure OpenAI variables are set
if [ -z "$AZURE_OPENAI_API_KEY" ] || [ -z "$AZURE_OPENAI_ENDPOINT" ] || [ -z "$AZURE_OPENAI_DEPLOYMENT" ]; then
  echo "Error: Azure OpenAI environment variables not set"
  echo "Please add the following to your .env file:"
  echo "AZURE_OPENAI_API_KEY=your-api-key"
  echo "AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/"
  echo "AZURE_OPENAI_DEPLOYMENT=your-deployment-name"
  exit 1
fi

# Check if input directory exists and has PDF files
if [ ! -d "./data/input" ] || [ -z "$(ls -A ./data/input/*.pdf 2>/dev/null)" ]; then
  echo "Error: No PDF files found in ./data/input/"
  echo "Please add your contract PDFs to the data/input directory"
  exit 1
fi

# Ensure output directories exist
mkdir -p ./data/output
mkdir -p ./data/debug

echo "=== Starting Contract Ingestion Process with Azure OpenAI ==="

# Step 1: Convert PDFs to JSON
echo "Step 1: Converting PDF contracts to JSON using Azure OpenAI..."
python src/convert-pdf-to-json-azure.py
if [ $? -ne 0 ]; then
  echo "Error: PDF to JSON conversion failed"
  exit 1
fi
echo "✓ PDF conversion complete"

# Step 2: Import JSON into Neo4j Knowledge Graph
echo "Step 2: Creating knowledge graph in Neo4j using Azure OpenAI..."
python src/create_graph_from_json_azure.py
if [ $? -ne 0 ]; then
  echo "Error: Knowledge graph creation failed"
  exit 1
fi
echo "✓ Knowledge graph creation complete"

echo "=== Contract Ingestion Complete ==="
echo "All contracts have been processed and loaded into Neo4j"

# Deactivate virtual environment
deactivate

#!/bin/bash
set -e

# Ensure we're in the right directory
cd "$(dirname "$0")"

# Define the app container name
APP_CONTAINER_NAME="streamlit-graphrag"

# Check if the app container is running
if ! docker ps --filter "name=${APP_CONTAINER_NAME}" --filter "status=running" | grep -q "${APP_CONTAINER_NAME}"; then
  echo "Error: The container '${APP_CONTAINER_NAME}' is not running."
  echo "Please start the application with: docker-compose up -d"
  exit 1
fi

# Check if .env file exists (for Azure credentials reminder)
if [ ! -f .env ]; then
  echo "Warning: .env file not found locally. Ensure Azure OpenAI credentials are set in the .env file used by docker-compose."
fi

# Ensure input directory exists and has PDF files locally (for user convenience before copying)
if [ ! -d "./data/input" ] || [ -z "$(ls -A ./data/input/*.pdf 2>/dev/null)" ]; then
  echo "Error: No PDF files found in ./data/input/ on your host machine."
  echo "Please add your contract PDFs to the data/input directory."
  exit 1
fi

# Create output directories locally if they don't exist (for script output if any)
mkdir -p ./data/output
mkdir -p ./data/debug

# Copy data to the container
# The docker-compose.yml should have a volume mapping for ./data to /app/data
# If not, we need to docker cp. For now, assuming volume mount.
echo "Ensuring data is accessible in the container..."
echo "(Assuming ./data on host is mapped to /app/data in container via docker-compose.yml volumes)"

# Path to scripts inside the container (assuming they are at /app/)
CONVERT_SCRIPT="convert-pdf-to-json-azure.py"
CREATE_GRAPH_SCRIPT="create_graph_from_json_azure.py"

echo "=== Starting Contract Ingestion Process with Azure OpenAI (within Docker) ==="

# Step 1: Convert PDFs to JSON inside the container
echo "Step 1: Converting PDF contracts to JSON using Azure OpenAI..."
# The script will look for files in /app/data/input/ inside the container
docker exec "${APP_CONTAINER_NAME}" python "${CONVERT_SCRIPT}"
if [ $? -ne 0 ]; then
  echo "Error: PDF to JSON conversion failed inside the container."
  exit 1
fi
echo "✓ PDF conversion complete (check /app/data/output inside container or mapped ./data/output on host)"

# Step 2: Import JSON into Neo4j Knowledge Graph inside the container
echo "Step 2: Creating knowledge graph in Neo4j using Azure OpenAI..."
# The script will look for files in /app/data/output/ and connect to Neo4j (neo4j:7687)
docker exec "${APP_CONTAINER_NAME}" python "${CREATE_GRAPH_SCRIPT}"
if [ $? -ne 0 ]; then
  echo "Error: Knowledge graph creation failed inside the container."
  exit 1
fi
echo "✓ Knowledge graph creation complete (Neo4j should be updated)"

echo "=== Contract Ingestion Complete (within Docker) ==="
echo "All contracts have been processed and loaded into Neo4j." 
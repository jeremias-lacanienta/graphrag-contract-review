#!/bin/bash

# GraphRAG Contract Review - Data Setup Script
# This script helps load contract data into the Neo4j database

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  GraphRAG Contract Review - Data Setup${NC}"
echo -e "${BLUE}================================================${NC}"

# Check if Docker and Docker Compose are running
if ! docker ps &> /dev/null; then
    echo -e "${RED}Docker is not running or you don't have permission to access it${NC}"
    echo -e "${YELLOW}Try: sudo systemctl start docker${NC}"
    exit 1
fi

# Check if containers are running
if ! docker-compose ps | grep -q "Up"; then
    echo -e "${RED}Application containers are not running${NC}"
    echo -e "${YELLOW}Start them with: docker-compose up -d${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker containers are running${NC}"

# Check if data directory exists
if [ ! -d "data" ]; then
    echo -e "${YELLOW}Creating data directory...${NC}"
    mkdir -p data
    echo -e "${BLUE}📁 Place your contract files (PDF/JSON) in the 'data' directory${NC}"
fi

# List files in data directory
if [ "$(ls -A data)" ]; then
    echo -e "${GREEN}Found files in data directory:${NC}"
    ls -la data/
else
    echo -e "${YELLOW}No files found in data directory${NC}"
    echo -e "${BLUE}Please add your contract files to the 'data' directory and run this script again${NC}"
    exit 0
fi

# Check if Neo4j is responding
echo -e "${YELLOW}Checking Neo4j connectivity...${NC}"
if ! docker exec neo4j-graphrag cypher-shell -u neo4j -p password123 "MATCH (n) RETURN count(n) as node_count" &> /dev/null; then
    echo -e "${RED}Cannot connect to Neo4j. Please wait for the database to fully start (may take up to 60 seconds)${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Neo4j is responding${NC}"

# Function to process PDF files
process_pdfs() {
    echo -e "${YELLOW}Processing PDF files...${NC}"
    for pdf_file in data/*.pdf; do
        if [ -f "$pdf_file" ]; then
            echo -e "${BLUE}Converting $pdf_file to JSON...${NC}"
            docker exec -it streamlit-graphrag python convert-pdf-to-json.py "$pdf_file"
        fi
    done
}

# Function to process JSON files and create graph
process_json_files() {
    echo -e "${YELLOW}Processing JSON files and creating knowledge graph...${NC}"
    for json_file in data/*.json; do
        if [ -f "$json_file" ]; then
            echo -e "${BLUE}Processing $json_file...${NC}"
            docker exec -it streamlit-graphrag python create_graph_from_json.py "$json_file"
        fi
    done
}

# Main processing
echo -e "${BLUE}Choose an option:${NC}"
echo -e "1. Process PDF files (convert to JSON)"
echo -e "2. Process JSON files (create knowledge graph)"
echo -e "3. Process all files (PDF → JSON → Graph)"
echo -e "4. Clear database and restart"
read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        process_pdfs
        ;;
    2)
        process_json_files
        ;;
    3)
        process_pdfs
        process_json_files
        ;;
    4)
        echo -e "${YELLOW}Clearing Neo4j database...${NC}"
        docker exec neo4j-graphrag cypher-shell -u neo4j -p password123 "MATCH (n) DETACH DELETE n"
        echo -e "${GREEN}Database cleared. You can now reprocess your data.${NC}"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Check final state
echo -e "${YELLOW}Checking database state...${NC}"
node_count=$(docker exec neo4j-graphrag cypher-shell -u neo4j -p password123 "MATCH (n) RETURN count(n) as count" | grep -o '[0-9]\+' | tail -1)
echo -e "${GREEN}Database contains $node_count nodes${NC}"

if [ "$node_count" -gt 0 ]; then
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}  Data Setup Complete!${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo -e "${BLUE}Your contract data has been loaded into the knowledge graph.${NC}"
    echo -e "${BLUE}You can now use the Streamlit interface at:${NC}"
    echo -e "${GREEN}http://$(curl -s ifconfig.me)${NC}"
else
    echo -e "${YELLOW}No data was loaded. Please check your files and try again.${NC}"
fi 
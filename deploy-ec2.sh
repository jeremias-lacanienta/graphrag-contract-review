#!/bin/bash

# GraphRAG Contract Review - EC2 Deployment Script
# This script sets up the application on an EC2 instance

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  GraphRAG Contract Review - EC2 Setup${NC}"
echo -e "${BLUE}================================================${NC}"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}This script should not be run as root${NC}"
   exit 1
fi

# Update system
echo -e "${YELLOW}Updating system packages...${NC}"
sudo apt-get update -y
sudo apt-get upgrade -y

# Install Docker if not already installed
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Installing Docker...${NC}"
    sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io
    
    # Add current user to docker group
    sudo usermod -aG docker $USER
    echo -e "${GREEN}Docker installed successfully!${NC}"
    echo -e "${YELLOW}Note: You may need to log out and back in for docker group changes to take effect${NC}"
else
    echo -e "${GREEN}Docker is already installed${NC}"
fi

# Install Docker Compose if not already installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}Installing Docker Compose...${NC}"
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo -e "${GREEN}Docker Compose installed successfully!${NC}"
else
    echo -e "${GREEN}Docker Compose is already installed${NC}"
fi

# Start Docker service
echo -e "${YELLOW}Starting Docker service...${NC}"
sudo systemctl start docker
sudo systemctl enable docker

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    echo "OPENAI_API_KEY=your_openai_api_key_here" > .env
    echo -e "${RED}⚠️  IMPORTANT: Please edit .env file and add your OpenAI API key${NC}"
    echo -e "${BLUE}   nano .env${NC}"
else
    echo -e "${GREEN}.env file already exists${NC}"
fi

# Configure UFW firewall (if installed)
if command -v ufw &> /dev/null; then
    echo -e "${YELLOW}Configuring firewall...${NC}"
    sudo ufw allow ssh
    sudo ufw allow 80/tcp
    sudo ufw allow 7474/tcp
    sudo ufw allow 7687/tcp
    echo -e "${GREEN}Firewall configured to allow HTTP (80), Neo4j Browser (7474), and Neo4j Bolt (7687)${NC}"
fi

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo -e "${BLUE}Next steps:${NC}"
echo -e "${BLUE}1. Edit the .env file and add your OpenAI API key:${NC}"
echo -e "   ${YELLOW}nano .env${NC}"
echo -e "${BLUE}2. Build and start the application:${NC}"
echo -e "   ${YELLOW}docker-compose up -d${NC}"
echo -e "${BLUE}3. Wait for services to start (about 30-60 seconds)${NC}"
echo -e "${BLUE}4. Load your contract data (see data-setup.sh)${NC}"
echo -e "${BLUE}5. Access the application at:${NC}"
echo -e "   ${GREEN}http://$(curl -s ifconfig.me)${NC} (Streamlit app)"
echo -e "   ${GREEN}http://$(curl -s ifconfig.me):7474${NC} (Neo4j Browser)"

# Check if user is in docker group
if ! groups $USER | grep -q '\bdocker\b'; then
    echo -e "${RED}⚠️  You need to log out and back in for docker group changes to take effect${NC}"
fi 
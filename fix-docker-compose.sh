#!/bin/bash

# Fix Docker Compose compatibility issue
# This script removes the old docker-compose and installs the correct version

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  Fixing Docker Compose Compatibility Issue${NC}"
echo -e "${BLUE}================================================${NC}"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}This script should not be run as root${NC}"
   exit 1
fi

# Remove old docker-compose installed via apt
echo -e "${YELLOW}Removing old docker-compose...${NC}"
sudo apt-get remove -y docker-compose

# Remove any pip-installed docker-compose
if command -v pip3 &> /dev/null; then
    echo -e "${YELLOW}Removing pip-installed docker-compose...${NC}"
    pip3 uninstall -y docker-compose 2>/dev/null || true
fi

# Remove old binary if it exists
if [ -f "/usr/bin/docker-compose" ]; then
    echo -e "${YELLOW}Removing old docker-compose binary...${NC}"
    sudo rm -f /usr/bin/docker-compose
fi

if [ -f "/usr/local/bin/docker-compose" ]; then
    echo -e "${YELLOW}Removing old docker-compose from /usr/local/bin...${NC}"
    sudo rm -f /usr/local/bin/docker-compose
fi

# Install Docker Compose V2 (standalone)
echo -e "${YELLOW}Installing Docker Compose V2...${NC}"
DOCKER_COMPOSE_VERSION="v2.23.3"
sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create symlink for compatibility
sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

# Verify installation
echo -e "${YELLOW}Verifying Docker Compose installation...${NC}"
if docker-compose --version; then
    echo -e "${GREEN}✅ Docker Compose installed successfully!${NC}"
else
    echo -e "${RED}❌ Docker Compose installation failed${NC}"
    exit 1
fi

# Check Docker daemon accessibility
echo -e "${YELLOW}Checking Docker daemon access...${NC}"
if ! docker ps &> /dev/null; then
    echo -e "${RED}Cannot access Docker daemon. Checking user permissions...${NC}"
    
    # Add user to docker group if not already there
    if ! groups $USER | grep -q '\bdocker\b'; then
        echo -e "${YELLOW}Adding user to docker group...${NC}"
        sudo usermod -aG docker $USER
        echo -e "${YELLOW}User added to docker group. You need to log out and back in for this to take effect.${NC}"
        echo -e "${BLUE}Alternative: Run 'newgrp docker' to activate the group in current session${NC}"
    fi
    
    # Start Docker service if not running
    if ! sudo systemctl is-active --quiet docker; then
        echo -e "${YELLOW}Starting Docker service...${NC}"
        sudo systemctl start docker
        sudo systemctl enable docker
    fi
    
    echo -e "${YELLOW}Trying Docker access with newgrp...${NC}"
    newgrp docker << EOF
if docker ps &> /dev/null; then
    echo -e "${GREEN}✅ Docker is now accessible!${NC}"
else
    echo -e "${RED}❌ Still cannot access Docker. You may need to:${NC}"
    echo -e "${RED}1. Log out and back in${NC}"
    echo -e "${RED}2. Or restart the EC2 instance${NC}"
fi
EOF
else
    echo -e "${GREEN}✅ Docker daemon is accessible${NC}"
fi

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  Fix Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo -e "${BLUE}Now try running: ${YELLOW}docker-compose up -d${NC}"
echo -e "${BLUE}If you still get permission errors, run: ${YELLOW}newgrp docker${NC}"
echo -e "${BLUE}Or log out and back in to your EC2 instance.${NC}" 
#!/bin/bash
# Quick Deploy Script for GraphRAG Contract Review
# Provides options for different deployment methods

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              GraphRAG Contract Review Deployment            ║${NC}"
echo -e "${BLUE}║                     Quick Deploy Script                     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${CYAN}Choose your deployment method:${NC}"
echo ""
echo -e "${YELLOW}1.${NC} Native EC2 Deployment (Full)"
echo -e "   ${GREEN}✓${NC} Complete system upgrade and installation"
echo -e "   ${GREEN}✓${NC} Best for new instances"
echo -e "   ${GREEN}✓${NC} Includes retry logic for package issues"
echo ""
echo -e "${YELLOW}2.${NC} Minimal EC2 Deployment (Recommended for package issues)"
echo -e "   ${GREEN}✓${NC} Skips system upgrades"
echo -e "   ${GREEN}✓${NC} Installs only essential packages"
echo -e "   ${GREEN}✓${NC} Faster deployment, fewer conflicts"
echo ""
echo -e "${YELLOW}3.${NC} Docker Deployment"
echo -e "   ${GREEN}✓${NC} Containerized deployment"
echo -e "   ${GREEN}✓${NC} Easy to manage and update"
echo -e "   ${GREEN}✓${NC} Isolated environment"
echo ""
echo -e "${YELLOW}4.${NC} Local Development Setup"
echo -e "   ${GREEN}✓${NC} Run locally for development"
echo -e "   ${GREEN}✓${NC} Uses existing setup scripts"
echo ""
echo -e "${YELLOW}5.${NC} View Deployment Guide"
echo -e "   ${GREEN}✓${NC} Read detailed instructions"
echo ""

read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo -e "${GREEN}🚀 Starting Full EC2 Deployment...${NC}"
        echo ""
        echo -e "${YELLOW}Prerequisites:${NC}"
        echo "- Ubuntu EC2 instance (20.04 or 22.04)"
        echo "- At least 4GB RAM and 2 vCPUs"
        echo "- Security group allowing ports 22, 80, 7687"
        echo "- OpenAI API key"
        echo ""
        echo -e "${YELLOW}Note: This includes full system upgrade and may take longer${NC}"
        echo ""
        read -p "Do you want to continue? (y/N): " confirm
        if [[ $confirm =~ ^[Yy]$ ]]; then
            echo -e "${BLUE}Running full deployment script...${NC}"
            ./deploy_ec2.sh
        else
            echo -e "${YELLOW}Deployment cancelled.${NC}"
        fi
        ;;
    2)
        echo -e "${GREEN}🚀 Starting Minimal EC2 Deployment...${NC}"
        echo ""
        echo -e "${YELLOW}Prerequisites:${NC}"
        echo "- Ubuntu EC2 instance (20.04 or 22.04)"
        echo "- At least 4GB RAM and 2 vCPUs"
        echo "- Security group allowing ports 22, 80, 7687"
        echo "- OpenAI API key"
        echo ""
        echo -e "${GREEN}✅ This option skips system upgrades and is recommended if you encountered package download errors${NC}"
        echo ""
        read -p "Do you want to continue? (y/N): " confirm
        if [[ $confirm =~ ^[Yy]$ ]]; then
            echo -e "${BLUE}Running minimal deployment script...${NC}"
            ./deploy_ec2_minimal.sh
        else
            echo -e "${YELLOW}Deployment cancelled.${NC}"
        fi
        ;;
    3)
        echo -e "${GREEN}🐳 Starting Docker Deployment...${NC}"
        echo ""
        echo -e "${YELLOW}Prerequisites:${NC}"
        echo "- Docker and Docker Compose installed"
        echo "- OpenAI API key"
        echo ""
        
        # Check if Docker is installed
        if ! command -v docker &> /dev/null; then
            echo -e "${RED}❌ Docker not found. Installing Docker...${NC}"
            sudo apt update
            sudo apt install -y docker.io docker-compose
            sudo systemctl enable docker
            sudo systemctl start docker
            sudo usermod -aG docker $USER
            echo -e "${YELLOW}⚠️ Please log out and back in for Docker group changes to take effect${NC}"
            echo -e "${YELLOW}Then run this script again${NC}"
            exit 1
        fi
        
        # Check if .env exists
        if [ ! -f .env ]; then
            echo -e "${YELLOW}📝 Creating .env file...${NC}"
            read -p "Enter your OpenAI API key: " openai_key
            cat > .env << EOF
OPENAI_API_KEY=${openai_key}
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=neo4j123
EOF
            echo -e "${GREEN}✅ .env file created${NC}"
        fi
        
        echo -e "${BLUE}Building and starting containers...${NC}"
        docker-compose up -d
        
        echo -e "${GREEN}✅ Docker deployment completed!${NC}"
        echo -e "${BLUE}Your application should be accessible at http://localhost${NC}"
        echo ""
        echo -e "${YELLOW}Useful commands:${NC}"
        echo "- Check status: docker-compose ps"
        echo "- View logs: docker-compose logs -f"
        echo "- Stop: docker-compose down"
        ;;
    4)
        echo -e "${GREEN}💻 Setting up local development environment...${NC}"
        echo ""
        if [ -f "./run_streamlit.sh" ]; then
            echo -e "${BLUE}Running existing Streamlit setup...${NC}"
            ./run_streamlit.sh
        else
            echo -e "${YELLOW}Setting up environment...${NC}"
            ./setup.sh
            echo -e "${GREEN}✅ Setup completed!${NC}"
            echo -e "${BLUE}You can now run: ./run_streamlit.sh${NC}"
        fi
        ;;
    5)
        echo -e "${GREEN}📖 Opening deployment guide...${NC}"
        if command -v less &> /dev/null; then
            less DEPLOYMENT.md
        elif command -v more &> /dev/null; then
            more DEPLOYMENT.md
        else
            cat DEPLOYMENT.md
        fi
        ;;
    *)
        echo -e "${RED}❌ Invalid choice. Please run the script again and choose 1-5.${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}🎉 Thank you for using GraphRAG Contract Review!${NC}" 
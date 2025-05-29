#!/bin/bash
# EC2 Deployment Script for GraphRAG Contract Review
# This script sets up the application on an EC2 instance and configures it to run on port 80

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting EC2 deployment for GraphRAG Contract Review${NC}"
echo "=================================================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}❌ This script should not be run as root${NC}"
   echo "Please run as a regular user with sudo privileges"
   exit 1
fi

# Update system packages
echo -e "${YELLOW}📦 Updating system packages...${NC}"
sudo apt update && sudo apt upgrade -y

# Install required system packages
echo -e "${YELLOW}📦 Installing system dependencies...${NC}"
sudo apt install -y \
    python3.10 \
    python3.10-venv \
    python3.10-dev \
    python3-pip \
    nginx \
    git \
    curl \
    wget \
    unzip \
    build-essential \
    netcat-openbsd

# Install Neo4j
echo -e "${YELLOW}📦 Installing Neo4j...${NC}"
wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo apt-key add -
echo 'deb https://debian.neo4j.com stable latest' | sudo tee -a /etc/apt/sources.list.d/neo4j.list
sudo apt update
sudo apt install -y neo4j

# Configure Neo4j
echo -e "${YELLOW}⚙️ Configuring Neo4j...${NC}"
sudo systemctl enable neo4j
sudo systemctl start neo4j

# Wait for Neo4j to start
echo -e "${YELLOW}⏳ Waiting for Neo4j to start...${NC}"
sleep 10

# Set Neo4j initial password (you should change this)
echo -e "${YELLOW}🔐 Setting Neo4j password...${NC}"
sudo neo4j-admin set-initial-password neo4j123

# Restart Neo4j with new password
sudo systemctl restart neo4j
sleep 10

# Get the current directory (where the app is located)
APP_DIR=$(pwd)
APP_USER=$(whoami)

echo -e "${YELLOW}📁 Application directory: ${APP_DIR}${NC}"
echo -e "${YELLOW}👤 Application user: ${APP_USER}${NC}"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${YELLOW}📝 Creating .env file...${NC}"
    cat > .env << EOF
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=neo4j123

# Streamlit Configuration
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
EOF
    echo -e "${RED}⚠️ Please edit .env file and add your OpenAI API key${NC}"
    echo -e "${RED}⚠️ You may also want to change the Neo4j password${NC}"
fi

# Set up Python virtual environment
echo -e "${YELLOW}🐍 Setting up Python virtual environment...${NC}"
python3.10 -m venv .venv_graphrag
source .venv_graphrag/bin/activate

# Upgrade pip and install requirements
pip install --upgrade pip
pip install -r requirements_graphrag.txt

# Install additional packages for production
pip install python-dotenv gunicorn

deactivate

# Create systemd service file
echo -e "${YELLOW}⚙️ Creating systemd service...${NC}"
sudo tee /etc/systemd/system/graphrag-streamlit.service > /dev/null << EOF
[Unit]
Description=GraphRAG Contract Review Streamlit App
After=network.target neo4j.service
Requires=neo4j.service

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment=PATH=${APP_DIR}/.venv_graphrag/bin
ExecStart=${APP_DIR}/.venv_graphrag/bin/streamlit run app_streamlit.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx
echo -e "${YELLOW}🌐 Configuring Nginx...${NC}"
sudo tee /etc/nginx/sites-available/graphrag > /dev/null << EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 86400;
    }

    # Handle Streamlit's WebSocket connections
    location /_stcore/stream {
        proxy_pass http://127.0.0.1:8501/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable the Nginx site
sudo ln -sf /etc/nginx/sites-available/graphrag /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Configure firewall
echo -e "${YELLOW}🔥 Configuring firewall...${NC}"
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 7687/tcp  # Neo4j
sudo ufw --force enable

# Reload systemd and start services
echo -e "${YELLOW}🔄 Starting services...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable graphrag-streamlit
sudo systemctl enable nginx
sudo systemctl restart nginx

# Start the application
sudo systemctl start graphrag-streamlit

# Check service status
echo -e "${GREEN}✅ Deployment completed!${NC}"
echo "=================================================================="
echo -e "${BLUE}📊 Service Status:${NC}"
echo -e "${YELLOW}Neo4j:${NC} $(sudo systemctl is-active neo4j)"
echo -e "${YELLOW}Nginx:${NC} $(sudo systemctl is-active nginx)"
echo -e "${YELLOW}GraphRAG App:${NC} $(sudo systemctl is-active graphrag-streamlit)"

echo ""
echo -e "${GREEN}🌐 Your application should now be accessible at:${NC}"
echo -e "${BLUE}http://$(curl -s ifconfig.me)${NC}"
echo -e "${BLUE}http://localhost${NC} (if accessing locally)"

echo ""
echo -e "${YELLOW}📝 Next steps:${NC}"
echo "1. Edit .env file and add your OpenAI API key"
echo "2. Restart the service: sudo systemctl restart graphrag-streamlit"
echo "3. Check logs: sudo journalctl -u graphrag-streamlit -f"
echo "4. Upload your contract data and run the ingestion process"

echo ""
echo -e "${YELLOW}🔧 Useful commands:${NC}"
echo "- Check app logs: sudo journalctl -u graphrag-streamlit -f"
echo "- Restart app: sudo systemctl restart graphrag-streamlit"
echo "- Check Neo4j status: sudo systemctl status neo4j"
echo "- Check Nginx status: sudo systemctl status nginx" 
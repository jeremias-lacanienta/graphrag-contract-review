#!/bin/bash
# Minimal EC2 Deployment Script for GraphRAG Contract Review
# This script skips system upgrades and installs only what's needed

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Minimal EC2 deployment for GraphRAG Contract Review${NC}"
echo "=================================================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}❌ This script should not be run as root${NC}"
   echo "Please run as a regular user with sudo privileges"
   exit 1
fi

# Update package lists only
echo -e "${YELLOW}📦 Updating package lists...${NC}"
sudo apt update

# Install only essential packages without upgrading
echo -e "${YELLOW}📦 Installing essential dependencies...${NC}"
sudo apt install -y --no-upgrade \
    python3.10 \
    python3.10-venv \
    python3.10-dev \
    python3-pip \
    nginx \
    curl \
    wget \
    build-essential \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg

# Install Neo4j using the official installation method
echo -e "${YELLOW}📦 Installing Neo4j...${NC}"

# Add Neo4j GPG key and repository
curl -fsSL https://debian.neo4j.com/neotechnology.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/neo4j.gpg
echo "deb [signed-by=/usr/share/keyrings/neo4j.gpg] https://debian.neo4j.com stable latest" | sudo tee /etc/apt/sources.list.d/neo4j.list

# Update and install Neo4j
sudo apt update
sudo apt install -y neo4j

# Configure and start Neo4j
echo -e "${YELLOW}⚙️ Configuring Neo4j...${NC}"
sudo systemctl enable neo4j
sudo systemctl start neo4j

# Wait for Neo4j to start
echo -e "${YELLOW}⏳ Waiting for Neo4j to start...${NC}"
sleep 15

# Set Neo4j password
echo -e "${YELLOW}🔐 Setting Neo4j password...${NC}"
sudo neo4j-admin dbms set-initial-password neo4j123 || echo "Password may already be set"

# Restart Neo4j
sudo systemctl restart neo4j
sleep 10

# Get application details
APP_DIR=$(pwd)
APP_USER=$(whoami)

echo -e "${YELLOW}📁 Application directory: ${APP_DIR}${NC}"
echo -e "${YELLOW}👤 Application user: ${APP_USER}${NC}"

# Create .env file
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
fi

# Set up Python virtual environment
echo -e "${YELLOW}🐍 Setting up Python virtual environment...${NC}"
python3.10 -m venv .venv_graphrag
source .venv_graphrag/bin/activate

# Install Python packages
echo -e "${YELLOW}📦 Installing Python packages...${NC}"
pip install --upgrade pip
pip install -r requirements_graphrag.txt
pip install python-dotenv

deactivate

# Create systemd service
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

# Enable Nginx site
sudo ln -sf /etc/nginx/sites-available/graphrag /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Configure basic firewall
echo -e "${YELLOW}🔥 Configuring firewall...${NC}"
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw --force enable

# Start services
echo -e "${YELLOW}🔄 Starting services...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable graphrag-streamlit
sudo systemctl enable nginx
sudo systemctl restart nginx
sudo systemctl start graphrag-streamlit

# Check status
echo -e "${GREEN}✅ Minimal deployment completed!${NC}"
echo "=================================================================="
echo -e "${BLUE}📊 Service Status:${NC}"
echo -e "${YELLOW}Neo4j:${NC} $(sudo systemctl is-active neo4j)"
echo -e "${YELLOW}Nginx:${NC} $(sudo systemctl is-active nginx)"
echo -e "${YELLOW}GraphRAG App:${NC} $(sudo systemctl is-active graphrag-streamlit)"

echo ""
echo -e "${GREEN}🌐 Your application should be accessible at:${NC}"
echo -e "${BLUE}http://your-ec2-public-ip${NC}"

echo ""
echo -e "${YELLOW}📝 Next steps:${NC}"
echo "1. Edit .env file: nano .env"
echo "2. Add your OpenAI API key"
echo "3. Restart the service: sudo systemctl restart graphrag-streamlit"
echo "4. Check logs: sudo journalctl -u graphrag-streamlit -f" 
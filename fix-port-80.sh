#!/bin/bash

# Fix port 80 conflict for Streamlit
# This script identifies what's using port 80 and helps resolve the conflict

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  Fixing Port 80 Conflict${NC}"
echo -e "${BLUE}================================================${NC}"

# Check what's using port 80
echo -e "${YELLOW}Checking what's using port 80...${NC}"
PORT_CHECK=$(sudo lsof -i :80 2>/dev/null)

if [ -n "$PORT_CHECK" ]; then
    echo -e "${RED}Port 80 is in use:${NC}"
    echo "$PORT_CHECK"
    echo ""
    
    # Check for common web servers
    if echo "$PORT_CHECK" | grep -q "apache\|httpd"; then
        echo -e "${YELLOW}Apache web server is running on port 80.${NC}"
        WEB_SERVER="apache2"
    elif echo "$PORT_CHECK" | grep -q "nginx"; then
        echo -e "${YELLOW}Nginx web server is running on port 80.${NC}"
        WEB_SERVER="nginx"
    else
        echo -e "${YELLOW}Some other service is using port 80.${NC}"
        WEB_SERVER="unknown"
    fi
    
    echo -e "${BLUE}Options:${NC}"
    echo -e "1. Stop the web server (recommended for dedicated GraphRAG server)"
    echo -e "2. Use port 8080 for Streamlit instead of port 80"
    echo -e "3. Set up reverse proxy (advanced)"
    echo ""
    read -p "Choose option (1, 2, or 3): " choice
    
    case $choice in
        1)
            if [ "$WEB_SERVER" != "unknown" ]; then
                echo -e "${YELLOW}Stopping $WEB_SERVER...${NC}"
                sudo systemctl stop $WEB_SERVER
                sudo systemctl disable $WEB_SERVER
                echo -e "${GREEN}✅ $WEB_SERVER stopped and disabled${NC}"
            else
                echo -e "${YELLOW}Attempting to stop unknown service on port 80...${NC}"
                PID=$(sudo lsof -t -i :80 2>/dev/null | head -1)
                if [ -n "$PID" ]; then
                    sudo kill -9 $PID
                    sleep 2
                    if ! sudo lsof -i :80 &>/dev/null; then
                        echo -e "${GREEN}✅ Port 80 is now free${NC}"
                    else
                        echo -e "${RED}❌ Could not free port 80${NC}"
                    fi
                fi
            fi
            ;;
        2)
            echo -e "${YELLOW}Modifying docker-compose.yml to use port 8080...${NC}"
            # Create backup
            cp docker-compose.yml docker-compose.yml.backup
            
            # Replace port mapping
            sed -i 's/"80:80"/"8080:80"/g' docker-compose.yml
            
            echo -e "${GREEN}✅ Modified docker-compose.yml to use port 8080${NC}"
            echo -e "${BLUE}Your Streamlit app will be accessible at:${NC}"
            echo -e "${GREEN}http://$(curl -s ifconfig.me):8080${NC}"
            
            # Update security group reminder
            echo -e "${YELLOW}⚠️  Remember to allow port 8080 in your EC2 Security Group!${NC}"
            ;;
        3)
            echo -e "${YELLOW}Setting up reverse proxy...${NC}"
            
            if [ "$WEB_SERVER" = "nginx" ]; then
                echo -e "${BLUE}Creating Nginx reverse proxy configuration...${NC}"
                
                # Create Nginx config for reverse proxy
                sudo tee /etc/nginx/sites-available/graphrag > /dev/null <<EOF
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support for Streamlit
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
EOF
                
                # Enable the site
                sudo rm -f /etc/nginx/sites-enabled/default
                sudo ln -sf /etc/nginx/sites-available/graphrag /etc/nginx/sites-enabled/
                
                # Modify docker-compose to use port 8080 internally
                cp docker-compose.yml docker-compose.yml.backup
                sed -i 's/"80:80"/"8080:80"/g' docker-compose.yml
                
                # Test and reload Nginx
                sudo nginx -t && sudo systemctl reload nginx
                
                echo -e "${GREEN}✅ Nginx reverse proxy configured${NC}"
                echo -e "${BLUE}Streamlit will run on port 8080, Nginx will proxy port 80${NC}"
                
            else
                echo -e "${RED}Reverse proxy setup requires Nginx. Please choose option 1 or 2.${NC}"
                exit 1
            fi
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac
    
else
    echo -e "${GREEN}✅ Port 80 is free${NC}"
fi

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  Port 80 Fix Complete!${NC}"
echo -e "${GREEN}================================================${NC}"

# Clean up any existing containers
echo -e "${YELLOW}Cleaning up existing containers...${NC}"
docker-compose down

echo -e "${BLUE}Now try running: ${YELLOW}docker-compose up -d${NC}"

# Final verification
echo -e "${YELLOW}Current port status:${NC}"
echo -e "Port 80: $(sudo lsof -i :80 >/dev/null 2>&1 && echo "In use" || echo "Free")"
echo -e "Port 8080: $(sudo lsof -i :8080 >/dev/null 2>&1 && echo "In use" || echo "Free")" 
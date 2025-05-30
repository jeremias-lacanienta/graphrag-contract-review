#!/bin/bash

# Fix port conflict issue for Neo4j
# This script identifies what's using port 7687 and helps resolve the conflict

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  Fixing Port Conflict (7687)${NC}"
echo -e "${BLUE}================================================${NC}"

# Check what's using port 7687
echo -e "${YELLOW}Checking what's using port 7687...${NC}"
PORT_CHECK=$(sudo lsof -i :7687 2>/dev/null)

if [ -n "$PORT_CHECK" ]; then
    echo -e "${RED}Port 7687 is in use:${NC}"
    echo "$PORT_CHECK"
    echo ""
    
    # Check if it's Neo4j
    if echo "$PORT_CHECK" | grep -q "neo4j\|java"; then
        echo -e "${YELLOW}It appears Neo4j is already running on this system.${NC}"
        
        # Check if it's a systemd service
        if sudo systemctl is-active --quiet neo4j 2>/dev/null; then
            echo -e "${YELLOW}Neo4j is running as a systemd service.${NC}"
            echo -e "${BLUE}Options:${NC}"
            echo -e "1. Stop the existing Neo4j service (recommended)"
            echo -e "2. Change ports in docker-compose.yml"
            echo ""
            read -p "Choose option (1 or 2): " choice
            
            if [ "$choice" = "1" ]; then
                echo -e "${YELLOW}Stopping existing Neo4j service...${NC}"
                sudo systemctl stop neo4j
                sudo systemctl disable neo4j
                echo -e "${GREEN}✅ Neo4j service stopped and disabled${NC}"
                
                # Also check for port 7474
                if sudo lsof -i :7474 &>/dev/null; then
                    echo -e "${YELLOW}Port 7474 was also in use, should be free now.${NC}"
                fi
                
            elif [ "$choice" = "2" ]; then
                echo -e "${YELLOW}Creating modified docker-compose.yml with different ports...${NC}"
                # Create backup
                cp docker-compose.yml docker-compose.yml.backup
                
                # Replace ports
                sed -i 's/"7474:7474"/"7475:7474"/g' docker-compose.yml
                sed -i 's/"7687:7687"/"7688:7687"/g' docker-compose.yml
                
                echo -e "${GREEN}✅ Modified docker-compose.yml to use ports 7475 and 7688${NC}"
                echo -e "${BLUE}Your Neo4j will be accessible at:${NC}"
                echo -e "${BLUE}  Browser: http://your-ec2-ip:7475${NC}"
                echo -e "${BLUE}  Bolt: bolt://your-ec2-ip:7688${NC}"
                
                # Also need to update the app's environment
                echo -e "${YELLOW}Updating app environment to use new ports...${NC}"
                sed -i 's/NEO4J_URI=bolt:\/\/neo4j:7687/NEO4J_URI=bolt:\/\/neo4j:7687/g' docker-compose.yml
                echo -e "${GREEN}✅ App configuration updated${NC}"
            fi
        else
            # Not a systemd service, try to kill the process
            echo -e "${YELLOW}Neo4j is not running as a service. Attempting to stop the process...${NC}"
            PID=$(sudo lsof -t -i :7687 2>/dev/null)
            if [ -n "$PID" ]; then
                echo -e "${YELLOW}Killing process $PID using port 7687...${NC}"
                sudo kill -9 $PID
                sleep 2
                
                # Check if it's stopped
                if ! sudo lsof -i :7687 &>/dev/null; then
                    echo -e "${GREEN}✅ Port 7687 is now free${NC}"
                else
                    echo -e "${RED}❌ Could not free port 7687${NC}"
                fi
            fi
        fi
    else
        echo -e "${YELLOW}Some other service is using port 7687.${NC}"
        PID=$(sudo lsof -t -i :7687 2>/dev/null | head -1)
        if [ -n "$PID" ]; then
            echo -e "${YELLOW}Attempting to stop process $PID...${NC}"
            sudo kill -9 $PID
            sleep 2
            
            if ! sudo lsof -i :7687 &>/dev/null; then
                echo -e "${GREEN}✅ Port 7687 is now free${NC}"
            else
                echo -e "${RED}❌ Could not free port 7687${NC}"
            fi
        fi
    fi
else
    echo -e "${GREEN}✅ Port 7687 is free${NC}"
fi

# Check port 7474 as well
echo -e "${YELLOW}Checking port 7474...${NC}"
if sudo lsof -i :7474 &>/dev/null; then
    echo -e "${YELLOW}Port 7474 is also in use. Stopping processes...${NC}"
    PID=$(sudo lsof -t -i :7474 2>/dev/null | head -1)
    if [ -n "$PID" ]; then
        sudo kill -9 $PID
        sleep 2
    fi
fi

# Check port 80
echo -e "${YELLOW}Checking port 80...${NC}"
if sudo lsof -i :80 &>/dev/null; then
    echo -e "${YELLOW}Port 80 is in use:${NC}"
    sudo lsof -i :80
    echo -e "${BLUE}This might be Apache, Nginx, or another web server.${NC}"
    echo -e "${BLUE}You may want to stop it: sudo systemctl stop apache2 nginx${NC}"
else
    echo -e "${GREEN}✅ Port 80 is free${NC}"
fi

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  Port Check Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo -e "${BLUE}Now try running: ${YELLOW}docker-compose up -d${NC}"

# Final verification
echo -e "${YELLOW}Current port status:${NC}"
echo -e "Port 80: $(sudo lsof -i :80 >/dev/null 2>&1 && echo "In use" || echo "Free")"
echo -e "Port 7474: $(sudo lsof -i :7474 >/dev/null 2>&1 && echo "In use" || echo "Free")"
echo -e "Port 7687: $(sudo lsof -i :7687 >/dev/null 2>&1 && echo "In use" || echo "Free")" 
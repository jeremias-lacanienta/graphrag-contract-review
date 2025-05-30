# GraphRAG Contract Review - EC2 Deployment Guide

This guide will help you deploy the GraphRAG Contract Review application on AWS EC2 with Streamlit hosted on port 80.

## Quick Start

1. **Launch EC2 Instance**
   - Recommended: Ubuntu 22.04 LTS
   - Instance type: t3.medium or larger (minimum 4GB RAM)
   - Security Group: Allow ports 22 (SSH), 80 (HTTP), 7474 (Neo4j Browser), 7687 (Neo4j Bolt)

2. **Connect to your EC2 instance**
   ```bash
   ssh -i your-key.pem ubuntu@your-ec2-ip
   ```

3. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd graphrag-contract-review
   ```

4. **Run the setup script**
   ```bash
   chmod +x deploy-ec2.sh
   ./deploy-ec2.sh
   ```

5. **Configure environment variables**
   ```bash
   nano .env
   # Add your OpenAI API key
   ```

6. **Start the application**
   ```bash
   docker-compose up -d
   ```

7. **Load your contract data**
   ```bash
   chmod +x data-setup.sh
   ./data-setup.sh
   ```

## Detailed Setup Instructions

### Prerequisites

- AWS EC2 instance with Ubuntu 22.04 LTS
- At least 4GB RAM (t3.medium recommended)
- 20GB+ storage space
- Security group allowing inbound traffic on ports 22, 80, 7474, 7687

### Step-by-step Deployment

#### 1. EC2 Security Group Configuration

Create or modify your security group to allow:
- Port 22 (SSH) - for remote access
- Port 80 (HTTP) - for Streamlit web interface
- Port 7474 (HTTP) - for Neo4j Browser (optional, for database management)
- Port 7687 (Custom TCP) - for Neo4j Bolt protocol (optional, for external connections)

#### 2. Connect and Setup

```bash
# Connect to your EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-public-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Clone your repository
git clone <your-repository-url>
cd graphrag-contract-review

# Make scripts executable
chmod +x deploy-ec2.sh data-setup.sh

# Run the automated setup
./deploy-ec2.sh
```

#### 3. Configure Environment Variables

```bash
# Copy example environment file
cp env.example .env

# Edit with your actual values
nano .env
```

Required configuration:
```env
OPENAI_API_KEY=sk-your-actual-openai-api-key
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password123
```

#### 4. Start Services

```bash
# Start all services in detached mode
docker-compose up -d

# Check status
docker-compose ps

# View logs if needed
docker-compose logs -f
```

#### 5. Load Contract Data

```bash
# Create data directory and add your files
mkdir -p data
# Upload your PDF or JSON contract files to the data/ directory

# Process the data
./data-setup.sh
```

### Accessing the Application

Once deployed, you can access:

- **Streamlit Interface**: `http://your-ec2-public-ip` (port 80)
- **Neo4j Browser**: `http://your-ec2-public-ip:7474` (username: neo4j, password: password123)

### Managing the Application

#### View Application Logs
```bash
# View all service logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f app
docker-compose logs -f neo4j
```

#### Stop/Start Services
```bash
# Stop all services
docker-compose down

# Start services
docker-compose up -d

# Restart specific service
docker-compose restart app
```

#### Update Application
```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

#### Backup Neo4j Data
```bash
# Create backup
docker exec neo4j-graphrag neo4j-admin dump --to=/var/lib/neo4j/backup.dump
docker cp neo4j-graphrag:/var/lib/neo4j/backup.dump ./neo4j-backup.dump
```

### Troubleshooting

#### Common Issues

1. **Cannot connect to Streamlit on port 80**
   - Check EC2 Security Group allows port 80
   - Verify container is running: `docker-compose ps`
   - Check logs: `docker-compose logs app`

2. **Neo4j connection issues**
   - Wait 60+ seconds for Neo4j to fully start
   - Check container status: `docker ps`
   - Verify environment variables in .env file

3. **OpenAI API errors**
   - Ensure OPENAI_API_KEY is correctly set in .env
   - Verify API key has sufficient credits

4. **Memory issues**
   - Ensure EC2 instance has at least 4GB RAM
   - Monitor with: `htop` or `free -h`

#### Performance Optimization

1. **For better performance with large datasets**:
   - Use t3.large or larger instance
   - Add swap space:
     ```bash
     sudo fallocate -l 2G /swapfile
     sudo chmod 600 /swapfile
     sudo mkswap /swapfile
     sudo swapon /swapfile
     ```

2. **Enable persistent data storage**:
   The Docker volumes will persist data across container restarts, but for additional backup:
   ```bash
   # Backup volumes
   docker run --rm -v graphrag-contract-review_neo4j_data:/data -v $(pwd):/backup alpine tar czf /backup/neo4j-data-backup.tar.gz -C /data .
   ```

### Security Considerations

1. **Production Deployment**:
   - Change default Neo4j password
   - Use HTTPS with SSL certificates
   - Restrict Security Group access to specific IPs
   - Enable CloudWatch monitoring

2. **Environment Variables**:
   - Never commit .env file to version control
   - Use AWS Systems Manager Parameter Store for sensitive data in production
   - Rotate API keys regularly

### Cost Optimization

- Use t3.medium for development/testing
- Use spot instances for non-production workloads  
- Stop EC2 instance when not in use (data persists in EBS volumes)
- Monitor costs with AWS Cost Explorer

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review logs: `docker-compose logs -f`
3. Ensure all prerequisites are met
4. Verify environment variables are correctly set

For additional help, please refer to the main README.md or open an issue in the repository. 
# GraphRAG Contract Review - EC2 Deployment Guide

This guide provides instructions for deploying the GraphRAG Contract Review application on an EC2 instance, accessible on port 80.

## Prerequisites

- AWS EC2 instance (Ubuntu 20.04 or 22.04 recommended)
- At least 4GB RAM and 2 vCPUs
- Security group allowing inbound traffic on ports 22 (SSH), 80 (HTTP), and optionally 7687 (Neo4j)
- OpenAI API key

## Deployment Options

### Option 1: Native EC2 Deployment (Recommended)

This method installs everything directly on the EC2 instance.

#### Step 1: Prepare Your EC2 Instance

1. Launch an Ubuntu EC2 instance
2. Connect via SSH
3. Clone your repository:
```bash
git clone <your-repo-url>
cd graphrag-contract-review
```

#### Step 2: Run the Deployment Script

Make the deployment script executable and run it:

```bash
chmod +x deploy_ec2.sh
./deploy_ec2.sh
```

The script will:
- Install system dependencies (Python 3.10, Nginx, Neo4j)
- Set up the Python virtual environment
- Configure systemd service for the Streamlit app
- Configure Nginx as a reverse proxy
- Set up firewall rules
- Start all services

#### Step 3: Configure Environment Variables

Edit the `.env` file to add your OpenAI API key:

```bash
nano .env
```

Update the following:
```env
OPENAI_API_KEY=your_actual_openai_api_key_here
NEO4J_PASSWORD=your_secure_password_here
```

#### Step 4: Restart the Service

```bash
sudo systemctl restart graphrag-streamlit
```

#### Step 5: Verify Deployment

Check that all services are running:
```bash
sudo systemctl status neo4j
sudo systemctl status nginx
sudo systemctl status graphrag-streamlit
```

Your application should now be accessible at `http://your-ec2-public-ip`

### Option 2: Docker Deployment

This method uses Docker containers for easier deployment and management.

#### Prerequisites for Docker Deployment

Install Docker and Docker Compose on your EC2 instance:

```bash
# Install Docker
sudo apt update
sudo apt install -y docker.io docker-compose
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
```

Log out and back in for the group changes to take effect.

#### Step 1: Prepare Environment

Create a `.env` file with your configuration:

```bash
cat > .env << EOF
OPENAI_API_KEY=your_openai_api_key_here
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=neo4j123
EOF
```

#### Step 2: Deploy with Docker Compose

```bash
# Build and start all services
docker-compose up -d

# Check logs
docker-compose logs -f
```

#### Step 3: Verify Docker Deployment

```bash
# Check running containers
docker-compose ps

# Check individual service logs
docker-compose logs app
docker-compose logs neo4j
docker-compose logs nginx
```

Your application should be accessible at `http://your-ec2-public-ip`

## Post-Deployment Configuration

### 1. Upload Contract Data

Upload your contract files to the `data/` directory and run the ingestion process:

```bash
# For native deployment
source .venv_graphrag/bin/activate
python create_graph_from_json.py

# For Docker deployment
docker-compose exec app python create_graph_from_json.py
```

### 2. Security Considerations

#### SSL/HTTPS Setup (Optional but Recommended)

To enable HTTPS, you can use Let's Encrypt:

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate (replace your-domain.com with your actual domain)
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

#### Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS (if using SSL)
sudo ufw enable
```

### 3. Monitoring and Maintenance

#### Check Application Logs

```bash
# Native deployment
sudo journalctl -u graphrag-streamlit -f

# Docker deployment
docker-compose logs -f app
```

#### Restart Services

```bash
# Native deployment
sudo systemctl restart graphrag-streamlit
sudo systemctl restart nginx

# Docker deployment
docker-compose restart app
docker-compose restart nginx
```

#### Update Application

```bash
# Native deployment
git pull
source .venv_graphrag/bin/activate
pip install -r requirements_graphrag.txt
sudo systemctl restart graphrag-streamlit

# Docker deployment
git pull
docker-compose build app
docker-compose up -d app
```

## Troubleshooting

### Common Issues

1. **Application not accessible on port 80**
   - Check if nginx is running: `sudo systemctl status nginx`
   - Check firewall: `sudo ufw status`
   - Check EC2 security group settings

2. **Neo4j connection errors**
   - Verify Neo4j is running: `sudo systemctl status neo4j`
   - Check credentials in `.env` file
   - Test connection: `cypher-shell -u neo4j -p your_password`

3. **Streamlit app crashes**
   - Check logs: `sudo journalctl -u graphrag-streamlit -f`
   - Verify Python dependencies: `source .venv_graphrag/bin/activate && pip list`
   - Check OpenAI API key in `.env`

### Performance Optimization

1. **Increase Neo4j memory** (for large datasets):
   ```bash
   sudo nano /etc/neo4j/neo4j.conf
   # Uncomment and adjust:
   # dbms.memory.heap.initial_size=2g
   # dbms.memory.heap.max_size=4g
   sudo systemctl restart neo4j
   ```

2. **Nginx optimization**:
   ```bash
   sudo nano /etc/nginx/nginx.conf
   # Increase worker_processes and worker_connections
   sudo systemctl restart nginx
   ```

## Scaling Considerations

For production deployments with high traffic:

1. **Use Application Load Balancer** with multiple EC2 instances
2. **Separate Neo4j database** to a dedicated instance or managed service
3. **Use Redis** for session management across multiple app instances
4. **Implement monitoring** with CloudWatch or similar tools

## Cost Optimization

1. **Use spot instances** for development/testing
2. **Schedule automatic shutdown** during off-hours
3. **Use smaller instance types** for low-traffic applications
4. **Monitor usage** with AWS Cost Explorer

## Support

For issues related to:
- **Application bugs**: Check the application logs and GitHub issues
- **AWS infrastructure**: Consult AWS documentation
- **Neo4j issues**: Check Neo4j logs and documentation
- **Nginx configuration**: Review nginx error logs

Remember to regularly backup your Neo4j database and application data! 
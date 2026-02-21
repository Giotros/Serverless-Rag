#!/bin/bash
# =============================================================================
# Deployment Script για Serverless RAG
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Serverless RAG - Deployment Script${NC}"
echo -e "${GREEN}========================================${NC}"

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

command -v python3 >/dev/null 2>&1 || { echo -e "${RED}Python 3 required${NC}"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo -e "${RED}Node.js/npm required${NC}"; exit 1; }
command -v terraform >/dev/null 2>&1 || { echo -e "${RED}Terraform required${NC}"; exit 1; }
command -v aws >/dev/null 2>&1 || { echo -e "${RED}AWS CLI required${NC}"; exit 1; }

echo -e "${GREEN}✓ All prerequisites met${NC}"

# Load environment variables
if [ -f .env ]; then
    echo -e "\n${YELLOW}Loading environment variables...${NC}"
    export $(cat .env | grep -v '^#' | xargs)
    echo -e "${GREEN}✓ Environment loaded${NC}"
else
    echo -e "${RED}Error: .env file not found. Copy .env.example to .env and configure.${NC}"
    exit 1
fi

# Check required variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}Error: OPENAI_API_KEY not set${NC}"
    exit 1
fi

# Install Python dependencies
echo -e "\n${YELLOW}Installing Python dependencies...${NC}"
pip install -r requirements.txt -q
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Create Lambda deployment packages
echo -e "\n${YELLOW}Creating Lambda deployment packages...${NC}"

# Ingestion Lambda
cd src/lambdas/ingestion
zip -r deployment.zip handler.py > /dev/null
cd ../../..
echo -e "${GREEN}✓ Ingestion Lambda packaged${NC}"

# Embedding Lambda
cd src/lambdas/embedding
zip -r deployment.zip handler.py > /dev/null
cd ../../..
echo -e "${GREEN}✓ Embedding Lambda packaged${NC}"

# Query Lambda
cd src/lambdas/query
zip -r deployment.zip handler.py > /dev/null
cd ../../..
echo -e "${GREEN}✓ Query Lambda packaged${NC}"

# Create Lambda layer
echo -e "\n${YELLOW}Creating Lambda layer...${NC}"
mkdir -p .layer/python
pip install openai pinecone-client pypdf python-docx -t .layer/python -q
cd .layer
zip -r ../src/layers/common.zip python > /dev/null
cd ..
rm -rf .layer
echo -e "${GREEN}✓ Lambda layer created${NC}"

# Deploy with Terraform
echo -e "\n${YELLOW}Deploying infrastructure with Terraform...${NC}"
cd infra/terraform

terraform init -upgrade > /dev/null

echo -e "${YELLOW}Planning deployment...${NC}"
terraform plan -var="openai_api_key=$OPENAI_API_KEY" \
               -var="pinecone_api_key=$PINECONE_API_KEY" \
               -out=tfplan

echo -e "\n${YELLOW}Apply deployment? (yes/no)${NC}"
read -r CONFIRM

if [ "$CONFIRM" = "yes" ]; then
    terraform apply tfplan

    # Get outputs
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}Deployment Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"

    echo -e "\n${YELLOW}API Endpoint:${NC}"
    terraform output api_endpoint

    echo -e "\n${YELLOW}S3 Bucket:${NC}"
    terraform output s3_bucket

    echo -e "\n${YELLOW}Test your deployment:${NC}"
    echo -e "curl -X POST \$(terraform output -raw api_endpoint)/query \\"
    echo -e "  -H 'Content-Type: application/json' \\"
    echo -e "  -d '{\"query\": \"Πόσες μέρες άδεια δικαιούμαι;\"}'"
else
    echo -e "${YELLOW}Deployment cancelled${NC}"
fi

cd ../..

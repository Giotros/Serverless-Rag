# =============================================================================
# Serverless RAG Project - Makefile
# =============================================================================

.PHONY: help install test lint deploy clean benchmark docs

# Default target
help:
	@echo "Serverless RAG - Available Commands"
	@echo "===================================="
	@echo "make install      - Install dependencies"
	@echo "make test         - Run unit tests"
	@echo "make lint         - Run linters"
	@echo "make deploy       - Deploy to AWS"
	@echo "make benchmark    - Run benchmarks"
	@echo "make docs         - Generate documentation"
	@echo "make clean        - Clean build artifacts"
	@echo "make package      - Create Lambda packages"

# Install dependencies
install:
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt
	@echo "Installing Node dependencies..."
	npm install
	@echo "Done!"

# Run tests
test:
	@echo "Running unit tests..."
	python -m pytest tests/unit -v --tb=short
	@echo "Done!"

# Run linters
lint:
	@echo "Running linters..."
	black --check src/
	flake8 src/ --max-line-length=100
	mypy src/ --ignore-missing-imports
	@echo "Done!"

# Format code
format:
	@echo "Formatting code..."
	black src/ tests/ examples/
	@echo "Done!"

# Create Lambda deployment packages
package:
	@echo "Creating Lambda packages..."
	@mkdir -p .build

	# Ingestion Lambda
	cd src/lambdas/ingestion && zip -r ../../../.build/ingestion.zip handler.py

	# Embedding Lambda
	cd src/lambdas/embedding && zip -r ../../../.build/embedding.zip handler.py

	# Query Lambda
	cd src/lambdas/query && zip -r ../../../.build/query.zip handler.py

	# Common layer
	mkdir -p .build/layer/python
	pip install openai pinecone-client -t .build/layer/python -q
	cd .build/layer && zip -r ../common-layer.zip python

	@echo "Packages created in .build/"

# Deploy infrastructure
deploy: package
	@echo "Deploying to AWS..."
	./scripts/deploy.sh
	@echo "Done!"

# Run benchmarks
benchmark:
	@echo "Running cost analysis..."
	python benchmarks/scripts/cost_analysis.py
	@echo ""
	@echo "Running latency benchmarks..."
	python benchmarks/scripts/latency_benchmark.py
	@echo "Done!"

# Generate Word report
docs:
	@echo "Generating documentation..."
	node docs/create_report.js
	@echo "Done!"

# Clean build artifacts
clean:
	@echo "Cleaning..."
	rm -rf .build/
	rm -rf .layer/
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf src/**/__pycache__/
	rm -rf tests/**/__pycache__/
	rm -f src/lambdas/*/deployment.zip
	@echo "Done!"

# Local development server (mock)
dev:
	@echo "Starting local development server..."
	@echo "Note: This requires additional setup"
	@echo "See docs/development.md for instructions"

# Terraform commands
tf-init:
	cd infra/terraform && terraform init

tf-plan:
	cd infra/terraform && terraform plan

tf-apply:
	cd infra/terraform && terraform apply

tf-destroy:
	cd infra/terraform && terraform destroy

# Quick validation
validate:
	@echo "Validating project structure..."
	@test -f src/lambdas/ingestion/handler.py || (echo "Missing ingestion handler" && exit 1)
	@test -f src/lambdas/embedding/handler.py || (echo "Missing embedding handler" && exit 1)
	@test -f src/lambdas/query/handler.py || (echo "Missing query handler" && exit 1)
	@test -f infra/terraform/main.tf || (echo "Missing Terraform config" && exit 1)
	@test -f requirements.txt || (echo "Missing requirements.txt" && exit 1)
	@echo "✓ All files present"

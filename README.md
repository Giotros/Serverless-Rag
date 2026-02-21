# Serverless RAG for Enterprise Knowledge

---

## Overview

This project implements a **Retrieval-Augmented Generation (RAG)** system using AWS serverless services. It allows users to query corporate documents in natural language and receive accurate, source-cited answers.

### Key Features

- ✅ **100% Serverless** - Zero cost when idle
- ✅ **AWS Free Tier Compatible** - Runs within free-tier limits
- ✅ **Multi-Vector DB** - Supports Pinecone & pgvector
- ✅ **Cost Analysis** - Serverless vs dedicated cost comparison included

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           CLIENTS                               │
│           Web App  |  Slack Bot  |  API Client                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AWS API Gateway                            │
│                (REST API + Rate Limiting)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
    ┌───────────┐     ┌───────────┐      ┌───────────┐
    │ Ingestion │     │ Embedding │      │   Query   │
    │  Lambda   │     │  Lambda   │      │  Lambda   │
    │           │     │           │      │           │
    │ • Chunking│     │ • OpenAI  │      │ • Search  │
    │ • Parse   │     │ • Batch   │      │ • Context │
    │ • Queue   │     │ • Store   │      │ • LLM     │
    └─────┬─────┘     └─────┬─────┘      └─────┬─────┘
          │                 │                  │
          ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                        STORAGE LAYER                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │    S3    │  │ DynamoDB │  │ Pinecone │  │   SQS    │        │
│  │  (Docs)  │  │(Metadata)│  │(Vectors) │  │ (Queue)  │        │
│  │ 5GB Free │  │25GB Free │  │100K Free │  │ 1M Free  │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Stack

| Component | Technology | Why |
|-----------|------------|-----|
| Compute | AWS Lambda | Pay-per-use, auto-scale |
| API | API Gateway | Managed, auth integration |
| Vector DB | Pinecone | 100K free vectors |
| Storage | S3 + DynamoDB | Generous free tier |
| Embeddings | OpenAI text-embedding-3-small | Best price/performance ratio |
| LLM | GPT-4o-mini | Cost-optimized |
| IaC | Terraform | Reproducible deployments |

---

## Project Structure

```
serverless-rag-project/
├── src/
│   ├── lambdas/
│   │   ├── ingestion/    # Document processing & chunking
│   │   ├── embedding/    # Vector generation
│   │   └── query/        # RAG query handling
│   └── layers/
│       └── common/       # Shared utilities & VectorDB abstraction
├── infra/
│   └── terraform/        # Infrastructure as Code
├── data/
│   └── sample_docs/      # Test documents
├── benchmarks/
│   ├── scripts/          # Performance & cost analysis scripts
│   └── results/          # Benchmark outputs
├── tests/
│   ├── unit/
│   └── integration/
└── docs/
    └── create_report.js  # Academic report generator
```

---

## Getting Started

### Prerequisites

```bash
# Required tools
- Python 3.11+
- Node.js 18+
- AWS CLI (configured)
- Terraform 1.5+

# API Keys
- OpenAI API key
- Pinecone API key (free tier: pinecone.io)
```

### Quick Start

```bash
# 1. Clone
git clone https://github.com/Giotros/Serverless-Rag.git
cd serverless-rag-project

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env with your API keys

# 4. Deploy
cd infra/terraform
terraform init
terraform apply

# 5. Test
python -m pytest tests/
```
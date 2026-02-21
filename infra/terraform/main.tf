# =============================================================================
# Serverless RAG Infrastructure - Terraform
# =============================================================================
# Περιγραφή: IaC για AWS serverless RAG architecture
# Συμβατό με AWS Free Tier
# =============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# =============================================================================
# Variables
# =============================================================================

variable "project_name" {
  description = "Όνομα project"
  default     = "serverless-rag"
}

variable "environment" {
  description = "Environment (dev/staging/prod)"
  default     = "dev"
}

variable "aws_region" {
  default = "eu-west-1"
}

variable "openai_api_key" {
  description = "OpenAI API Key"
  sensitive   = true
}

variable "pinecone_api_key" {
  description = "Pinecone API Key"
  sensitive   = true
  default     = ""
}

variable "pinecone_index" {
  default = "rag-index"
}

# =============================================================================
# Provider
# =============================================================================

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# =============================================================================
# S3 Bucket - Document Storage
# =============================================================================

resource "aws_s3_bucket" "documents" {
  bucket = "${var.project_name}-docs-${var.environment}-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# =============================================================================
# DynamoDB Tables
# =============================================================================

# Metadata Table
resource "aws_dynamodb_table" "metadata" {
  name         = "${var.project_name}-metadata-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "document_id"

  attribute {
    name = "document_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}

# Cache Table
resource "aws_dynamodb_table" "cache" {
  name         = "${var.project_name}-cache-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "cache_key"

  attribute {
    name = "cache_key"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
}

# =============================================================================
# SQS Queue
# =============================================================================

resource "aws_sqs_queue" "embedding_queue" {
  name                       = "${var.project_name}-embedding-${var.environment}"
  delay_seconds              = 0
  max_message_size           = 262144
  message_retention_seconds  = 86400
  receive_wait_time_seconds  = 20
  visibility_timeout_seconds = 300

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "dlq" {
  name = "${var.project_name}-dlq-${var.environment}"
}

# =============================================================================
# IAM Role for Lambda
# =============================================================================

resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-lambda-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "lambda" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.documents.arn,
          "${aws_s3_bucket.documents.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = [
          aws_dynamodb_table.metadata.arn,
          aws_dynamodb_table.cache.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = [aws_sqs_queue.embedding_queue.arn]
      }
    ]
  })
}

# =============================================================================
# Lambda Functions
# =============================================================================

# Ingestion Lambda
resource "aws_lambda_function" "ingestion" {
  filename         = "${path.module}/../../src/lambdas/ingestion/deployment.zip"
  function_name    = "${var.project_name}-ingestion-${var.environment}"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.11"
  timeout          = 60
  memory_size      = 512

  environment {
    variables = {
      DOCUMENTS_BUCKET    = aws_s3_bucket.documents.id
      EMBEDDING_QUEUE_URL = aws_sqs_queue.embedding_queue.url
      METADATA_TABLE      = aws_dynamodb_table.metadata.name
      CHUNK_SIZE          = "1000"
      CHUNK_OVERLAP       = "200"
    }
  }
}

# Embedding Lambda
resource "aws_lambda_function" "embedding" {
  filename         = "${path.module}/../../src/lambdas/embedding/deployment.zip"
  function_name    = "${var.project_name}-embedding-${var.environment}"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.11"
  timeout          = 120
  memory_size      = 1024

  environment {
    variables = {
      OPENAI_API_KEY   = var.openai_api_key
      PINECONE_API_KEY = var.pinecone_api_key
      PINECONE_INDEX   = var.pinecone_index
      VECTOR_DB_TYPE   = "pinecone"
      EMBEDDING_MODEL  = "text-embedding-3-small"
      METADATA_TABLE   = aws_dynamodb_table.metadata.name
    }
  }
}

# Query Lambda
resource "aws_lambda_function" "query" {
  filename         = "${path.module}/../../src/lambdas/query/deployment.zip"
  function_name    = "${var.project_name}-query-${var.environment}"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 512

  environment {
    variables = {
      OPENAI_API_KEY   = var.openai_api_key
      PINECONE_API_KEY = var.pinecone_api_key
      PINECONE_INDEX   = var.pinecone_index
      VECTOR_DB_TYPE   = "pinecone"
      LLM_MODEL        = "gpt-4o-mini"
      CACHE_TABLE      = aws_dynamodb_table.cache.name
      CACHE_ENABLED    = "true"
      TOP_K            = "5"
    }
  }
}

# =============================================================================
# S3 Event Notification
# =============================================================================

resource "aws_lambda_permission" "s3" {
  statement_id  = "AllowS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.documents.arn
}

resource "aws_s3_bucket_notification" "documents" {
  bucket = aws_s3_bucket.documents.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.ingestion.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "uploads/"
  }

  depends_on = [aws_lambda_permission.s3]
}

# =============================================================================
# SQS Event Source Mapping
# =============================================================================

resource "aws_lambda_event_source_mapping" "embedding" {
  event_source_arn = aws_sqs_queue.embedding_queue.arn
  function_name    = aws_lambda_function.embedding.arn
  batch_size       = 10
  enabled          = true
}

# =============================================================================
# API Gateway
# =============================================================================

resource "aws_apigatewayv2_api" "main" {
  name          = "${var.project_name}-api-${var.environment}"
  protocol_type = "HTTP"

  cors_configuration {
    allow_headers = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_origins = ["*"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_stage" "main" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = var.environment
  auto_deploy = true
}

# Query Integration
resource "aws_apigatewayv2_integration" "query" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.query.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "query" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /query"
  target    = "integrations/${aws_apigatewayv2_integration.query.id}"
}

resource "aws_lambda_permission" "api_query" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.query.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# =============================================================================
# Outputs
# =============================================================================

output "api_endpoint" {
  description = "API Gateway endpoint"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/${var.environment}"
}

output "s3_bucket" {
  description = "S3 bucket για documents"
  value       = aws_s3_bucket.documents.id
}

output "sqs_queue" {
  description = "SQS queue URL"
  value       = aws_sqs_queue.embedding_queue.url
}

output "lambda_ingestion" {
  value = aws_lambda_function.ingestion.function_name
}

output "lambda_embedding" {
  value = aws_lambda_function.embedding.function_name
}

output "lambda_query" {
  value = aws_lambda_function.query.function_name
}

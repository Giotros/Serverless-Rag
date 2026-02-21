"""
Embedding Lambda Handler
Δημιουργία vector embeddings και αποθήκευση σε vector database.

Serverless RAG Project - MSc Thesis
"""

import json
import os
import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import boto3

# ============================================================================
# Configuration
# ============================================================================

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
PINECONE_INDEX = os.environ.get("PINECONE_INDEX", "rag-index")
VECTOR_DB_TYPE = os.environ.get("VECTOR_DB_TYPE", "pinecone")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1536"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "100"))
METADATA_TABLE = os.environ.get("METADATA_TABLE", "rag-metadata")

# AWS Clients
dynamodb = boto3.resource("dynamodb")

# Lazy-loaded clients
_openai_client = None
_pinecone_index = None


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class EmbeddingResult:
    """Αποτέλεσμα embedding"""
    chunk_id: str
    document_id: str
    vector: List[float]
    text: str
    metadata: Dict[str, Any]


@dataclass
class ProcessingMetrics:
    """Μετρικές επεξεργασίας"""
    total_chunks: int
    successful: int
    failed: int
    total_tokens: int
    latency_ms: float
    cost_usd: float


# ============================================================================
# OpenAI Client
# ============================================================================

def get_openai_client():
    """Lazy initialization του OpenAI client"""
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def create_embeddings(texts: List[str]) -> Tuple[List[List[float]], int]:
    """
    Δημιουργία embeddings μέσω OpenAI API.

    Returns:
        Tuple of (embeddings list, total tokens used)
    """
    if not texts:
        return [], 0

    client = get_openai_client()

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )

    embeddings = [item.embedding for item in response.data]
    tokens = response.usage.total_tokens

    return embeddings, tokens


def calculate_cost(tokens: int) -> float:
    """Υπολογισμός κόστους embedding (text-embedding-3-small: $0.02/1M tokens)"""
    return (tokens / 1_000_000) * 0.02


# ============================================================================
# Pinecone Client
# ============================================================================

def get_pinecone_index():
    """Lazy initialization του Pinecone index"""
    global _pinecone_index
    if _pinecone_index is None:
        from pinecone import Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        _pinecone_index = pc.Index(PINECONE_INDEX)
    return _pinecone_index


def store_vectors_pinecone(results: List[EmbeddingResult]) -> int:
    """
    Αποθήκευση vectors στο Pinecone.

    Returns:
        Number of vectors stored
    """
    if not results:
        return 0

    index = get_pinecone_index()

    # Prepare vectors for upsert
    vectors = []
    for r in results:
        vectors.append({
            "id": r.chunk_id,
            "values": r.vector,
            "metadata": {
                "document_id": r.document_id,
                "text": r.text[:1000],  # Pinecone metadata limit
                **r.metadata
            }
        })

    # Batch upsert (max 100 per request)
    stored = 0
    for i in range(0, len(vectors), BATCH_SIZE):
        batch = vectors[i:i + BATCH_SIZE]
        index.upsert(vectors=batch)
        stored += len(batch)

    return stored


# ============================================================================
# pgvector Storage (Alternative)
# ============================================================================

def store_vectors_pgvector(results: List[EmbeddingResult],
                           connection_string: str) -> int:
    """
    Αποθήκευση vectors σε PostgreSQL με pgvector.

    Requires: psycopg2, pgvector extension
    """
    try:
        import psycopg2
        from pgvector.psycopg2 import register_vector

        conn = psycopg2.connect(connection_string)
        register_vector(conn)
        cur = conn.cursor()

        # Create table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id TEXT PRIMARY KEY,
                document_id TEXT,
                embedding vector(1536),
                text TEXT,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert vectors
        stored = 0
        for r in results:
            cur.execute("""
                INSERT INTO embeddings (id, document_id, embedding, text, metadata)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    text = EXCLUDED.text,
                    metadata = EXCLUDED.metadata
            """, (
                r.chunk_id,
                r.document_id,
                r.vector,
                r.text,
                json.dumps(r.metadata)
            ))
            stored += 1

        conn.commit()
        cur.close()
        conn.close()

        return stored

    except ImportError:
        print("pgvector support requires psycopg2 and pgvector packages")
        return 0


# ============================================================================
# Processing Logic
# ============================================================================

def generate_chunk_id(document_id: str, chunk_index: int, text: str) -> str:
    """Δημιουργία unique chunk ID"""
    content = f"{document_id}:{chunk_index}:{text[:100]}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def process_chunks(
    chunks: List[Dict[str, Any]],
    document_id: str,
    doc_metadata: Dict[str, Any]
) -> Tuple[List[EmbeddingResult], ProcessingMetrics]:
    """
    Επεξεργασία chunks: embedding + preparation for storage.

    Returns:
        Tuple of (results, metrics)
    """
    start_time = time.time()

    # Extract texts
    texts = [c["text"] for c in chunks]

    # Create embeddings
    try:
        embeddings, tokens = create_embeddings(texts)
    except Exception as e:
        print(f"Embedding error: {e}")
        return [], ProcessingMetrics(
            total_chunks=len(chunks),
            successful=0,
            failed=len(chunks),
            total_tokens=0,
            latency_ms=0,
            cost_usd=0
        )

    # Build results
    results = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_id = generate_chunk_id(
            document_id,
            chunk.get("chunk_index", i),
            chunk["text"]
        )

        results.append(EmbeddingResult(
            chunk_id=chunk_id,
            document_id=document_id,
            vector=embedding,
            text=chunk["text"],
            metadata={
                **doc_metadata,
                "chunk_index": chunk.get("chunk_index", i)
            }
        ))

    latency = (time.time() - start_time) * 1000

    metrics = ProcessingMetrics(
        total_chunks=len(chunks),
        successful=len(results),
        failed=len(chunks) - len(results),
        total_tokens=tokens,
        latency_ms=round(latency, 2),
        cost_usd=round(calculate_cost(tokens), 6)
    )

    return results, metrics


def update_document_status(document_id: str, status: str, chunk_count: int = 0):
    """Ενημέρωση status εγγράφου στο DynamoDB"""
    try:
        table = dynamodb.Table(METADATA_TABLE)
        table.update_item(
            Key={"document_id": document_id},
            UpdateExpression="SET #status = :status, processed_chunks = :chunks",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": status,
                ":chunks": chunk_count
            }
        )
    except Exception as e:
        print(f"Failed to update status: {e}")


# ============================================================================
# Lambda Handler
# ============================================================================

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda entry point.

    Triggers:
    - SQS Event: Messages from ingestion queue
    - Direct invocation: For testing
    """

    all_results = []
    total_metrics = {
        "documents": 0,
        "chunks": 0,
        "tokens": 0,
        "cost": 0.0,
        "vectors_stored": 0
    }

    # Parse messages
    messages = []

    if "Records" in event:
        # SQS Trigger
        for record in event["Records"]:
            body = json.loads(record["body"])
            messages.append(body)
    elif "document_id" in event:
        # Direct invocation
        messages.append(event)
    elif "body" in event:
        # API Gateway
        body = event["body"]
        if isinstance(body, str):
            body = json.loads(body)
        messages.append(body)

    # Process each message
    for msg in messages:
        document_id = msg.get("document_id", "unknown")
        chunks = msg.get("chunks", [])
        metadata = msg.get("metadata", {})

        if not chunks:
            print(f"No chunks for document {document_id}")
            continue

        print(f"Processing {len(chunks)} chunks for {document_id}")

        # Process chunks
        results, metrics = process_chunks(chunks, document_id, metadata)

        # Store vectors
        vectors_stored = 0
        if results:
            if VECTOR_DB_TYPE == "pinecone":
                vectors_stored = store_vectors_pinecone(results)
            # Add pgvector support here if needed

        # Update document status
        status = "completed" if vectors_stored > 0 else "failed"
        update_document_status(document_id, status, vectors_stored)

        # Aggregate metrics
        total_metrics["documents"] += 1
        total_metrics["chunks"] += metrics.total_chunks
        total_metrics["tokens"] += metrics.total_tokens
        total_metrics["cost"] += metrics.cost_usd
        total_metrics["vectors_stored"] += vectors_stored

        all_results.append({
            "document_id": document_id,
            "chunks_processed": metrics.successful,
            "vectors_stored": vectors_stored,
            "tokens": metrics.total_tokens,
            "latency_ms": metrics.latency_ms,
            "cost_usd": metrics.cost_usd
        })

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({
            "message": f"Processed {total_metrics['documents']} documents",
            "metrics": total_metrics,
            "results": all_results
        })
    }



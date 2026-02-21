"""
Query Lambda Handler
RAG Pipeline: Semantic search + LLM response generation.

Serverless RAG Project - MSc Thesis
"""

import json
import os
import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import boto3

# ============================================================================
# Configuration
# ============================================================================

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
PINECONE_INDEX = os.environ.get("PINECONE_INDEX", "rag-index")
VECTOR_DB_TYPE = os.environ.get("VECTOR_DB_TYPE", "pinecone")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
CACHE_TABLE = os.environ.get("CACHE_TABLE", "rag-cache")
CACHE_ENABLED = os.environ.get("CACHE_ENABLED", "true").lower() == "true"
CACHE_TTL = int(os.environ.get("CACHE_TTL", "3600"))  # 1 hour
TOP_K = int(os.environ.get("TOP_K", "5"))
SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD", "0.7"))

# AWS Clients
dynamodb = boto3.resource("dynamodb")

# Lazy-loaded clients
_openai_client = None
_pinecone_index = None


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SearchResult:
    """Αποτέλεσμα semantic search"""
    chunk_id: str
    document_id: str
    text: str
    score: float
    metadata: Dict[str, Any]


@dataclass
class QueryMetrics:
    """Μετρικές query"""
    embedding_ms: float
    search_ms: float
    llm_ms: float
    total_ms: float
    tokens_used: int
    cost_usd: float
    cache_hit: bool


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


def create_query_embedding(text: str) -> List[float]:
    """Δημιουργία embedding για το query"""
    client = get_openai_client()

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )

    return response.data[0].embedding


def generate_response(query: str, context: str, history: List[Dict] = None) -> Tuple[str, int]:
    """
    Δημιουργία απάντησης μέσω LLM με το context.

    Returns:
        Tuple of (response text, tokens used)
    """
    client = get_openai_client()

    system_prompt = """Είσαι ένας βοηθός που απαντά ερωτήσεις βασιζόμενος
ΑΠΟΚΛΕΙΣΤΙΚΑ στο context που σου δίνεται.

Κανόνες:
1. Απάντησε ΜΟΝΟ με βάση το context
2. Αν δεν υπάρχει σχετική πληροφορία, πες "Δεν βρήκα σχετική πληροφορία στα έγγραφα"
3. Αναφέρου στην πηγή όταν είναι δυνατόν
4. Να είσαι σύντομος και ακριβής
5. Απάντα στη γλώσσα της ερώτησης"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"""Context από εταιρικά έγγραφα:
---
{context}
---

Ερώτηση: {query}

Απάντηση:"""}
    ]

    # Add conversation history if provided
    if history:
        messages = [messages[0]] + history + [messages[-1]]

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=500
    )

    answer = response.choices[0].message.content
    tokens = response.usage.total_tokens

    return answer, tokens


# ============================================================================
# Pinecone Search
# ============================================================================

def get_pinecone_index():
    """Lazy initialization του Pinecone index"""
    global _pinecone_index
    if _pinecone_index is None:
        from pinecone import Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        _pinecone_index = pc.Index(PINECONE_INDEX)
    return _pinecone_index


def search_pinecone(
    query_embedding: List[float],
    top_k: int = TOP_K,
    filter_metadata: Dict = None
) -> List[SearchResult]:
    """
    Semantic search στο Pinecone.

    Returns:
        List of SearchResult sorted by score
    """
    index = get_pinecone_index()

    query_params = {
        "vector": query_embedding,
        "top_k": top_k,
        "include_metadata": True
    }

    if filter_metadata:
        query_params["filter"] = filter_metadata

    response = index.query(**query_params)

    results = []
    for match in response.matches:
        if match.score >= SIMILARITY_THRESHOLD:
            results.append(SearchResult(
                chunk_id=match.id,
                document_id=match.metadata.get("document_id", ""),
                text=match.metadata.get("text", ""),
                score=match.score,
                metadata=match.metadata
            ))

    return results


# ============================================================================
# Caching
# ============================================================================

def get_cache_key(query: str) -> str:
    """Δημιουργία cache key από το query"""
    normalized = query.lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


def get_cached_response(cache_key: str) -> Optional[Dict]:
    """Αναζήτηση cached response"""
    if not CACHE_ENABLED:
        return None

    try:
        table = dynamodb.Table(CACHE_TABLE)
        response = table.get_item(Key={"cache_key": cache_key})

        if "Item" in response:
            item = response["Item"]
            # Check TTL
            if item.get("expires_at", 0) > time.time():
                return item.get("response")
    except Exception as e:
        print(f"Cache read error: {e}")

    return None


def cache_response(cache_key: str, response: Dict):
    """Αποθήκευση response στο cache"""
    if not CACHE_ENABLED:
        return

    try:
        table = dynamodb.Table(CACHE_TABLE)
        table.put_item(Item={
            "cache_key": cache_key,
            "response": response,
            "expires_at": int(time.time() + CACHE_TTL)
        })
    except Exception as e:
        print(f"Cache write error: {e}")


# ============================================================================
# Cost Calculation
# ============================================================================

def calculate_query_cost(embedding_tokens: int, llm_tokens: int) -> float:
    """
    Υπολογισμός κόστους query.

    Pricing (as of Jan 2026):
    - text-embedding-3-small: $0.02 / 1M tokens
    - gpt-4o-mini: $0.15 / 1M input, $0.60 / 1M output
    """
    embedding_cost = (embedding_tokens / 1_000_000) * 0.02
    llm_cost = (llm_tokens / 1_000_000) * 0.40  # Approximate average
    return round(embedding_cost + llm_cost, 6)


# ============================================================================
# Main RAG Pipeline
# ============================================================================

def process_query(
    query: str,
    filter_metadata: Dict = None,
    history: List[Dict] = None
) -> Tuple[Dict, QueryMetrics]:
    """
    Πλήρες RAG pipeline:
    1. Check cache
    2. Create query embedding
    3. Semantic search
    4. Build context
    5. Generate response
    6. Cache result

    Returns:
        Tuple of (response dict, metrics)
    """
    start_time = time.time()
    cache_hit = False
    embedding_tokens = 0
    llm_tokens = 0

    # 1. Check cache
    cache_key = get_cache_key(query)
    cached = get_cached_response(cache_key)

    if cached:
        print(f"Cache hit for query: {query[:50]}...")
        return cached, QueryMetrics(
            embedding_ms=0,
            search_ms=0,
            llm_ms=0,
            total_ms=(time.time() - start_time) * 1000,
            tokens_used=0,
            cost_usd=0,
            cache_hit=True
        )

    # 2. Create query embedding
    embed_start = time.time()
    query_embedding = create_query_embedding(query)
    embedding_tokens = len(query.split()) * 1.3  # Approximate
    embed_ms = (time.time() - embed_start) * 1000

    # 3. Semantic search
    search_start = time.time()
    search_results = search_pinecone(
        query_embedding,
        top_k=TOP_K,
        filter_metadata=filter_metadata
    )
    search_ms = (time.time() - search_start) * 1000

    # 4. Build context
    if not search_results:
        context = "Δεν βρέθηκαν σχετικά έγγραφα."
        sources = []
    else:
        context_parts = []
        sources = []
        for i, result in enumerate(search_results, 1):
            source = result.metadata.get("filename", result.document_id)
            context_parts.append(f"[{i}] {result.text}")
            sources.append({
                "document_id": result.document_id,
                "filename": source,
                "score": round(result.score, 3),
                "chunk_id": result.chunk_id
            })
        context = "\n\n".join(context_parts)

    # 5. Generate response
    llm_start = time.time()
    answer, llm_tokens = generate_response(query, context, history)
    llm_ms = (time.time() - llm_start) * 1000

    # Build response
    response = {
        "answer": answer,
        "sources": sources,
        "context_used": len(search_results)
    }

    # 6. Cache result
    cache_response(cache_key, response)

    total_ms = (time.time() - start_time) * 1000

    metrics = QueryMetrics(
        embedding_ms=round(embed_ms, 2),
        search_ms=round(search_ms, 2),
        llm_ms=round(llm_ms, 2),
        total_ms=round(total_ms, 2),
        tokens_used=int(embedding_tokens + llm_tokens),
        cost_usd=calculate_query_cost(int(embedding_tokens), llm_tokens),
        cache_hit=False
    )

    return response, metrics


# ============================================================================
# Lambda Handler
# ============================================================================

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda entry point.

    Expected input:
    {
        "query": "Πόσες μέρες άδεια δικαιούμαι;",
        "filter": {"department": "HR"},  // optional
        "history": [...]  // optional conversation history
    }
    """

    # Parse input
    body = event
    if "body" in event:
        body = event["body"]
        if isinstance(body, str):
            body = json.loads(body)

    query = body.get("query", "").strip()
    filter_metadata = body.get("filter")
    history = body.get("history", [])

    # Validation
    if not query:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing 'query' parameter"})
        }

    if len(query) > 1000:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Query too long (max 1000 chars)"})
        }

    try:
        # Process query
        response, metrics = process_query(query, filter_metadata, history)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "query": query,
                **response,
                "metrics": {
                    "embedding_ms": metrics.embedding_ms,
                    "search_ms": metrics.search_ms,
                    "llm_ms": metrics.llm_ms,
                    "total_ms": metrics.total_ms,
                    "tokens_used": metrics.tokens_used,
                    "cost_usd": metrics.cost_usd,
                    "cache_hit": metrics.cache_hit
                }
            }, ensure_ascii=False)
        }

    except Exception as e:
        print(f"Query error: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }



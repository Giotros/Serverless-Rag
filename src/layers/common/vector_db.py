"""
Vector Database Abstraction Layer
Υποστηρίζει Pinecone και pgvector για σύγκριση.

Serverless RAG Project - MSc Thesis
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import os


@dataclass
class VectorRecord:
    """Εγγραφή vector"""
    id: str
    vector: List[float]
    text: str
    metadata: Dict[str, Any]
    score: Optional[float] = None


class VectorDBInterface(ABC):
    """Abstract interface για vector databases"""

    @abstractmethod
    def upsert(self, records: List[VectorRecord]) -> int:
        """Εισαγωγή/Ενημέρωση vectors"""
        pass

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_metadata: Dict = None
    ) -> List[VectorRecord]:
        """Semantic search"""
        pass

    @abstractmethod
    def delete(self, ids: List[str]) -> int:
        """Διαγραφή vectors βάσει ID"""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Στατιστικά του index"""
        pass


# ============================================================================
# Pinecone Implementation
# ============================================================================

class PineconeDB(VectorDBInterface):
    """Pinecone vector database implementation"""

    def __init__(
        self,
        api_key: str = None,
        index_name: str = None,
        batch_size: int = 100
    ):
        self.api_key = api_key or os.environ.get("PINECONE_API_KEY")
        self.index_name = index_name or os.environ.get("PINECONE_INDEX", "rag-index")
        self.batch_size = batch_size
        self._index = None

    @property
    def index(self):
        """Lazy initialization του Pinecone index"""
        if self._index is None:
            from pinecone import Pinecone
            pc = Pinecone(api_key=self.api_key)
            self._index = pc.Index(self.index_name)
        return self._index

    def upsert(self, records: List[VectorRecord]) -> int:
        """Εισαγωγή vectors στο Pinecone"""
        if not records:
            return 0

        vectors = []
        for r in records:
            vectors.append({
                "id": r.id,
                "values": r.vector,
                "metadata": {
                    "text": r.text[:1000],  # Pinecone metadata limit
                    **r.metadata
                }
            })

        # Batch upsert
        upserted = 0
        for i in range(0, len(vectors), self.batch_size):
            batch = vectors[i:i + self.batch_size]
            self.index.upsert(vectors=batch)
            upserted += len(batch)

        return upserted

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_metadata: Dict = None
    ) -> List[VectorRecord]:
        """Semantic search στο Pinecone"""
        query_params = {
            "vector": query_vector,
            "top_k": top_k,
            "include_metadata": True
        }

        if filter_metadata:
            query_params["filter"] = filter_metadata

        response = self.index.query(**query_params)

        results = []
        for match in response.matches:
            results.append(VectorRecord(
                id=match.id,
                vector=[],  # Δεν επιστρέφουμε vectors για οικονομία
                text=match.metadata.get("text", ""),
                metadata=match.metadata,
                score=match.score
            ))

        return results

    def delete(self, ids: List[str]) -> int:
        """Διαγραφή vectors"""
        if not ids:
            return 0

        self.index.delete(ids=ids)
        return len(ids)

    def get_stats(self) -> Dict[str, Any]:
        """Στατιστικά index"""
        stats = self.index.describe_index_stats()
        return {
            "total_vectors": stats.total_vector_count,
            "dimensions": stats.dimension,
            "namespaces": list(stats.namespaces.keys()) if stats.namespaces else []
        }


# ============================================================================
# pgvector Implementation
# ============================================================================

class PgVectorDB(VectorDBInterface):
    """PostgreSQL + pgvector implementation"""

    def __init__(
        self,
        connection_string: str = None,
        table_name: str = "embeddings",
        dimensions: int = 1536
    ):
        self.connection_string = connection_string or os.environ.get("PGVECTOR_CONNECTION")
        self.table_name = table_name
        self.dimensions = dimensions
        self._conn = None

    @property
    def conn(self):
        """Lazy initialization της σύνδεσης"""
        if self._conn is None:
            import psycopg2
            from pgvector.psycopg2 import register_vector

            self._conn = psycopg2.connect(self.connection_string)
            register_vector(self._conn)
            self._ensure_table()

        return self._conn

    def _ensure_table(self):
        """Δημιουργία table αν δεν υπάρχει"""
        cur = self.conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id TEXT PRIMARY KEY,
                embedding vector({self.dimensions}),
                text TEXT,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS {self.table_name}_embedding_idx
            ON {self.table_name}
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)
        self.conn.commit()
        cur.close()

    def upsert(self, records: List[VectorRecord]) -> int:
        """Εισαγωγή vectors στο pgvector"""
        if not records:
            return 0

        import json
        cur = self.conn.cursor()

        for r in records:
            cur.execute(f"""
                INSERT INTO {self.table_name} (id, embedding, text, metadata)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    text = EXCLUDED.text,
                    metadata = EXCLUDED.metadata
            """, (r.id, r.vector, r.text, json.dumps(r.metadata)))

        self.conn.commit()
        cur.close()

        return len(records)

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_metadata: Dict = None
    ) -> List[VectorRecord]:
        """Semantic search με pgvector"""
        import json
        cur = self.conn.cursor()

        # Build query with optional metadata filter
        where_clause = ""
        params = [query_vector, top_k]

        if filter_metadata:
            conditions = []
            for key, value in filter_metadata.items():
                conditions.append(f"metadata->>'{key}' = %s")
                params.insert(-1, value)
            where_clause = "WHERE " + " AND ".join(conditions)

        cur.execute(f"""
            SELECT id, text, metadata, 1 - (embedding <=> %s) as score
            FROM {self.table_name}
            {where_clause}
            ORDER BY embedding <=> %s
            LIMIT %s
        """, params + [query_vector])

        results = []
        for row in cur.fetchall():
            results.append(VectorRecord(
                id=row[0],
                vector=[],
                text=row[1],
                metadata=row[2] if isinstance(row[2], dict) else json.loads(row[2]),
                score=row[3]
            ))

        cur.close()
        return results

    def delete(self, ids: List[str]) -> int:
        """Διαγραφή vectors"""
        if not ids:
            return 0

        cur = self.conn.cursor()
        placeholders = ",".join(["%s"] * len(ids))
        cur.execute(f"DELETE FROM {self.table_name} WHERE id IN ({placeholders})", ids)
        deleted = cur.rowcount
        self.conn.commit()
        cur.close()

        return deleted

    def get_stats(self) -> Dict[str, Any]:
        """Στατιστικά table"""
        cur = self.conn.cursor()

        cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
        count = cur.fetchone()[0]

        cur.execute(f"""
            SELECT pg_size_pretty(pg_total_relation_size('{self.table_name}'))
        """)
        size = cur.fetchone()[0]

        cur.close()

        return {
            "total_vectors": count,
            "dimensions": self.dimensions,
            "table_size": size
        }

    def __del__(self):
        """Cleanup σύνδεσης"""
        if self._conn:
            self._conn.close()


# ============================================================================
# Factory Function
# ============================================================================

def get_vector_db(db_type: str = None, **kwargs) -> VectorDBInterface:
    """
    Factory για δημιουργία του κατάλληλου vector DB client.

    Args:
        db_type: "pinecone" ή "pgvector"
        **kwargs: Configuration parameters

    Returns:
        VectorDBInterface implementation
    """
    db_type = db_type or os.environ.get("VECTOR_DB_TYPE", "pinecone")

    if db_type.lower() == "pinecone":
        return PineconeDB(**kwargs)
    elif db_type.lower() in ["pgvector", "postgres", "postgresql"]:
        return PgVectorDB(**kwargs)
    else:
        raise ValueError(f"Unknown vector DB type: {db_type}")


# ============================================================================
# Benchmark Utilities
# ============================================================================

def benchmark_operation(db: VectorDBInterface, operation: str,
                        *args, **kwargs) -> Tuple[Any, float]:
    """
    Εκτέλεση operation με μέτρηση χρόνου.

    Returns:
        Tuple of (result, latency_ms)
    """
    import time

    start = time.time()
    result = getattr(db, operation)(*args, **kwargs)
    latency = (time.time() - start) * 1000

    return result, latency



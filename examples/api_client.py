"""
API Client για Serverless RAG
Παράδειγμα χρήσης του RAG API.

Serverless RAG Project - MSc Thesis
"""

import os
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import requests
from dotenv import load_dotenv

# Load environment
load_dotenv()


@dataclass
class RAGResponse:
    """Απάντηση από το RAG API"""
    answer: str
    sources: List[Dict[str, Any]]
    query: str
    metrics: Dict[str, float]
    cache_hit: bool


class RAGClient:
    """
    Client για το Serverless RAG API.

    Παράδειγμα χρήσης:
        client = RAGClient("https://xxx.execute-api.eu-west-1.amazonaws.com/dev")
        response = client.query("Πόσες μέρες άδεια δικαιούμαι;")
        print(response.answer)
    """

    def __init__(
        self,
        api_endpoint: str,
        api_key: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize RAG client.

        Args:
            api_endpoint: Base URL του API (e.g., https://xxx.execute-api.../dev)
            api_key: Optional API key για authentication
            timeout: Request timeout σε seconds
        """
        self.api_endpoint = api_endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        self.session = requests.Session()
        if api_key:
            self.session.headers["x-api-key"] = api_key

    def query(
        self,
        question: str,
        filter_metadata: Optional[Dict] = None,
        top_k: int = 5
    ) -> RAGResponse:
        """
        Υποβολή ερωτήματος στο RAG.

        Args:
            question: Το ερώτημα σε φυσική γλώσσα
            filter_metadata: Optional φίλτρα (e.g., {"department": "HR"})
            top_k: Πόσα chunks να επιστραφούν

        Returns:
            RAGResponse με την απάντηση και τις πηγές
        """
        url = f"{self.api_endpoint}/query"

        payload = {
            "query": question,
            "top_k": top_k
        }

        if filter_metadata:
            payload["filter"] = filter_metadata

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            return RAGResponse(
                answer=data.get("answer", ""),
                sources=data.get("sources", []),
                query=data.get("query", question),
                metrics=data.get("metrics", {}),
                cache_hit=data.get("metrics", {}).get("cache_hit", False)
            )

        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"API request failed: {e}")

    def upload_document(
        self,
        s3_key: str,
        bucket: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Trigger document ingestion.

        Args:
            s3_key: Path του document στο S3
            bucket: Optional bucket name (default: configured bucket)
            metadata: Optional metadata για το document

        Returns:
            Ingestion result
        """
        url = f"{self.api_endpoint}/ingest"

        payload = {
            "key": s3_key
        }

        if bucket:
            payload["bucket"] = bucket
        if metadata:
            payload["metadata"] = metadata

        response = self.session.post(url, json=payload, timeout=60)
        response.raise_for_status()

        return response.json()

    def batch_query(
        self,
        questions: List[str],
        delay: float = 0.5
    ) -> List[RAGResponse]:
        """
        Batch query για πολλαπλές ερωτήσεις.

        Args:
            questions: Λίστα ερωτήσεων
            delay: Delay μεταξύ requests (rate limiting)

        Returns:
            Λίστα με RAGResponse
        """
        responses = []

        for i, question in enumerate(questions):
            print(f"Processing query {i+1}/{len(questions)}: {question[:50]}...")

            response = self.query(question)
            responses.append(response)

            if i < len(questions) - 1:
                time.sleep(delay)

        return responses


# =============================================================================
# CLI Interface
# =============================================================================

def interactive_mode(client: RAGClient):
    """Interactive Q&A mode"""
    print("\n" + "=" * 50)
    print("Serverless RAG - Interactive Mode")
    print("=" * 50)
    print("Γράψε την ερώτησή σου ή 'exit' για έξοδο.\n")

    while True:
        try:
            question = input("Ερώτηση: ").strip()

            if question.lower() in ["exit", "quit", "q"]:
                print("Αντίο!")
                break

            if not question:
                continue

            print("\nΕπεξεργασία...")
            start = time.time()
            response = client.query(question)
            elapsed = (time.time() - start) * 1000

            print(f"\n📝 Απάντηση:\n{response.answer}")

            if response.sources:
                print(f"\n📚 Πηγές ({len(response.sources)}):")
                for i, source in enumerate(response.sources, 1):
                    filename = source.get("filename", source.get("document_id", "Unknown"))
                    score = source.get("score", 0)
                    print(f"   {i}. {filename} (score: {score:.3f})")

            print(f"\n⏱️  Latency: {elapsed:.0f}ms "
                  f"{'(cache hit)' if response.cache_hit else '(cache miss)'}")
            print("-" * 50)

        except KeyboardInterrupt:
            print("\n\nΔιακοπή...")
            break
        except Exception as e:
            print(f"\n❌ Σφάλμα: {e}")


def demo_queries(client: RAGClient):
    """Run demo queries"""
    demo_questions = [
        "Πόσες μέρες κανονικής άδειας δικαιούμαι;",
        "Ποια είναι η πολιτική τηλεργασίας;",
        "Ποιες είναι οι ασφαλιστικές παροχές;",
        "Πότε γίνεται η αξιολόγηση απόδοσης;",
        "Ποια είναι η πολιτική κωδικών πρόσβασης;",
    ]

    print("\n" + "=" * 50)
    print("Serverless RAG - Demo Queries")
    print("=" * 50)

    for question in demo_questions:
        print(f"\n❓ {question}")
        try:
            response = client.query(question)
            print(f"📝 {response.answer[:200]}...")
            print(f"⏱️  Latency: {response.metrics.get('total_ms', 0):.0f}ms")
        except Exception as e:
            print(f"❌ Error: {e}")

        time.sleep(1)


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG API Client")
    parser.add_argument("--endpoint", "-e",
                       default=os.getenv("RAG_API_ENDPOINT", "http://localhost:3000"),
                       help="API endpoint URL")
    parser.add_argument("--api-key", "-k",
                       default=os.getenv("RAG_API_KEY"),
                       help="API key")
    parser.add_argument("--query", "-q",
                       help="Single query to run")
    parser.add_argument("--demo", action="store_true",
                       help="Run demo queries")
    parser.add_argument("--interactive", "-i", action="store_true",
                       help="Interactive mode")

    args = parser.parse_args()

    client = RAGClient(args.endpoint, args.api_key)

    if args.query:
        response = client.query(args.query)
        print(json.dumps({
            "query": response.query,
            "answer": response.answer,
            "sources": response.sources,
            "metrics": response.metrics
        }, ensure_ascii=False, indent=2))

    elif args.demo:
        demo_queries(client)

    elif args.interactive:
        interactive_mode(client)

    else:
        # Default: show help
        parser.print_help()
        print("\n\nΠαράδειγμα χρήσης:")
        print("  python api_client.py -e https://xxx.execute-api.../dev -i")
        print("  python api_client.py -q 'Πόσες μέρες άδεια δικαιούμαι;'")
        print("  python api_client.py --demo")

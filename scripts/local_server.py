#!/usr/bin/env python3
"""
Local Mock Server για Serverless RAG
Επιτρέπει τοπικό testing χωρίς AWS deployment.

Serverless RAG Project - MSc Thesis
"""

import os
import sys
import json
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                          "flask", "flask-cors", "--break-system-packages", "-q"])
    from flask import Flask, request, jsonify
    from flask_cors import CORS

# =============================================================================
# Configuration
# =============================================================================

app = Flask(__name__)
CORS(app)

# Sample document chunks (simulating vector DB)
SAMPLE_CHUNKS = [
    {
        "id": "benefits_001",
        "text": "Η TechCorp Hellas προσφέρει 25 ημέρες κανονικής άδειας για εργαζόμενους με 0-5 έτη προϋπηρεσίας, 26 ημέρες για 6-10 έτη, 27 ημέρες για 11-15 έτη, και 30 ημέρες για 21+ έτη.",
        "metadata": {"source": "benefits_guide.md", "section": "Άδειες"},
        "embedding": None
    },
    {
        "id": "benefits_002",
        "text": "Αναρρωτική άδεια: 15 ημέρες με πλήρεις αποδοχές, επιπλέον 15 ημέρες με μισές αποδοχές. Ιατρική βεβαίωση απαιτείται για απουσία άνω των 3 ημερών.",
        "metadata": {"source": "benefits_guide.md", "section": "Αναρρωτική Άδεια"},
        "embedding": None
    },
    {
        "id": "benefits_003",
        "text": "Γονική άδεια: Μητρότητα 17 εβδομάδες με πλήρεις αποδοχές, Πατρότητα 14 ημέρες με πλήρεις αποδοχές, Γονική ανατροφής 4 μήνες χωρίς αποδοχές έως 8 ετών τέκνου.",
        "metadata": {"source": "benefits_guide.md", "section": "Γονική Άδεια"},
        "embedding": None
    },
    {
        "id": "benefits_004",
        "text": "Υγειονομική κάλυψη περιλαμβάνει νοσηλεία έως €50.000, χειρουργεία έως €30.000, διαγνωστικά έως €5.000, φάρμακα έως €3.000 ετησίως. Πάροχος: Interamerican Group Health.",
        "metadata": {"source": "benefits_guide.md", "section": "Υγειονομική Κάλυψη"},
        "embedding": None
    },
    {
        "id": "security_001",
        "text": "Κωδικοί πρόσβασης: Ελάχιστο 12 χαρακτήρες, τουλάχιστον 1 κεφαλαίο, 1 πεζό, 1 αριθμός, 1 ειδικός χαρακτήρας. Αλλαγή κάθε 90 ημέρες. Απαγορεύεται η κοινοποίηση σε τρίτους.",
        "metadata": {"source": "it_security_policy.md", "section": "Κωδικοί"},
        "embedding": None
    },
    {
        "id": "security_002",
        "text": "MFA είναι υποχρεωτικό για email, VPN, cloud εφαρμογές (AWS, GCP, Azure), HR systems, και financial systems. Εγκεκριμένες μέθοδοι: Microsoft Authenticator, Google Authenticator, Hardware tokens.",
        "metadata": {"source": "it_security_policy.md", "section": "MFA"},
        "embedding": None
    },
    {
        "id": "security_003",
        "text": "Σε περίπτωση απώλειας/κλοπής συσκευής: 1) Αναφορά στο IT Help Desk εντός 1 ώρας, 2) Remote wipe, 3) Αλλαγή όλων των κωδικών, 4) Αναφορά στην ασφάλεια αν περιέχει ευαίσθητα δεδομένα.",
        "metadata": {"source": "it_security_policy.md", "section": "Απώλεια Συσκευής"},
        "embedding": None
    },
    {
        "id": "policy_001",
        "text": "Τηλεργασία: Επιτρέπεται έως 3 ημέρες/εβδομάδα με έγκριση manager. Απαιτείται σταθερή σύνδεση internet, χρήση VPN, και διαθεσιμότητα κατά τις ώρες εργασίας.",
        "metadata": {"source": "company_policy.md", "section": "Τηλεργασία"},
        "embedding": None
    },
    {
        "id": "policy_002",
        "text": "Αξιολόγηση απόδοσης: Διενεργείται δύο φορές ετησίως (Ιούνιος και Δεκέμβριος). Περιλαμβάνει αυτοαξιολόγηση, αξιολόγηση από manager, και συζήτηση στόχων.",
        "metadata": {"source": "company_policy.md", "section": "Αξιολόγηση"},
        "embedding": None
    },
    {
        "id": "benefits_005",
        "text": "Ticket Restaurant αξίας €8/ημέρα εργασίας με κάρτα Sodexo, αποδεκτά σε 30.000+ σημεία. Επιδότηση μετακίνησης €100/μήνα για ΜΜΜ ή parking.",
        "metadata": {"source": "benefits_guide.md", "section": "Οικονομικές Παροχές"},
        "embedding": None
    },
]

# Simple keyword-based search (simulating vector similarity)
def simple_search(query: str, top_k: int = 5) -> List[Dict]:
    """Simple keyword search to simulate vector similarity"""
    query_words = set(query.lower().split())

    scored_chunks = []
    for chunk in SAMPLE_CHUNKS:
        chunk_words = set(chunk["text"].lower().split())
        # Simple Jaccard-like similarity
        intersection = len(query_words & chunk_words)
        union = len(query_words | chunk_words)
        score = intersection / union if union > 0 else 0

        # Boost exact phrase matches
        if any(word in chunk["text"].lower() for word in query_words if len(word) > 3):
            score += 0.2

        scored_chunks.append((chunk, score))

    # Sort by score and return top_k
    scored_chunks.sort(key=lambda x: x[1], reverse=True)
    return [
        {
            "text": chunk["text"],
            "score": score,
            "metadata": chunk["metadata"]
        }
        for chunk, score in scored_chunks[:top_k]
        if score > 0
    ]

def generate_answer(query: str, contexts: List[Dict]) -> str:
    """Generate a mock answer based on retrieved contexts"""
    if not contexts:
        return "Δεν βρέθηκαν σχετικές πληροφορίες στη βάση γνώσης."

    # Build context string
    context_text = "\n".join([c["text"] for c in contexts[:3]])

    # Simple rule-based response (simulating LLM)
    query_lower = query.lower()

    if "άδεια" in query_lower or "άδειες" in query_lower:
        if "αναρρωτική" in query_lower:
            return "Σύμφωνα με την πολιτική της εταιρείας, δικαιούστε 15 ημέρες αναρρωτικής άδειας με πλήρεις αποδοχές, και επιπλέον 15 ημέρες με μισές αποδοχές. Για απουσία άνω των 3 ημερών απαιτείται ιατρική βεβαίωση."
        elif "γονική" in query_lower or "μητρότητα" in query_lower:
            return "Η εταιρεία προσφέρει: Άδεια μητρότητας 17 εβδομάδες με πλήρεις αποδοχές, άδεια πατρότητας 14 ημέρες με πλήρεις αποδοχές, και γονική άδεια ανατροφής 4 μηνών (χωρίς αποδοχές) για παιδιά έως 8 ετών."
        else:
            return "Η κανονική άδεια εξαρτάται από τα έτη προϋπηρεσίας: 25 ημέρες για 0-5 έτη, 26 ημέρες για 6-10 έτη, 27 ημέρες για 11-15 έτη, 28 ημέρες για 16-20 έτη, και 30 ημέρες για 21+ έτη."

    elif "κωδικ" in query_lower or "password" in query_lower:
        return "Η πολιτική κωδικών απαιτεί: ελάχιστο 12 χαρακτήρες, τουλάχιστον 1 κεφαλαίο, 1 πεζό, 1 αριθμός, και 1 ειδικός χαρακτήρας. Οι κωδικοί πρέπει να αλλάζουν κάθε 90 ημέρες και απαγορεύεται η κοινοποίησή τους."

    elif "mfa" in query_lower or "authentication" in query_lower:
        return "Το MFA (Multi-Factor Authentication) είναι υποχρεωτικό για: email, VPN, cloud εφαρμογές (AWS, GCP, Azure), HR systems, και financial systems. Εγκεκριμένες μέθοδοι: Microsoft Authenticator (προτιμώμενο), Google Authenticator, και Hardware tokens."

    elif "τηλεργασία" in query_lower or "remote" in query_lower:
        return "Η τηλεργασία επιτρέπεται έως 3 ημέρες την εβδομάδα με έγκριση του manager. Απαιτείται σταθερή σύνδεση internet, χρήση VPN για πρόσβαση σε εταιρικά συστήματα, και διαθεσιμότητα κατά τις κανονικές ώρες εργασίας."

    elif "αξιολόγηση" in query_lower or "απόδοση" in query_lower:
        return "Η αξιολόγηση απόδοσης διενεργείται δύο φορές ετησίως (Ιούνιος και Δεκέμβριος). Η διαδικασία περιλαμβάνει αυτοαξιολόγηση του εργαζομένου, αξιολόγηση από τον manager, και συζήτηση για τους στόχους της επόμενης περιόδου."

    elif "ασφάλι" in query_lower or "υγεί" in query_lower or "insurance" in query_lower:
        return "Η υγειονομική κάλυψη περιλαμβάνει: νοσηλεία έως €50.000, χειρουργεία έως €30.000, διαγνωστικά έως €5.000, και φάρμακα (80% κάλυψη) έως €3.000 ετησίως. Πάροχος είναι η Interamerican Group Health. Δυνατότητα επέκτασης για σύζυγο (+€80/μήνα) και παιδιά (+€40/μήνα)."

    elif "ticket" in query_lower or "σίτιση" in query_lower or "φαγητό" in query_lower:
        return "Η εταιρεία παρέχει Ticket Restaurant αξίας €8 ανά ημέρα εργασίας μέσω κάρτας Sodexo, η οποία γίνεται αποδεκτή σε περισσότερα από 30.000 σημεία πανελλαδικά."

    else:
        # Generic response using first context
        return f"Με βάση τις διαθέσιμες πληροφορίες: {contexts[0]['text']}"

# =============================================================================
# API Routes
# =============================================================================

@app.route("/", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Serverless RAG (Local Mock)",
        "version": "1.0.0",
        "mode": "development"
    })

@app.route("/query", methods=["POST"])
def query():
    """RAG Query endpoint"""
    start_time = time.time()

    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"error": "Missing 'query' field"}), 400

    query_text = data["query"]
    top_k = data.get("top_k", 5)

    # Simulate processing time
    time.sleep(0.1)

    # Search for relevant chunks
    search_start = time.time()
    results = simple_search(query_text, top_k)
    search_time = (time.time() - search_start) * 1000

    # Generate answer
    llm_start = time.time()
    answer = generate_answer(query_text, results)
    llm_time = (time.time() - llm_start) * 1000

    total_time = (time.time() - start_time) * 1000

    # Check for "cache hit" simulation (same query hash)
    query_hash = hashlib.md5(query_text.encode()).hexdigest()[:8]
    cache_hit = hasattr(app, '_last_query') and app._last_query == query_hash
    app._last_query = query_hash

    return jsonify({
        "query": query_text,
        "answer": answer,
        "sources": [
            {
                "filename": r["metadata"]["source"],
                "section": r["metadata"]["section"],
                "score": round(r["score"], 3),
                "text": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"]
            }
            for r in results
        ],
        "metrics": {
            "total_ms": round(total_time, 1),
            "search_ms": round(search_time, 1),
            "llm_ms": round(llm_time, 1),
            "cache_hit": cache_hit
        }
    })

@app.route("/ingest", methods=["POST"])
def ingest():
    """Mock ingestion endpoint"""
    data = request.get_json()
    if not data or "key" not in data:
        return jsonify({"error": "Missing 'key' field"}), 400

    # Simulate ingestion
    time.sleep(0.2)

    return jsonify({
        "status": "success",
        "message": f"Document '{data['key']}' queued for processing (mock)",
        "document_id": hashlib.md5(data["key"].encode()).hexdigest()[:12],
        "chunks_created": 5  # Mock value
    })

@app.route("/documents", methods=["GET"])
def list_documents():
    """List indexed documents"""
    unique_sources = set(chunk["metadata"]["source"] for chunk in SAMPLE_CHUNKS)
    return jsonify({
        "documents": [
            {"name": source, "chunks": sum(1 for c in SAMPLE_CHUNKS if c["metadata"]["source"] == source)}
            for source in unique_sources
        ],
        "total_chunks": len(SAMPLE_CHUNKS)
    })

# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Local RAG Mock Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", "-p", type=int, default=3000, help="Port to listen on")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    print("\n" + "=" * 50)
    print("🚀 Serverless RAG - Local Mock Server")
    print("=" * 50)
    print(f"\n📍 Server: http://{args.host}:{args.port}")
    print(f"📚 Indexed: {len(SAMPLE_CHUNKS)} chunks from {len(set(c['metadata']['source'] for c in SAMPLE_CHUNKS))} documents")
    print("\n📋 Endpoints:")
    print(f"   GET  /           - Health check")
    print(f"   POST /query      - RAG query")
    print(f"   POST /ingest     - Document ingestion (mock)")
    print(f"   GET  /documents  - List indexed documents")
    print("\n💡 Test with:")
    print(f"   python examples/api_client.py -e http://localhost:{args.port} -i")
    print("\n" + "-" * 50)
    print("Press Ctrl+C to stop\n")

    app.run(host=args.host, port=args.port, debug=args.debug)

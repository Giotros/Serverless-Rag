"""
Latency Benchmark Tool για Serverless RAG
Μετράει P50, P95, P99 latency για διάφορα components.

Serverless RAG Project - MSc Thesis
"""

import time
import json
import statistics
import random
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

# Simulated latencies based on real-world measurements
# (για actual benchmarks θα χρειαστούν real API calls)


@dataclass
class LatencyResult:
    """Αποτέλεσμα μέτρησης latency"""
    operation: str
    samples: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    std_dev_ms: float
    min_ms: float
    max_ms: float


@dataclass
class BenchmarkConfig:
    """Configuration για benchmark"""
    num_samples: int = 100
    warmup_samples: int = 10
    concurrency: int = 1
    query_lengths: List[int] = None  # [short, medium, long]
    document_sizes: List[int] = None  # KB

    def __post_init__(self):
        if self.query_lengths is None:
            self.query_lengths = [20, 50, 100]  # words
        if self.document_sizes is None:
            self.document_sizes = [10, 100, 500]  # KB


# =============================================================================
# Simulated Components (for demo - replace with actual API calls)
# =============================================================================

def simulate_embedding_latency(text_length: int) -> float:
    """
    Simulate OpenAI embedding API latency.
    Real-world: ~50-150ms depending on text length and load.
    """
    base = 50  # ms
    length_factor = text_length * 0.5
    noise = random.gauss(0, 15)
    return max(20, base + length_factor + noise)


def simulate_pinecone_search(top_k: int = 5) -> float:
    """
    Simulate Pinecone vector search latency.
    Real-world: ~30-80ms for top-k=5.
    """
    base = 35
    k_factor = top_k * 2
    noise = random.gauss(0, 10)
    return max(15, base + k_factor + noise)


def simulate_pgvector_search(top_k: int = 5, with_cold_start: bool = False) -> float:
    """
    Simulate pgvector (Aurora) search latency.
    Real-world: ~60-150ms warm, 5-8s cold start.
    """
    if with_cold_start:
        return random.uniform(5000, 8000)

    base = 70
    k_factor = top_k * 3
    noise = random.gauss(0, 25)
    return max(30, base + k_factor + noise)


def simulate_llm_latency(input_tokens: int, output_tokens: int) -> float:
    """
    Simulate LLM (GPT-4o-mini) latency.
    Real-world: ~500-2000ms depending on tokens.
    """
    base = 400
    input_factor = input_tokens * 0.3
    output_factor = output_tokens * 2
    noise = random.gauss(0, 100)
    return max(200, base + input_factor + output_factor + noise)


def simulate_lambda_cold_start() -> float:
    """
    Simulate Lambda cold start latency.
    Real-world: ~500-3000ms depending on package size.
    """
    return random.uniform(500, 2500)


def simulate_dynamodb_read() -> float:
    """
    Simulate DynamoDB read latency.
    Real-world: ~5-20ms for single item.
    """
    base = 8
    noise = random.gauss(0, 3)
    return max(2, base + noise)


def simulate_s3_download(size_kb: int) -> float:
    """
    Simulate S3 download latency.
    Real-world: ~50-200ms for small files.
    """
    base = 40
    size_factor = size_kb * 0.1
    noise = random.gauss(0, 20)
    return max(20, base + size_factor + noise)


# =============================================================================
# Benchmark Functions
# =============================================================================

def run_latency_samples(
    func: Callable[[], float],
    num_samples: int,
    warmup: int = 10
) -> List[float]:
    """Run multiple samples and return latencies"""
    # Warmup
    for _ in range(warmup):
        func()

    # Actual samples
    latencies = []
    for _ in range(num_samples):
        latencies.append(func())

    return latencies


def calculate_percentiles(latencies: List[float]) -> LatencyResult:
    """Calculate percentile statistics"""
    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)

    return LatencyResult(
        operation="",  # Will be set by caller
        samples=n,
        p50_ms=round(sorted_latencies[int(n * 0.50)], 2),
        p95_ms=round(sorted_latencies[int(n * 0.95)], 2),
        p99_ms=round(sorted_latencies[int(n * 0.99)], 2),
        mean_ms=round(statistics.mean(latencies), 2),
        std_dev_ms=round(statistics.stdev(latencies) if n > 1 else 0, 2),
        min_ms=round(min(latencies), 2),
        max_ms=round(max(latencies), 2)
    )


def benchmark_embedding(config: BenchmarkConfig) -> LatencyResult:
    """Benchmark embedding generation"""
    latencies = run_latency_samples(
        lambda: simulate_embedding_latency(random.choice(config.query_lengths)),
        config.num_samples,
        config.warmup_samples
    )
    result = calculate_percentiles(latencies)
    result.operation = "Embedding (OpenAI)"
    return result


def benchmark_pinecone(config: BenchmarkConfig) -> LatencyResult:
    """Benchmark Pinecone vector search"""
    latencies = run_latency_samples(
        lambda: simulate_pinecone_search(top_k=5),
        config.num_samples,
        config.warmup_samples
    )
    result = calculate_percentiles(latencies)
    result.operation = "Vector Search (Pinecone)"
    return result


def benchmark_pgvector(config: BenchmarkConfig) -> LatencyResult:
    """Benchmark pgvector search"""
    latencies = run_latency_samples(
        lambda: simulate_pgvector_search(top_k=5),
        config.num_samples,
        config.warmup_samples
    )
    result = calculate_percentiles(latencies)
    result.operation = "Vector Search (pgvector)"
    return result


def benchmark_llm(config: BenchmarkConfig) -> LatencyResult:
    """Benchmark LLM response generation"""
    latencies = run_latency_samples(
        lambda: simulate_llm_latency(
            input_tokens=random.randint(500, 1500),
            output_tokens=random.randint(100, 300)
        ),
        config.num_samples,
        config.warmup_samples
    )
    result = calculate_percentiles(latencies)
    result.operation = "LLM Response (GPT-4o-mini)"
    return result


def benchmark_dynamodb(config: BenchmarkConfig) -> LatencyResult:
    """Benchmark DynamoDB cache read"""
    latencies = run_latency_samples(
        simulate_dynamodb_read,
        config.num_samples,
        config.warmup_samples
    )
    result = calculate_percentiles(latencies)
    result.operation = "Cache Read (DynamoDB)"
    return result


def benchmark_full_rag_pipeline(config: BenchmarkConfig) -> LatencyResult:
    """Benchmark full RAG pipeline (cache miss)"""

    def full_pipeline():
        # 1. Cache check
        cache_latency = simulate_dynamodb_read()

        # 2. Query embedding
        embed_latency = simulate_embedding_latency(50)

        # 3. Vector search
        search_latency = simulate_pinecone_search(5)

        # 4. LLM response
        llm_latency = simulate_llm_latency(800, 200)

        return cache_latency + embed_latency + search_latency + llm_latency

    latencies = run_latency_samples(
        full_pipeline,
        config.num_samples,
        config.warmup_samples
    )
    result = calculate_percentiles(latencies)
    result.operation = "Full RAG Pipeline (Pinecone)"
    return result


def benchmark_full_rag_pgvector(config: BenchmarkConfig) -> LatencyResult:
    """Benchmark full RAG pipeline with pgvector"""

    def full_pipeline():
        cache_latency = simulate_dynamodb_read()
        embed_latency = simulate_embedding_latency(50)
        search_latency = simulate_pgvector_search(5)
        llm_latency = simulate_llm_latency(800, 200)
        return cache_latency + embed_latency + search_latency + llm_latency

    latencies = run_latency_samples(
        full_pipeline,
        config.num_samples,
        config.warmup_samples
    )
    result = calculate_percentiles(latencies)
    result.operation = "Full RAG Pipeline (pgvector)"
    return result


# =============================================================================
# Concurrent Benchmark
# =============================================================================

def benchmark_concurrent_queries(
    config: BenchmarkConfig,
    concurrency: int = 10
) -> Dict[str, Any]:
    """Benchmark concurrent query handling"""

    def single_query():
        start = time.time()
        # Simulate full RAG pipeline
        simulate_dynamodb_read()
        simulate_embedding_latency(50)
        simulate_pinecone_search(5)
        simulate_llm_latency(800, 200)
        return (time.time() - start) * 1000

    results = []
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(single_query) for _ in range(config.num_samples)]

        for future in as_completed(futures):
            results.append(future.result())

    total_time = time.time() - start_time
    throughput = config.num_samples / total_time

    latency_result = calculate_percentiles(results)

    return {
        "concurrency": concurrency,
        "total_queries": config.num_samples,
        "total_time_sec": round(total_time, 2),
        "throughput_qps": round(throughput, 2),
        "latency": asdict(latency_result)
    }


# =============================================================================
# Reporting
# =============================================================================

def generate_latency_report(config: BenchmarkConfig = None) -> str:
    """Generate comprehensive latency report"""

    if config is None:
        config = BenchmarkConfig(num_samples=100)

    lines = []
    lines.append("=" * 70)
    lines.append("LATENCY BENCHMARK REPORT - SERVERLESS RAG")
    lines.append("=" * 70)
    lines.append(f"Samples per test: {config.num_samples}")
    lines.append(f"Warmup samples: {config.warmup_samples}")
    lines.append("")

    # Individual component benchmarks
    benchmarks = [
        ("Embedding", benchmark_embedding),
        ("Pinecone Search", benchmark_pinecone),
        ("pgvector Search", benchmark_pgvector),
        ("LLM Response", benchmark_llm),
        ("DynamoDB Cache", benchmark_dynamodb),
        ("Full RAG (Pinecone)", benchmark_full_rag_pipeline),
        ("Full RAG (pgvector)", benchmark_full_rag_pgvector),
    ]

    results = []
    for name, func in benchmarks:
        print(f"Running {name} benchmark...")
        result = func(config)
        results.append(result)

    # Format table
    lines.append("-" * 70)
    lines.append(f"{'Operation':<30} {'P50':>8} {'P95':>8} {'P99':>8} {'Mean':>8}")
    lines.append("-" * 70)

    for r in results:
        lines.append(f"{r.operation:<30} {r.p50_ms:>7.1f}ms {r.p95_ms:>7.1f}ms {r.p99_ms:>7.1f}ms {r.mean_ms:>7.1f}ms")

    lines.append("-" * 70)

    # Summary
    lines.append("")
    lines.append("SUMMARY - Pinecone vs pgvector")
    lines.append("-" * 70)

    pinecone_p50 = results[5].p50_ms  # Full RAG Pinecone
    pgvector_p50 = results[6].p50_ms  # Full RAG pgvector
    diff_ms = pgvector_p50 - pinecone_p50
    diff_pct = (diff_ms / pinecone_p50) * 100

    lines.append(f"Pinecone P50: {pinecone_p50:.1f}ms")
    lines.append(f"pgvector P50: {pgvector_p50:.1f}ms")
    lines.append(f"Difference: +{diff_ms:.1f}ms ({diff_pct:.1f}% slower)")
    lines.append("")
    lines.append("Note: pgvector has additional 5-8s cold start penalty")

    # Concurrent test
    lines.append("")
    lines.append("=" * 70)
    lines.append("CONCURRENT QUERY BENCHMARK")
    lines.append("=" * 70)

    for concurrency in [1, 5, 10, 20]:
        print(f"Running concurrent benchmark (concurrency={concurrency})...")
        concurrent_result = benchmark_concurrent_queries(
            BenchmarkConfig(num_samples=50),
            concurrency=concurrency
        )
        lines.append(f"Concurrency {concurrency:>2}: "
                    f"Throughput={concurrent_result['throughput_qps']:.1f} QPS, "
                    f"P99={concurrent_result['latency']['p99_ms']:.1f}ms")

    return "\n".join(lines)


def generate_json_report(config: BenchmarkConfig = None) -> Dict:
    """Generate JSON report for visualization"""

    if config is None:
        config = BenchmarkConfig(num_samples=50)

    results = {
        "config": asdict(config),
        "components": {},
        "comparison": {},
        "concurrent": []
    }

    # Component benchmarks
    benchmarks = [
        ("embedding", benchmark_embedding),
        ("pinecone_search", benchmark_pinecone),
        ("pgvector_search", benchmark_pgvector),
        ("llm_response", benchmark_llm),
        ("dynamodb_cache", benchmark_dynamodb),
        ("full_rag_pinecone", benchmark_full_rag_pipeline),
        ("full_rag_pgvector", benchmark_full_rag_pgvector),
    ]

    for key, func in benchmarks:
        result = func(config)
        results["components"][key] = asdict(result)

    # Comparison
    results["comparison"] = {
        "pinecone_vs_pgvector": {
            "p50_diff_ms": results["components"]["full_rag_pgvector"]["p50_ms"] -
                          results["components"]["full_rag_pinecone"]["p50_ms"],
            "p99_diff_ms": results["components"]["full_rag_pgvector"]["p99_ms"] -
                          results["components"]["full_rag_pinecone"]["p99_ms"],
            "recommendation": "pinecone" if results["components"]["full_rag_pinecone"]["p50_ms"] <
                                           results["components"]["full_rag_pgvector"]["p50_ms"] else "pgvector"
        }
    }

    # Concurrent tests
    for concurrency in [1, 5, 10]:
        concurrent_result = benchmark_concurrent_queries(
            BenchmarkConfig(num_samples=30),
            concurrency=concurrency
        )
        results["concurrent"].append(concurrent_result)

    return results


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("Starting latency benchmarks...\n")

    # Text report
    report = generate_latency_report(BenchmarkConfig(num_samples=50))
    print("\n" + report)

    # Save JSON report
    json_report = generate_json_report(BenchmarkConfig(num_samples=30))

    output_path = os.path.join(os.path.dirname(__file__), "../results/latency_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(json_report, f, indent=2)

    print(f"\nJSON report saved to: {output_path}")

"""
Cost Analysis Tool για Serverless RAG
Σύγκριση TCO μεταξύ serverless και dedicated architectures.

Serverless RAG Project - MSc Thesis
"""

from dataclasses import dataclass
from typing import Dict, List
from enum import Enum


class WorkloadType(Enum):
    """Προκαθορισμένα προφίλ φόρτου εργασίας"""
    STARTUP = "startup"
    GROWING = "growing"
    ENTERPRISE = "enterprise"


@dataclass
class Workload:
    """Παράμετροι φόρτου εργασίας"""
    name: str
    queries_per_day: int
    documents: int
    storage_gb: float
    peak_qps: int


@dataclass
class CostBreakdown:
    """Ανάλυση κόστους"""
    compute: float
    storage: float
    vector_db: float
    networking: float
    embeddings: float
    llm: float

    @property
    def total(self) -> float:
        return (self.compute + self.storage + self.vector_db +
                self.networking + self.embeddings + self.llm)


# =============================================================================
# Τιμολόγηση (Ιανουάριος 2026)
# =============================================================================

PRICING = {
    "aws": {
        "lambda": {
            "requests_per_million": 0.20,
            "duration_per_gb_sec": 0.0000166667,
            "free_requests": 1_000_000,
            "free_gb_seconds": 400_000
        },
        "api_gateway": {
            "requests_per_million": 1.00,
            "free_requests": 1_000_000
        },
        "dynamodb": {
            "write_per_million": 1.25,
            "read_per_million": 0.25,
            "storage_per_gb": 0.25,
            "free_storage_gb": 25
        },
        "s3": {
            "storage_per_gb": 0.023,
            "requests_per_thousand": 0.0004,
            "free_storage_gb": 5
        },
        "ec2_t3_medium": {
            "hourly": 0.0416,
            "monthly": 30.37
        },
        "ec2_m5_large": {
            "hourly": 0.096,
            "monthly": 70.08
        },
        "aurora_serverless_v2": {
            "acu_per_hour": 0.12,
            "storage_per_gb": 0.10
        }
    },
    "pinecone": {
        "serverless": {
            "storage_per_gb": 0.33,
            "free_vectors": 100_000
        }
    },
    "openai": {
        "embedding_3_small": {
            "per_million_tokens": 0.02
        },
        "gpt_4o_mini": {
            "input_per_million": 0.15,
            "output_per_million": 0.60
        }
    }
}

WORKLOADS = {
    WorkloadType.STARTUP: Workload(
        name="Startup",
        queries_per_day=500,
        documents=5_000,
        storage_gb=1,
        peak_qps=5
    ),
    WorkloadType.GROWING: Workload(
        name="Growing",
        queries_per_day=5_000,
        documents=50_000,
        storage_gb=10,
        peak_qps=20
    ),
    WorkloadType.ENTERPRISE: Workload(
        name="Enterprise",
        queries_per_day=50_000,
        documents=500_000,
        storage_gb=100,
        peak_qps=100
    )
}


# =============================================================================
# Υπολογισμοί Κόστους
# =============================================================================

def calculate_serverless_cost(workload: Workload) -> CostBreakdown:
    """Υπολογισμός μηνιαίου κόστους για serverless architecture"""

    monthly_queries = workload.queries_per_day * 30

    # Lambda costs
    lambda_invocations = monthly_queries * 3  # 3 functions per query
    lambda_duration = lambda_invocations * 0.5 * 0.3  # 0.5GB, 300ms avg

    lambda_req_cost = max(0, (lambda_invocations - PRICING["aws"]["lambda"]["free_requests"])) \
                      * PRICING["aws"]["lambda"]["requests_per_million"] / 1_000_000
    lambda_dur_cost = max(0, (lambda_duration - PRICING["aws"]["lambda"]["free_gb_seconds"])) \
                      * PRICING["aws"]["lambda"]["duration_per_gb_sec"]
    compute_cost = lambda_req_cost + lambda_dur_cost

    # API Gateway
    api_cost = max(0, (monthly_queries - PRICING["aws"]["api_gateway"]["free_requests"])) \
               * PRICING["aws"]["api_gateway"]["requests_per_million"] / 1_000_000

    # DynamoDB
    ddb_storage = min(workload.storage_gb * 0.1, 25)
    ddb_cost = max(0, ddb_storage - PRICING["aws"]["dynamodb"]["free_storage_gb"]) \
               * PRICING["aws"]["dynamodb"]["storage_per_gb"]

    # S3
    s3_cost = max(0, workload.storage_gb - PRICING["aws"]["s3"]["free_storage_gb"]) \
              * PRICING["aws"]["s3"]["storage_per_gb"]

    storage_cost = ddb_cost + s3_cost

    # Pinecone (free tier: 100K vectors)
    vectors = workload.documents * 10  # ~10 chunks per doc
    if vectors <= PRICING["pinecone"]["serverless"]["free_vectors"]:
        vector_db_cost = 0
    else:
        storage_gb = (vectors * 1536 * 4) / (1024**3)
        vector_db_cost = storage_gb * PRICING["pinecone"]["serverless"]["storage_per_gb"]

    # Embeddings (OpenAI)
    embed_tokens = monthly_queries * 50  # avg query tokens
    embed_cost = embed_tokens * PRICING["openai"]["embedding_3_small"]["per_million_tokens"] / 1_000_000

    # LLM (GPT-4o-mini)
    input_tokens = monthly_queries * 550  # query + context
    output_tokens = monthly_queries * 150
    llm_cost = (
        input_tokens * PRICING["openai"]["gpt_4o_mini"]["input_per_million"] / 1_000_000 +
        output_tokens * PRICING["openai"]["gpt_4o_mini"]["output_per_million"] / 1_000_000
    )

    return CostBreakdown(
        compute=round(compute_cost, 2),
        storage=round(storage_cost, 2),
        vector_db=round(vector_db_cost, 2),
        networking=round(api_cost, 2),
        embeddings=round(embed_cost, 2),
        llm=round(llm_cost, 2)
    )


def calculate_dedicated_cost(workload: Workload) -> CostBreakdown:
    """Υπολογισμός μηνιαίου κόστους για dedicated architecture"""

    monthly_queries = workload.queries_per_day * 30

    # EC2 compute
    if workload.peak_qps <= 20:
        compute_cost = PRICING["aws"]["ec2_t3_medium"]["monthly"]
    else:
        instances = max(1, workload.peak_qps // 50)
        compute_cost = PRICING["aws"]["ec2_m5_large"]["monthly"] * instances

    # Aurora pgvector
    avg_acu = max(0.5, workload.peak_qps / 100)
    aurora_compute = avg_acu * PRICING["aws"]["aurora_serverless_v2"]["acu_per_hour"] * 24 * 30
    aurora_storage = workload.storage_gb * 0.5 * PRICING["aws"]["aurora_serverless_v2"]["storage_per_gb"]
    vector_db_cost = aurora_compute + aurora_storage

    # S3 storage
    storage_cost = workload.storage_gb * PRICING["aws"]["s3"]["storage_per_gb"]

    # Networking (ALB + data transfer)
    networking_cost = 20

    # Embeddings & LLM (same as serverless)
    embed_tokens = monthly_queries * 50
    embed_cost = embed_tokens * PRICING["openai"]["embedding_3_small"]["per_million_tokens"] / 1_000_000

    input_tokens = monthly_queries * 550
    output_tokens = monthly_queries * 150
    llm_cost = (
        input_tokens * PRICING["openai"]["gpt_4o_mini"]["input_per_million"] / 1_000_000 +
        output_tokens * PRICING["openai"]["gpt_4o_mini"]["output_per_million"] / 1_000_000
    )

    return CostBreakdown(
        compute=round(compute_cost, 2),
        storage=round(storage_cost, 2),
        vector_db=round(vector_db_cost, 2),
        networking=round(networking_cost, 2),
        embeddings=round(embed_cost, 2),
        llm=round(llm_cost, 2)
    )


def calculate_break_even(workload: Workload) -> int:
    """Υπολογισμός break-even point σε queries/day"""

    serverless = calculate_serverless_cost(workload)
    dedicated = calculate_dedicated_cost(workload)

    # Fixed costs για dedicated
    dedicated_fixed = dedicated.compute + dedicated.networking

    # Variable cost per query
    monthly_queries = workload.queries_per_day * 30
    serverless_per_query = serverless.total / monthly_queries if monthly_queries > 0 else 0
    dedicated_var_per_query = (dedicated.embeddings + dedicated.llm) / monthly_queries if monthly_queries > 0 else 0

    cost_diff = serverless_per_query - dedicated_var_per_query

    if cost_diff > 0:
        break_even_monthly = dedicated_fixed / cost_diff
        return int(break_even_monthly / 30)

    return 999999


# =============================================================================
# Reporting
# =============================================================================

def generate_report() -> str:
    """Δημιουργία πλήρους αναφοράς κόστους"""

    lines = []
    lines.append("=" * 70)
    lines.append("ΑΝΑΛΥΣΗ ΚΟΣΤΟΥΣ - SERVERLESS RAG")
    lines.append("=" * 70)

    for wtype, workload in WORKLOADS.items():
        serverless = calculate_serverless_cost(workload)
        dedicated = calculate_dedicated_cost(workload)
        break_even = calculate_break_even(workload)

        lines.append(f"\n## {workload.name}")
        lines.append(f"   Queries/day: {workload.queries_per_day:,}")
        lines.append(f"   Documents: {workload.documents:,}")
        lines.append(f"   Storage: {workload.storage_gb} GB")

        lines.append(f"\n   SERVERLESS:")
        lines.append(f"     Compute:   ${serverless.compute:.2f}")
        lines.append(f"     Storage:   ${serverless.storage:.2f}")
        lines.append(f"     Vector DB: ${serverless.vector_db:.2f}")
        lines.append(f"     Network:   ${serverless.networking:.2f}")
        lines.append(f"     Embed:     ${serverless.embeddings:.2f}")
        lines.append(f"     LLM:       ${serverless.llm:.2f}")
        lines.append(f"     TOTAL:     ${serverless.total:.2f}/μήνα")

        lines.append(f"\n   DEDICATED:")
        lines.append(f"     Compute:   ${dedicated.compute:.2f}")
        lines.append(f"     Storage:   ${dedicated.storage:.2f}")
        lines.append(f"     Vector DB: ${dedicated.vector_db:.2f}")
        lines.append(f"     Network:   ${dedicated.networking:.2f}")
        lines.append(f"     Embed:     ${dedicated.embeddings:.2f}")
        lines.append(f"     LLM:       ${dedicated.llm:.2f}")
        lines.append(f"     TOTAL:     ${dedicated.total:.2f}/μήνα")

        savings = dedicated.total - serverless.total
        savings_pct = (savings / dedicated.total * 100) if dedicated.total > 0 else 0

        if serverless.total < dedicated.total:
            lines.append(f"\n   ✓ SERVERLESS εξοικονομεί ${savings:.2f}/μήνα ({savings_pct:.1f}%)")
        else:
            lines.append(f"\n   ✓ DEDICATED εξοικονομεί ${-savings:.2f}/μήνα ({-savings_pct:.1f}%)")

        lines.append(f"   Break-even: ~{break_even:,} queries/day")

    lines.append("\n" + "=" * 70)
    lines.append("ΣΥΝΟΨΗ")
    lines.append("=" * 70)

    lines.append(f"\n{'Profile':<15} {'Serverless':<15} {'Dedicated':<15} {'Savings':<15} {'Recommendation':<15}")
    lines.append("-" * 70)

    for wtype, workload in WORKLOADS.items():
        serverless = calculate_serverless_cost(workload)
        dedicated = calculate_dedicated_cost(workload)
        break_even = calculate_break_even(workload)
        savings = dedicated.total - serverless.total
        rec = "Serverless" if workload.queries_per_day < break_even else "Dedicated"

        lines.append(f"{workload.name:<15} ${serverless.total:<14.2f} ${dedicated.total:<14.2f} ${savings:<14.2f} {rec:<15}")

    return "\n".join(lines)


def generate_json_report() -> Dict:
    """Δημιουργία JSON αναφοράς για visualization"""

    results = {}

    for wtype, workload in WORKLOADS.items():
        serverless = calculate_serverless_cost(workload)
        dedicated = calculate_dedicated_cost(workload)
        break_even = calculate_break_even(workload)

        results[wtype.value] = {
            "workload": {
                "name": workload.name,
                "queries_per_day": workload.queries_per_day,
                "documents": workload.documents,
                "storage_gb": workload.storage_gb
            },
            "serverless": {
                "compute": serverless.compute,
                "storage": serverless.storage,
                "vector_db": serverless.vector_db,
                "networking": serverless.networking,
                "embeddings": serverless.embeddings,
                "llm": serverless.llm,
                "total": round(serverless.total, 2)
            },
            "dedicated": {
                "compute": dedicated.compute,
                "storage": dedicated.storage,
                "vector_db": dedicated.vector_db,
                "networking": dedicated.networking,
                "embeddings": dedicated.embeddings,
                "llm": dedicated.llm,
                "total": round(dedicated.total, 2)
            },
            "break_even_queries_per_day": break_even,
            "recommendation": "serverless" if workload.queries_per_day < break_even else "dedicated"
        }

    return results


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print(generate_report())

    import json
    print("\n\nJSON Report:")
    print(json.dumps(generate_json_report(), indent=2))

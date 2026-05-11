from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
import json
import re


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INDEX_PATH = PROJECT_ROOT / "knowledge" / "index" / "knowledge_chunks.jsonl"


STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "for", "with", "in",
    "on", "using", "use", "design", "build", "create", "robot", "robotic",
    "system", "systems", "machine", "machines"
}


def tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9_+-]+", text.lower())
    return {token for token in tokens if token not in STOPWORDS and len(token) > 2}


def load_chunks() -> List[Dict]:
    if not INDEX_PATH.exists():
        return []

    chunks = []

    with INDEX_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            try:
                chunks.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return chunks


def retrieve_knowledge(
    query: str,
    selected_domains: Optional[List[str]] = None,
    top_k: int = 8,
    max_per_source: int = 2,
) -> List[Dict]:
    """
    Retrieves relevant OMNI knowledge chunks.

    Current method:
    - keyword overlap
    - optional domain filtering
    - source diversity limit

    Later upgrade:
    - embeddings/vector retrieval
    - citation/provenance ranking
    - domain-specific weighting
    """

    chunks = load_chunks()
    query_tokens = tokenize(query)

    scored_results = []

    for chunk in chunks:
        domain = chunk.get("domain", "")

        if selected_domains and domain not in selected_domains:
            continue

        text = chunk.get("text", "")
        source_file = chunk.get("source_file", "unknown")
        chunk_tokens = tokenize(text)

        overlap_tokens = query_tokens.intersection(chunk_tokens)
        overlap_score = len(overlap_tokens)

        if overlap_score <= 0:
            continue

        # Small bonus if important query terms appear in the source filename.
        filename_tokens = tokenize(source_file)
        filename_bonus = len(query_tokens.intersection(filename_tokens))

        final_score = overlap_score + filename_bonus

        scored_results.append({
            "score": final_score,
            "matched_terms": sorted(list(overlap_tokens)),
            "domain": domain,
            "source_file": source_file,
            "chunk_id": chunk.get("chunk_id", -1),
            "text": text[:1200],
        })

    scored_results.sort(key=lambda item: item["score"], reverse=True)

    diversified = []
    source_counts = defaultdict(int)

    for result in scored_results:
        source = result["source_file"]

        if source_counts[source] >= max_per_source:
            continue

        diversified.append(result)
        source_counts[source] += 1

        if len(diversified) >= top_k:
            break

    return diversified


def build_retrieval_context(
    mission_text: str,
    selected_domains: Optional[List[str]] = None,
    top_k: int = 8,
) -> Dict:
    results = retrieve_knowledge(
        query=mission_text,
        selected_domains=selected_domains,
        top_k=top_k,
    )

    return {
        "mission_text": mission_text,
        "selected_domains": selected_domains or [],
        "retrieved_knowledge": results,
    }

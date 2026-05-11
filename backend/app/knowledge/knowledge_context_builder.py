from typing import Dict

from backend.app.knowledge.domain_router import build_knowledge_context
from backend.app.knowledge.local_knowledge_retriever import retrieve_knowledge


def build_omni_knowledge_context(mission_text: str, top_k: int = 8) -> Dict:
    """
    Builds the complete knowledge context for an OMNI mission.

    This is the bridge between:
    - mission text
    - domain routing
    - local retrieval
    - agent context injection
    """

    routed_context = build_knowledge_context(mission_text)
    selected_domains = routed_context["selected_domains"]

    retrieved_knowledge = retrieve_knowledge(
        query=mission_text,
        selected_domains=selected_domains,
        top_k=top_k,
    )

    return {
        "mission_text": mission_text,
        "selected_domains": selected_domains,
        "domain_summaries": routed_context["domain_summaries"],
        "retrieved_knowledge": retrieved_knowledge,
    }

from backend.app.knowledge.knowledge_context_builder import build_omni_knowledge_context


mission = "Design a futuristic insect-inspired autonomous rover with compliant legs and 3D printable armor panels."

context = build_omni_knowledge_context(mission, top_k=8)

print("\nMISSION:")
print(context["mission_text"])

print("\nSELECTED DOMAINS:")
for domain in context["selected_domains"]:
    print(f"- {domain}: {context['domain_summaries'][domain]}")

print("\nRETRIEVED KNOWLEDGE:")
for i, item in enumerate(context["retrieved_knowledge"], start=1):
    print(f"\n--- KNOWLEDGE HIT {i} ---")
    print(f"Score: {item['score']}")
    print(f"Domain: {item['domain']}")
    print(f"Source: {item['source_file']}")
    print(f"Chunk: {item['chunk_id']}")
    print(f"Matched terms: {', '.join(item.get('matched_terms', []))}")
    print(item["text"][:500])

from backend.app.knowledge.local_knowledge_retriever import retrieve_knowledge


mission = "Design a bio-inspired snake robot for autonomous terrain navigation using compliant body motion."

results = retrieve_knowledge(
    query=mission,
    selected_domains=[
        "bio_inspired_robotics",
        "autonomous_machine_architecture",
        "fabrication_patterns",
    ],
    top_k=5,
)

print("\nMISSION:")
print(mission)

print("\nTOP KNOWLEDGE RESULTS:")
for i, result in enumerate(results, start=1):
    print(f"\n--- RESULT {i} ---")
    print(f"Score: {result['score']}")
    print(f"Domain: {result['domain']}")
    print(f"Source: {result['source_file']}")
    print(f"Chunk: {result['chunk_id']}")
    print(result["text"][:600])

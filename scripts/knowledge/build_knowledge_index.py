from pathlib import Path
import json
import re


PROCESSED_ROOT = Path("knowledge/processed")
INDEX_PATH = Path("knowledge/index/knowledge_chunks.jsonl")

CHUNK_SIZE = 1800
CHUNK_OVERLAP = 250


def normalize(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text(text: str):
    text = normalize(text)

    if not text:
        return

    start = 0
    chunk_id = 0

    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end].strip()

        if chunk:
            yield chunk_id, chunk

        chunk_id += 1
        start = end - CHUNK_OVERLAP


def main() -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

    total_chunks = 0

    with INDEX_PATH.open("w", encoding="utf-8") as index_file:
        for domain_dir in PROCESSED_ROOT.iterdir():
            if not domain_dir.is_dir():
                continue

            domain = domain_dir.name

            for txt_path in domain_dir.rglob("*.txt"):
                text = txt_path.read_text(encoding="utf-8", errors="ignore")

                for chunk_id, chunk in chunk_text(text):
                    record = {
                        "domain": domain,
                        "source_file": txt_path.name,
                        "chunk_id": chunk_id,
                        "text": chunk,
                    }

                    index_file.write(json.dumps(record) + "\n")
                    total_chunks += 1

    print(f"[OK] Built index: {INDEX_PATH}")
    print(f"[OK] Total chunks: {total_chunks}")


if __name__ == "__main__":
    main()

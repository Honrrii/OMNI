from pathlib import Path
from pypdf import PdfReader
import re


RAW_ROOT = Path("knowledge/raw")
PROCESSED_ROOT = Path("knowledge/processed")


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_pdf(pdf_path: Path, output_path: Path) -> None:
    try:
        reader = PdfReader(str(pdf_path))
        pages = []

        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
                text = clean_text(text)

                if text:
                    pages.append(f"\n\n--- PAGE {i + 1} ---\n{text}")

            except Exception as page_error:
                pages.append(f"\n\n--- PAGE {i + 1} EXTRACTION ERROR: {page_error} ---")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(pages), encoding="utf-8")

        print(f"[OK] {pdf_path} -> {output_path}")

    except Exception as error:
        print(f"[ERROR] Could not extract {pdf_path}: {error}")


def main() -> None:
    for domain_dir in RAW_ROOT.iterdir():
        if not domain_dir.is_dir():
            continue

        domain_name = domain_dir.name
        output_domain_dir = PROCESSED_ROOT / domain_name

        # Recursive search because your zip files created nested folders.
        for pdf_path in domain_dir.rglob("*.pdf"):
            relative_name = "__".join(pdf_path.relative_to(domain_dir).parts)
            output_path = output_domain_dir / f"{Path(relative_name).stem}.txt"
            extract_pdf(pdf_path, output_path)


if __name__ == "__main__":
    main()

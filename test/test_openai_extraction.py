import argparse
import base64
import os
from pathlib import Path

import openai
import pymupdf

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5.4"
API_KEY_ENV_VAR = "AZURE_OPENAI_API_KEY"

EXTRACTION_PROMPT = """Extract all visible text from this PDF page.
Preserve headings, reading order, numbers, negative values, currencies, and table
relationships. Represent tables as Markdown tables where possible. Do not
summarize, interpret, or omit text. Return only the extracted Markdown text.
"""


def extract_pdf_page(pdf_path: Path, page_number: int) -> bytes:
    """Return one PDF page as PDF bytes. page_number is one-based."""
    with pymupdf.open(pdf_path) as source_pdf:
        if not 1 <= page_number <= source_pdf.page_count:
            raise ValueError(
                f"Page {page_number} is outside the valid range "
                f"1-{source_pdf.page_count}."
            )

        with pymupdf.open() as single_page_pdf:
            page_index = page_number - 1
            single_page_pdf.insert_pdf(
                source_pdf,
                from_page=page_index,
                to_page=page_index,
            )
            return single_page_pdf.tobytes()


def extract_text_with_azure(pdf_page: bytes) -> str:
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        raise RuntimeError(
            f"Missing {API_KEY_ENV_VAR}. Set it before running this script."
        )

    pdf_base64 = base64.b64encode(pdf_page).decode("ascii")
    client = openai.OpenAI(
        base_url=os.environ.get(DEFAULT_BASE_URL),
        api_key=api_key,
    )
    response = client.responses.create(
        model=os.environ.get("AZURE_OPENAI_MODEL", DEFAULT_MODEL),
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": "page.pdf",
                        "file_data": (
                            "data:application/pdf;base64," + pdf_base64
                        ),
                    },
                    {
                        "type": "input_text",
                        "text": EXTRACTION_PROMPT,
                    },
                ],
            }
        ],
    )
    return response.output_text.strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract one PDF page using Azure OpenAI."
    )
    parser.add_argument("pdf", type=Path, help="Path to the source PDF")
    parser.add_argument(
        "--page",
        type=int,
        required=True,
        help="One-based page number to extract",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional Markdown output file; otherwise print to stdout",
    )
    args = parser.parse_args()

    page_pdf = extract_pdf_page(args.pdf, args.page)
    page_pdf_path = Path.cwd() / f"{args.pdf.stem}_page_{args.page}.pdf"
    page_pdf_path.write_bytes(page_pdf)
    print(f"Saved PDF page {args.page} to {page_pdf_path}")

    extracted_text = extract_text_with_azure(page_pdf)

    if args.output:
        args.output.write_text(extracted_text + "\n", encoding="utf-8")
        print(f"Saved extracted page text to {args.output}")
    else:
        print(extracted_text)


if __name__ == "__main__":
    main()

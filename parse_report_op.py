import base64
import os
import time

import pymupdf
from openai import OpenAI

DEFAULT_BASE_URL = "http://192.168.10.48:12434/v1"
DEFAULT_MODEL = "Qwen/Qwen3.8-27B-FP8"

SYSTEM_PROMPT = """You are given an image of a page from a financial or annual report.

Extract all visible text from the page image.
Preserve headings, reading order, numbers, negative values, currencies, and table
relationships. Represent tables as Markdown tables where possible. Keep bilingual
Chinese/English text as shown on the page. Do not summarize, interpret, or omit text.

Return only the extracted Markdown. Do not wrap the answer in code fences.
"""


def parse_text_with_llm(pix):
    client = OpenAI(api_key="None", base_url=DEFAULT_BASE_URL)
    image_b64 = base64.b64encode(pix.tobytes("png")).decode("ascii")
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Extract this page as Markdown.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}",
                        },
                    },
                ],
            },
        ],
        # extra_body={
        #     "chat_template_kwargs": {"enable_thinking": False},
        # },
    )
    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.removeprefix("```markdown").removeprefix("```md")
        content = content.removeprefix("```").removesuffix("```").strip()
    return content


def parse_report(pdf_dir):
    start_time = time.time()
    images_dir = os.path.join(pdf_dir, "images")
    parsed_dir = os.path.join(pdf_dir, "parsed")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(parsed_dir, exist_ok=True)

    for file in os.listdir(pdf_dir):
        if not file.endswith(".pdf"):
            continue

        pdf_path = os.path.join(pdf_dir, file)
        stem = os.path.splitext(file)[0]
        report_images_dir = os.path.join(images_dir, stem)
        os.makedirs(report_images_dir, exist_ok=True)

        parts = []
        with pymupdf.open(pdf_path) as pdf:
            for page in pdf:
                page_no = page.number + 1
                pix = page.get_pixmap()
                image_path = os.path.join(report_images_dir, f"p{page_no:04d}.png")
                pix.save(image_path)
                markdown = parse_text_with_llm(pix)
                parts.append(f"<!-- page {page_no} -->\n\n{markdown}")
                if page_no > 10:
                    break


        output_path = os.path.join(parsed_dir, f"{stem}.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n\n-----\n\n".join(parts))
        print(f"Wrote {output_path} ({len(parts)} pages)")
        break
    end_time = time.time()
    print(f"Time taken: {end_time - start_time} seconds")


if __name__ == "__main__":
    parse_report("./test")

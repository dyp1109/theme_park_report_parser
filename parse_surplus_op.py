import json
import os
import re
import tempfile
import unicodedata
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import asyncio

import pymupdf
from openai import AsyncOpenAI
from liteparse import LiteParse


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5.4"
API_KEY_ENV_VAR = "AZURE_OPENAI_API_KEY"
METRIC_CONFIG = {
    "surplus": {
        "instruction": """Extract the surplus/deficit for the year.
Use a negative value (and is_deficit true) when the report shows a deficit.
Do not use operating surplus when a final surplus/deficit for the year is available.""",
        "schema": '"surplus": number or null,\n  "currency": "e.g. HKD or null",\n  "is_deficit": false',
        "terms": [
            "surplusfortheyear", "deficitfortheyear", "本年度盈餘", "本年度虧損",
        ],
    },
    "attendance": {
        "instruction": """Extract attendance / admission count (入場人次) for the year.
If attendance for the Park and Water World is shown separately, add both figures together and return their combined attendance.
Return the full number of admissions (for example, 7.7 million as 7700000).
Do not confuse attendance with capacity, membership, attendance targets, or cumulative attendance.""",
        "schema": '"attendance": number or null',
        "terms": [
            "attendance", "admissions", "visitors", "guests", "入場人次", "入園人次", "訪客人次",
        ],
    },
    "revenue": {
        "instruction": """Extract revenue (收入) for the year.
Return the full amount in Hong Kong dollars (for example, HK$4,272 million as 4272000000).
Do not confuse revenue with surplus, profit, funding, assets, attendance, or other income.""",
        "schema": '"revenue": number or null,\n  "currency": "HKD or null"',
        "terms": [
            "revenue", "totalrevenue", "營業收入", "收入", "收益",
        ],
    },
}


def build_system_prompt(metric):
    if metric not in METRIC_CONFIG:
        raise ValueError(
            f"Unsupported metric: {metric}. Choose from: {', '.join(METRIC_CONFIG)}"
        )
    config = METRIC_CONFIG[metric]
    return f"""You are given a page from a financial report.

For OCEAN PARK CORPORATION (海洋公園公司) only:
{config['instruction']}
Do not use figures from subsidiaries, the Ocean Park Trust Fund, or other group entities.

Reply with one JSON object and no other text:
{{
  "type": {metric},
  "year": "YYYY or null",
  {config['schema']},
  "evidence": "short quote from the report",
  "confidence": "high"
}}

confidence is "high", "medium", or "low".
If the requested figure cannot be found on this page, set it to null and explain in evidence.
If the reporting year is a consecutive range (e.g. 2020-2021), return the later year (e.g. 2021).
"""

def get_openai_client():
    # image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    api_key = os.environ.get(API_KEY_ENV_VAR)
    base_url = os.environ.get(DEFAULT_BASE_URL)
    if not api_key:
        raise RuntimeError(
            f"Missing {API_KEY_ENV_VAR}. Set it before running this script."
        )

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    return client

async def parse_metric_with_openai(client, text, metric):
    response = await client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": build_system_prompt(metric)},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    # {
                    #     "type": "image_url",
                    #     "image_url": {
                    #         "url": f"data:image/png;base64,{image_b64}",
                    #     },
                    # },
                ],
            },
        ],
        # extra_body={
        #     "chat_template_kwargs": {"enable_thinking": False},
        # },
    )
    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.removeprefix("```json").removeprefix("```")
        content = content.removesuffix("```").strip()

    try:
        parsed_json = json.loads(content)
    except json.JSONDecodeError:
        print(f"Error parsing JSON: {content}")
        return None
    return parsed_json

def normalize_for_matching(text):
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", "", text.casefold())

def score_candidate_page(text, metric):
    if metric not in METRIC_CONFIG:
        raise ValueError(
            f"Unsupported metric: {metric}. Choose from: {', '.join(METRIC_CONFIG)}"
        )

    normalized = normalize_for_matching(text)
    score = 0
    if (
        "oceanparkcorporation" in normalized
        or "海洋公園公司" in normalized
    ):
        score += 3
    # if (
    #     "oceanparktrustfund" in normalized
    #     or "海洋公園信託基金" in normalized
    # ):
    #     print('oceanparktrustfund')
    #     score -= 5
    if any(term in normalized for term in METRIC_CONFIG[metric]["terms"]):
        score += 5
    return score

def aggregate_metric_data(metric_data):
    if not metric_data:
        return []

    result = []
    current_year_check = metric_data[0]["year"]

    for metric in METRIC_CONFIG.keys():
        counts = Counter()
        items_by_value = {}
        for item in metric_data:
            if item["type"] != metric:
                continue
            value = item.get(metric)
            normalized_value = str(round(value, 2)) if value is not None else None
            if item["year"] != current_year_check:
                most_common = counts.most_common(1)
                if most_common:
                    result.append(items_by_value[most_common[0][0]])
                counts = Counter()
                items_by_value = {}
                current_year_check = item["year"]
            if normalized_value is not None:
                counts.update([normalized_value])
                items_by_value[normalized_value] = item

        most_common = counts.most_common(1)
        if most_common:
            result.append(items_by_value[most_common[0][0]])
    return result

def split_pdf(source_pdf_path):
    pdf_dir = os.path.dirname(source_pdf_path)
    file = os.path.basename(source_pdf_path)
    split_dir = os.path.join(pdf_dir, "split")
    os.makedirs(split_dir, exist_ok=True)
    split_pdf_path = os.path.join(split_dir, file)

    with pymupdf.open(source_pdf_path) as pdf, pymupdf.open() as new_pdf:
        for page in pdf:
            rect = page.rect
            width = rect.width
            height = rect.height
            if width / height > 1.15:
                midpoint = rect.x0 + width / 2
                left_clip = pymupdf.Rect(rect.x0, rect.y0, midpoint, rect.y1)
                right_clip = pymupdf.Rect(midpoint, rect.y0, rect.x1, rect.y1)

                left_page = new_pdf.new_page(width=left_clip.width, height=height)
                left_page.show_pdf_page(
                    left_page.rect,
                    pdf,
                    page.number,
                    clip=left_clip,
                )
                right_page = new_pdf.new_page(width=right_clip.width, height=height)
                right_page.show_pdf_page(
                    right_page.rect,
                    pdf,
                    page.number,
                    clip=right_clip,
                )
            else:
                copied_page = new_pdf.new_page(width=width, height=height)
                copied_page.show_pdf_page(
                    copied_page.rect,
                    pdf,
                    page.number,
                    clip=rect,
                )

        new_pdf.save(split_pdf_path)
    return split_pdf_path

async def parse_report_async(candidates):
    semaphore = asyncio.Semaphore(10)
    client = get_openai_client()

    async def parse_one(metric, page_no, page, score):
        async with semaphore:
            parsed = await parse_metric_with_openai(client, page, metric)
        if parsed is None or parsed.get("year") is None:
            return None
        parsed["page"] = page_no
        parsed["text"] = page
        parsed["score"] = score
        return parsed

    results = await asyncio.gather(*[
        parse_one(metric, page_no, page, score)
        for metric, page_no, page, score in candidates
    ])
    return [item for item in results if item is not None]


def parse_reports(pdf_dir):
    start_time = time.time()
    files = [
        os.path.join(pdf_dir, file)
        for file in os.listdir(pdf_dir)
        if file.endswith(".pdf")
    ]

    with ProcessPoolExecutor(max_workers=8) as executor:
        split_paths = list(executor.map(split_pdf, files))

    with LiteParse(
        output_format="markdown",   # "json" | "text" | "markdown"
        image_mode="placeholder",   # "placeholder" | "off" | "embed"
        extract_links=True,
        ocr_language="eng+chi_tra",
        tessdata_path="./tessdata",
        pool_size=8,
    ) as parser:
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(parser.parse, split_paths))

    print(f"Time taken parse page: {time.time() - start_time} seconds")

    candidates = []
    for result in results:
        pages = result.text.split("-----")
        for metric in METRIC_CONFIG:
            for idx, page in enumerate(pages):
                score = score_candidate_page(page, metric)
                if score >= 8:
                    candidates.append((metric, idx + 1, page, score))

    metric_data = asyncio.run(parse_report_async(candidates))
    call = len(candidates)

    end_time = time.time()
    print(f"Time taken: {end_time - start_time} seconds")
    print(f"Number of calls: {call}")
    for item in metric_data:
        item["year"] = int(item["year"]) if item["year"] is not None else 0
    metric_data.sort(key=lambda x: (x["year"], x["type"]))
    with open('review_metric_data.json', 'w') as f:
        json.dump(metric_data, f, ensure_ascii=False, indent=2)
    metric_data = aggregate_metric_data(metric_data)

    output_path = f"metric_data.json"
    with open(output_path, "w") as f:
        json.dump(metric_data, f, ensure_ascii=False, indent=2)
    return metric_data


if __name__ == '__main__':
    parse_reports('./annual_report_os')

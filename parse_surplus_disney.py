import os
import time
import re
import json
from concurrent.futures import ThreadPoolExecutor
import asyncio

from liteparse import LiteParse

from client import DEFAULT_MODEL, get_openai_client


FINANCIAL_STATEMENT_KEYWORD = r"^\#?\s*\w*(業績數據)\w+(財務摘要)\w*\s*"
FINANCIAL_STATEMENT_ENDWORD = r"^\#?\s*\w*(流動資金)\w*\s*"

SYSTEM_PROMPT = """
You are given an excerpt from a Hong Kong Disneyland (香港迪士尼) annual business review.

Extract figures for the latest fiscal year only. Ignore the prior-year column and the 變動 column. If the year is a range such as 2024-2025, return the later year.

Return these metrics:
- attendance (入場人次): park admissions for the year. The report may say 樂園入場人次. A figure in 百萬 is millions of visits (7.5 means 7500000). A figure in 萬 is tens of thousands of visits (750萬 means 7500000). Return the full visitor count.
- local_visitor_pct (香港本地訪客比例): guest share labelled 本地.
- mainland_visitor_pct (中國內地訪客比例): guest share labelled 中國內地.
- international_visitor_pct (國際訪客比例): guest share labelled 其他市場 or 國際.
- revenue_hkd (收入): revenue for the year, in Hong Kong dollars. A table headed 百萬港元 is in millions (8694 means 8694000000). A figure in 億港元 is in hundreds of millions (86.94億 means 8694000000).
- net_profit_hkd (純利): net profit for the year, in Hong Kong dollars. Accept 純利, 淨利潤, 淨虧損, or 純利/(淨虧損). Use the same unit conversion as revenue. A loss or a figure in parentheses is negative.

Visitor shares are percentages from 0 to 100 (36% is 36).
Use 未扣除利息、稅項、折舊及攤銷前盈利 only as context. It is not net profit.
Hotel occupancy, per-guest spending, and year-over-year percentage changes are not attendance or visitor share.

Reply with one JSON object and no other text:
{
  "year": "YYYY or null",
  "attendance": null,
  "local_visitor_pct": null,
  "mainland_visitor_pct": null,
  "international_visitor_pct": null,
  "revenue_hkd": null,
  "net_profit_hkd": null,
  "evidence": "short quotes from the excerpt",
  "confidence": "high"
}

confidence is "high", "medium", or "low".
If a figure is missing, set it to null and say so in evidence.
"""

async def parse_metric_with_openai(client, text):

    # client = openai.OpenAI(base_url=DEFAULT_BASE_URL, api_key=api_key)
    response = await client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                ],
            },
        ],
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

def extract_financial_text(parser, pdf_path):    
    result = parser.parse(pdf_path)
    name = os.path.splitext(os.path.basename(pdf_path))[0] + ".md"
    parsed_dir = os.path.join(os.path.dirname(pdf_path), "parsed")
    with open(os.path.join(parsed_dir, name), "w", encoding="utf-8") as f:
        f.write(result.text)
    financial_statement_match = re.search(FINANCIAL_STATEMENT_KEYWORD, result.text, re.MULTILINE)
    statement_end_match = re.search(FINANCIAL_STATEMENT_ENDWORD, result.text, re.MULTILINE)
    if financial_statement_match:
        print(financial_statement_match.start())
        if statement_end_match and statement_end_match.start() > financial_statement_match.start():
            print(statement_end_match.start())
            financial_statement_text = result.text[financial_statement_match.start():statement_end_match.start()]
        else:
            financial_statement_text = result.text[financial_statement_match.start():]
    else:
        financial_statement_text = result.text
    return (pdf_path, financial_statement_text)


async def parse_report_async(financial_texts):
    semaphore = asyncio.Semaphore(10)
    client = get_openai_client()
    async def parse_metric_with_openai_async(client, financial_text):
        async with semaphore:
            result = await parse_metric_with_openai(client, financial_text)
            return result
    results = await asyncio.gather(*[parse_metric_with_openai_async(client, financial_text) for financial_text in financial_texts])
    return [r for r in results if r is not None]

def parse_reports(pdf_dir):
    start_time = time.time()
    financial_texts = []
    pdf_paths = []

    for file in os.listdir(pdf_dir):
        if file.endswith('.pdf'):
            pdf_path = os.path.join(pdf_dir, file)
            pdf_paths.append(pdf_path)

    parsed_dir = os.path.join(pdf_dir, "parsed")
    os.makedirs(parsed_dir, exist_ok=True)

    with LiteParse(output_format="markdown", pool_size=8) as parser:
        with ThreadPoolExecutor(max_workers=8) as executor:
            for pdf_path, financial_text in executor.map(lambda path: extract_financial_text(parser, path), pdf_paths):
                if financial_text is not None:
                    financial_texts.append(financial_text)
                else:
                    print(f"Error extracting financial text from {pdf_path}")

    parsed_results = asyncio.run(parse_report_async(financial_texts))
    endtime = time.time()
    print(f"Time taken: {endtime - start_time} seconds")
    return parsed_results

if __name__ == "__main__":
    parsed_results = parse_reports("./annual_report_disney")
    with open("disney_metric.json", "w") as f:
        json.dump(parsed_results, f, indent=4, ensure_ascii=False)
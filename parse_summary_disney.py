import os
import asyncio
import json
import re

from client import DEFAULT_MODEL, get_openai_client


def report_year_from_filename(file: str) -> int | None:
    """Map AnnualBusinessReviewYY.md -> 20YY."""
    match = re.search(r"AnnualBusinessReview(\d{2})", file)
    if not match:
        return None
    return 2000 + int(match.group(1))

SYSTEM_PROMPT = """
Review this annual report and identify facts that may merit inclusion in a
Wikipedia article about Hong Kong Disneyland.

Omit routine, promotional, temporary, trivial, or repetitive material.
Do not treat selection as an annual highlight by Disney as proof of
encyclopedic significance. Do not copy promotional language.

Omit financial and attendance figures (revenue, profit/loss, guest numbers,
year-over-year % changes, etc.): these already appear in the Wikipedia
financial table. Include a finance or attendance fact only if it marks a
truly exceptional turning point that changed the park's direction (e.g.
first-ever profit after years of losses, a structural bailout or ownership
restructuring driven by finances)—not ordinary annual results.

Return ONLY valid JSON in this exact shape (no markdown fences, no prose):

{
  "facts": [
    {
      "category": "leadership",
      "statement": "Jane Smith於2022年5月獲委任為主席。",
      "importance": "high",
      "reason": "Change in organizational leadership",
      "source_quote": "Jane Smith was appointed Chairperson with effect from 15 May 2022.",
      "page": 17,
      "section": "Corporate Governance",
      "confidence": 0.96
    }
  ]
}

Field rules:
- category: one of expansion, attraction, ownership, finance, attendance,
  operations, employment, leadership, controversy, or other
- statement: concise neutral factual summary in Traditional Chinese
  (encyclopedic tone; do not use Simplified Chinese)
- importance: "high" (strong inclusion — major lasting significance),
  "medium" (possible inclusion — needs independent secondary sources),
  or "low" (weak / borderline; prefer omitting instead)
- reason: why this fact matters for Wikipedia (or why importance is set)
- source_quote: exact supporting quotation from the report
- page: integer page number if known, otherwise null
- section: report section or heading
- confidence: float 0–1 for extraction correctness

Only include candidates worth considering; prefer an empty "facts" array
over padding with omit-worthy items.
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

async def main(markdown_dir):
    sem = asyncio.Semaphore(10)
    client = get_openai_client()

    async def parse_summary_with_openai(client, file):
        async with sem:
            if file.endswith(".md"):
                with open(os.path.join(markdown_dir, file), "r") as f:
                    text = f.read()
                result = await parse_metric_with_openai(client, text)
                if result is None:
                    return None
                result["year"] = report_year_from_filename(file)
                return result
        return None

    todo = []
    for file in os.listdir(markdown_dir):
        if file.endswith(".md"):
            todo.append(parse_summary_with_openai(client, file))
    results = await asyncio.gather(*todo)
    return results

if __name__ == "__main__":
    results = asyncio.run(main("./annual_report_disney/parsed"))
    with open("disney_summary.json", "w") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
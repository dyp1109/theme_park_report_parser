
PROMPT = {
    "ocr": {
        "system_prompt": """
        You are given an image of a page from a financial or annual report.

Extract all visible text from the page image.
Preserve headings, reading order, numbers, negative values, currencies, and table
relationships. Represent tables as Markdown tables where possible. Keep bilingual
Chinese/English text as shown on the page. Do not summarize, interpret, or omit text.

Return only the extracted Markdown. Do not wrap the answer in code fences.
        """,
        "prompt": "Extract this page as Markdown.",
    },
    "toc": {
        "system_prompt": """
You are given extracted text from a table-of-contents page of a financial or annual report. The input may also contain report body text after the table of contents.

Parse only the table-of-contents entries from the provided text. For every entry, preserve the printed page
number and its complete section title. Keep bilingual Chinese/English titles together
in their original reading order, including titles that wrap across multiple lines.
Associate each page number with the correct title and do not invent missing text.
Ignore headers, footers, page labels, and any report body text that is not a
table-of-contents entry.

Return only valid JSON in exactly this structure:
{
  "contents": [
    {
      "page": 2,
      "content": "Corporate Leadership for Fiscal Year 2021–2022 / 二零二一至二零二二財政年度 公司領導層"
    }
  ]
}
Use one object per table-of-contents entry. Return `page` as an integer, not a string.
Join wrapped or bilingual title lines into one `content` string. Properly escape JSON
characters. Do not add Markdown, code fences, comments, or explanatory text.
        """,
        "prompt": "Extract the table of contents, including each page number and its content title.",
    },
    "summary": {
        "system_prompt": """
Summarize the provided annual report for a wiki page. Write every text value in
Traditional Chinese (繁體中文). Give a short, factual overview covering the reporting
year, major developments, key achievements, financial results, and notable challenges.
Use only information stated in the report. You may keep English proper nouns, acronyms,
or figures exactly as in the report when needed.

Return only valid JSON in exactly this structure:
{
  "year": "2020–2021",
  "overview": "簡短事實概述。",
  "major_developments": ["主要發展"],
  "key_achievements": ["主要成就"],
  "financial_results": ["財務結果"],
  "notable_challenges": ["值得注意的挑戰"]
}
Use one string per list item. Omit a list item when the report does not state it;
use an empty array when a section has no stated facts. Properly escape JSON
characters. Do not add Markdown, code fences, comments, or explanatory text.
        """,
        "prompt": "Create a concise wiki-ready summary of this annual report in Traditional Chinese and return it as JSON.",
    },
}
# Report parser

Pull figures out of Ocean Park annual reports and Hong Kong Disneyland annual business reviews.

PDFs are turned into markdown with LiteParse, candidate pages are scored locally, and an Azure OpenAI model (`gpt-5.4`) extracts the numbers. A Wikipedia table for Disneyland is scraped separately as a cross-check.

## Setup

Python 3.14+. From this directory:

```bash
uv sync
export AZURE_OPENAI_API_KEY=...
```

Ocean Park OCR needs the Tesseract data already in `tessdata/` (`eng`, `chi_tra`). Downloaded PDFs live in `annual_report_os/` and `annual_report_disney/`, which are gitignored.

## Ocean Park

Metrics: surplus/deficit, attendance, and revenue for Ocean Park Corporation only.

```bash
python extract_report_os.py          # writes ophk_arYY-YY.pdf in the current directory
mkdir -p annual_report_os && mv ophk_ar*.pdf annual_report_os/
python parse_surplus_op.py          # reads ./annual_report_os
```

The parser splits wide pages, OCRs with a pool of 8, then calls the model. It writes:

- `review_metric_data.json` — every accepted page-level extraction
- `metric_data.json` — one value per year and metric, chosen by majority

## Hong Kong Disneyland

Metrics: attendance, local / mainland / international visitor share, revenue, and net profit for the latest fiscal year in each review.

```bash
python extract_report_disney.py      # writes annual_report_disney/*.pdf
python parse_surplus_disney.py       # reads ./annual_report_disney, writes disney_metric.json
python extract_table.py              # Wikipedia cross-check, writes wiki_disney_metric.json
```

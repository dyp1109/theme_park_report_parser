# Report parser

Extract figures and wiki-ready notes from Ocean Park annual reports and Hong Kong Disneyland annual business reviews.

Ocean Park has two paths. The current one renders each PDF page, OCRs it with a local model, splits the markdown on the table of contents, and summarizes the 年內事項 section. The older path uses LiteParse plus Azure OpenAI (`gpt-5.4`) to pull surplus, attendance, and revenue. Disneyland still uses the LiteParse plus Azure path for metrics and encyclopedic facts, with a Wikipedia table scraped as a cross-check.

## Setup

Python 3.14+. From this directory:

```bash
uv sync
```

Azure calls (`parse_surplus_op.py`, `parse_surplus_disney.py`, `parse_summary_disney.py`) read `AZURE_OPENAI_API_KEY` and `DEFAULT_BASE_URL` from the environment or from `.env`. The model name is `gpt-5.4` in `client.py`.

Local OCR, table-of-contents parsing, and Ocean Park summaries call the vLLM servers hardcoded in `models/qwen3_8.py`, `models/unlimited_ocr.py`, and `models/paddle_ocr.py`.

Ocean Park LiteParse needs Tesseract data in `tessdata/` (`eng`, `chi_tra`). Downloaded PDFs, page images, and `tessdata/` are gitignored (`annual_report_os/`, `annual_report_disney/`, `test_data/`).

## Ocean Park

### Download

```bash
python extract_report_os.py          # writes ophk_arYY-YY.pdf in the current directory
mkdir -p annual_report_os && mv ophk_ar*.pdf annual_report_os/
```

Years requested: 2000–2024 (`ophk_ar00-01` through `ophk_ar24-25`) from `media.oceanpark.com.hk`. Missing years are skipped.

### OCR to markdown

`parse_report_op.py` renders every PDF in a directory to `images/{stem}/pNNNN.png`, then OCRs through `models/model_router.py`.

| `model_name` | Backend | Granularity |
|---|---|---|
| `qwen3_8` | Qwen3.8-27B-FP8 vision | one page per request |
| `paddle_ocr` | Paddle layout-parsing | one page per request |
| `unlimited_ocr` | `baidu/Unlimited-OCR` | whole document per request |

```bash
python parse_report_op.py
```

The `__main__` block runs `./test_data` with `unlimited_ocr` and 64 workers. Each run writes:

- `parsed_{run_id}/{stem}.md` — pages separated by `-----`, each marked `<!-- page N -->` (a whole-document model omits the page marker)
- `parsed_{run_id}/metrics_{run_id}_workers{N}.jsonl` — latency and token counts

Point the later steps at whichever markdown directory you keep. Checked-in layout output lives under `annual_report_os/parsed/`.

### Table of contents and sections

`parse_report_layout_op.py` finds the 目錄 page, asks Qwen for `{page, content}` entries, and slices the markdown into sections. Requests are spread across the Qwen instances with 10 workers.

```bash
python parse_report_layout_op.py                         # ./annual_report_os/parsed
python parse_report_layout_op.py ./annual_report_os/parsed --sections-only
```

`--sections-only` rebuilds sections from existing `*_toc.json` files and skips the model. A report that already has `*_sections.json` is skipped. For each `ophk_arYY-YY.md`:

- `ophk_arYY-YY.md_toc.json` — `contents` list of printed page number and title
- `ophk_arYY-YY.md_sections.json` — section title to the page texts that belong to it

Printed TOC page numbers are shifted by the markdown page that holds the 目錄. If that page cannot be found, the script uses `content_page_number` on the toc JSON.

### Wiki summaries

`parse_report_summary_op.py` takes the TOC entry whose title matches `年.*事.*` (年內事項), summarizes that section in Traditional Chinese, and merges the result into `ophk_ar_summaries.json`. Years already present in that file are left as they are.

```bash
python parse_report_summary_op.py
```

Each year (`01-02`, …) is an object with `year`, `overview`, `major_developments`, `key_achievements`, `financial_results`, and `notable_challenges`.

### Metrics (LiteParse + Azure)

`parse_surplus_op.py` extracts surplus/deficit, attendance, and revenue for Ocean Park Corporation only. It splits wide pages, OCRs with a LiteParse pool of 8 (`eng+chi_tra`), scores candidate pages, and keeps the majority value per year and metric.

```bash
python parse_surplus_op.py          # reads ./test, writes metric_data.json
```

Markdown for the split PDFs is written to `{pdf_dir}/parsed/`. Change the path in `__main__` to point at another directory of PDFs.

## Hong Kong Disneyland

Metrics: attendance, local / mainland / international visitor share, revenue, and net profit for the latest fiscal year in each review.

```bash
mkdir -p annual_report_disney
python extract_report_disney.py      # AnnualBusinessReviewYY.pdf for 2009–2025
python parse_surplus_disney.py       # reads ./annual_report_disney, writes disney_metric.json
python parse_summary_disney.py       # reads ./annual_report_disney/parsed, writes disney_summary.json
python extract_table.py              # zh.wikipedia 香港迪士尼樂園 table, writes wiki_disney_metric.json
```

`parse_surplus_disney.py` OCRs each PDF with LiteParse, keeps the 業績數據 / 財務摘要 excerpt, and sends that excerpt to Azure. Markdown lands in `annual_report_disney/parsed/`.

`parse_summary_disney.py` reads those markdown files and returns Wikipedia-candidate facts (leadership, expansion, ownership, and similar). Financial and attendance figures are omitted unless they mark a structural turning point. `statement` is Traditional Chinese. Each result includes `year` taken from `AnnualBusinessReviewYY.md`.

`extract_table.py` parses the attendance wikitable into the same metric fields as `disney_metric.json`.

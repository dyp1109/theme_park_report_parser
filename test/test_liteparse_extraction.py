from liteparse import LiteParse


def main(pdf_path):
    parser = LiteParse(
        output_format="markdown",   # "json" | "text" | "markdown"
        image_mode="placeholder",   # "placeholder" | "off" | "embed"
        extract_links=True,
        ocr_language="eng+chi_tra" 
    )
    result = parser.parse(pdf_path)
    print(result.text)

if __name__ == "__main__":
    main('./annual_report_disney/AnnualBusinessReview12.pdf')
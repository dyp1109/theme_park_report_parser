import requests

def extract_report():
    for year in range(2009, 2026):
        year_str = str(year)[2:]
        url = f"https://hkcorporate.hongkongdisneyland.com/zh-hk/pdf/AnnualBusinessReview{year_str}.pdf"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to download report for {url}")
            continue
        with open(f"annual_report_disney/AnnualBusinessReview{year_str}.pdf", "wb") as file:
            file.write(response.content)
        print(f"Downloaded report for {url}")

if __name__ == "__main__":
    extract_report()
    
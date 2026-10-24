import requests

def extract_report():
    for year in range(2000, 2025):
        year_str = str(year)[2:] + "-" + str(year+1)[2:]
        url = f"https://media.oceanpark.com.hk/files/s3fs-public/ophk_ar{year_str}.pdf"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to download report for {url}")
            continue
        with open(f"ophk_ar{year_str}.pdf", "wb") as file:
            file.write(response.content)
        print(f"Downloaded report for {url}")

if __name__ == "__main__":
    extract_report()
    
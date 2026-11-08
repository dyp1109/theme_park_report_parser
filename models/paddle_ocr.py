import base64
import pathlib
import time

import requests

INSTANCES = [
    {
        "base_url": "http://192.168.10.48:12434/v1",
    },
    # {
    #     "base_url": "http://192.168.10.48:12435",
    # },
]
# BASE_URL = "http://192.168.10.48:12434"
OUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "test_data" / "parsed"


def parse_with_paddle_ocr(pix, base_url, output_dir=None, stem="doc"):
    worker_started = time.perf_counter()
    out_dir = pathlib.Path(output_dir) if output_dir else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    debug_dir = out_dir / "paddle_debug" / stem
    debug_dir.mkdir(parents=True, exist_ok=True)

    image_data = base64.b64encode(pix.tobytes("png")).decode("ascii")

    payload = {
        "file": image_data,  # Base64-encoded file content or file URL
        "fileType": 1,  # File type, 1 indicates an image file
    }

    request_started = time.perf_counter()
    response = requests.post(base_url + "/layout-parsing", json=payload)
    assert response.status_code == 200, (response.status_code, response.text)

    result = response.json()["result"]
    pages = []
    for i, res in enumerate(result["layoutParsingResults"]):
        pages.append(
            {
                "prunedResult": res["prunedResult"],
                "markdownImages": res["markdown"].get("images"),
            }
        )
        for img_name, img in res["outputImages"].items():
            img_path = debug_dir / f"{img_name}_{i}.jpg"
            img_path.parent.mkdir(parents=True, exist_ok=True)
            img_path.write_bytes(base64.b64decode(img))
            print(f"Output image saved at {img_path}")

    payload = {
        "pages": pages,
        "concatenatePages": True,
    }

    response = requests.post(base_url + "/restructure-pages", json=payload)
    assert response.status_code == 200, (response.status_code, response.text)

    result = response.json()["result"]
    res = result["layoutParsingResults"][0]
    content = res["markdown"]["text"]

    md_path = out_dir / f"{stem}.md"
    md_path.write_text(content, encoding="utf-8")
    for rel_path, img in res["markdown"]["images"].items():
        img_path = out_dir / rel_path
        img_path.parent.mkdir(parents=True, exist_ok=True)
        img_path.write_bytes(base64.b64decode(img))
    print(f"Markdown document saved at {md_path}")

    finished = time.perf_counter()
    request_latency = finished - request_started
    worker_latency = finished - worker_started
    metrics = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "request_latency": request_latency,
        "worker_latency": worker_latency,
        "encode_latency": request_started - worker_started,
        "completion_tokens_per_second": 0,
        "finish_reason": "stop",
        "output_chars": len(content),
    }
    return content, metrics

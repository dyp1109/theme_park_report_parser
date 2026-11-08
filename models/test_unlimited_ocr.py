import base64
import json
import os
import tempfile

import fitz
import requests
from sglang.srt.sampling.custom_logit_processor import DeepseekOCRNoRepeatNGramLogitProcessor

server_url = "http://192.168.10.48:10000/v1"
NGRAM_PROCESSOR = DeepseekOCRNoRepeatNGramLogitProcessor.to_str()

session = requests.Session()
session.trust_env = False


def pdf_to_images(pdf_path, dpi=300):
    doc = fitz.open(pdf_path)
    tmp_dir = tempfile.mkdtemp(prefix="pdf_ocr_")
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    image_paths = []
    for i, page in enumerate(doc):
        image_path = os.path.join(tmp_dir, f"page_{i + 1:04d}.png")
        page.get_pixmap(matrix=mat).save(image_path)
        image_paths.append(image_path)
    doc.close()
    return image_paths


def encode_image(image_path):
    ext = os.path.splitext(image_path)[1].lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.')}"
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


def build_content(image_paths):
    prompt = "<PAGE><image>" * len(image_paths) + "Multi page parsing."
    return [encode_image(path) for path in image_paths] + [{"type": "text", "text": prompt}]


def generate(image_paths, crop_mode=True, tokens_per_page=8000):
    # A wider n-gram window for multi-page documents, as in our evaluation setup.
    window_size = 1024 if len(image_paths) > 1 else 128
    payload = {
        "model": "Unlimited-OCR-2",
        "messages": [{"role": "user", "content": build_content(image_paths)}],
        # Must be positive: it is the global output budget for the whole document.
        "max_tokens": tokens_per_page * len(image_paths),
        "temperature": 0,
        "skip_special_tokens": False,
        "images_config": {"crop_mode": crop_mode},  # True = gundam (tiles), False = base
        "custom_logit_processor": NGRAM_PROCESSOR,
        "custom_params": {
            "ngram_size": 35,
            "window_size": window_size,
            "page_token_id": 128827,   # <PAGE> marker id (= sparse_attention_config.page_token_id)
            "eos_token_id": 1,         # = eos_token_id in config.json
            "max_page_tokens": 20000,  # per-page output cap, <= 0 disables the page guard
        },
        "stream": True,
    }
    response = session.post(
        f"{server_url}/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=6000,
        stream=True,
    )
    response.raise_for_status()

    chunks = []
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if data == "[DONE]":
            break
        event = json.loads(data)
        choices = event.get("choices") or []  # the final chunk carries usage only
        if not choices:
            continue
        delta = (choices[0].get("delta") or {}).get("content") or ""
        if delta:
            print(delta, end="", flush=True)
            chunks.append(delta)
    return "".join(chunks)


# # Multi page: all pages of a document, parsed in one request
# pages = [f"your_doc/page_{i}.jpg" for i in range(1, 8)]
# generate(pages)

# # Single page
# generate(["your_doc/page_1.jpg"])

# PDF
result = generate(pdf_to_images("ophk_ar04-05.pdf", dpi=300))
with open("result.txt", "w") as f:
    f.write(result)
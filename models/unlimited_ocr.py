import base64
import time

from openai import OpenAI

INSTANCES = [
    {
        "base_url": "http://192.168.10.48:10000/v1",
    },
    # {
    #     "base_url": "http://192.168.10.48:10001/v1",
    # },
]
def get_client(base_url):
    return OpenAI(
        api_key="EMPTY",
        base_url=base_url,
        timeout=3600,
    )


def parse_with_unlimited_ocr(
    pixes,
    base_url,
    model="baidu/Unlimited-OCR",
):
    worker_started = time.perf_counter()
    client = get_client(base_url)
    image_b64 = [
        base64.b64encode(pix.tobytes("png")).decode("ascii") for pix in pixes
    ]
    request_started = time.perf_counter()
    print(f"Sending request to {base_url}")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "<image>document parsing."},
                    *[
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image}",
                            },
                        }
                        for image in image_b64
                    ],
                ],
            }
        ],
        max_tokens=8192,
        temperature=0.0,
        extra_body={
            "skip_special_tokens": False,
            "vllm_xargs": {"ngram_size": 35, "window_size": 128},
        },
    )
    print(f"Response received from {base_url}")
    if response.choices[0].message.content is None:
        return None, None

    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.removeprefix("```markdown").removeprefix("```md")
        content = content.removeprefix("```").removesuffix("```").strip()

    finished = time.perf_counter()
    request_latency = finished - request_started
    worker_latency = finished - worker_started
    usage = response.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    total_tokens = usage.total_tokens if usage else 0
    metrics = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "request_latency": request_latency,
        "worker_latency": worker_latency,
        "encode_latency": request_started - worker_started,
        "completion_tokens_per_second": (
            completion_tokens / request_latency if request_latency else 0
        ),
        "finish_reason": response.choices[0].finish_reason,
        "output_chars": len(content),
    }
    return content, metrics

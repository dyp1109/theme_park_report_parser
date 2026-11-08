from openai import OpenAI
import base64
import time
from models.prompt import PROMPT

def get_client(base_url):
    return OpenAI(api_key="None", base_url=base_url)

VLLM_INSTANCES = [
    {
        "base_url": "http://192.168.10.48:12434/v1",
        "model": "Qwen3.8-27B-FP8-gpu0",
        "client": get_client("http://192.168.10.48:12434/v1"),
    },
    {
        "base_url": "http://192.168.10.48:12435/v1",
        "model": "Qwen3.8-27B-FP8-gpu1",
        "client": get_client("http://192.168.10.48:12435/v1"),
    },
]

def parse_with_llm(pix, client, model):
    system_prompt = PROMPT["ocr"]["system_prompt"]
    prompt = PROMPT["ocr"]["prompt"]
    worker_started = time.perf_counter()
    image_b64 = base64.b64encode(pix.tobytes("png")).decode("ascii")
    request_started = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}",
                        },
                    },
                ],
            },
        ],
        # extra_body={
        #     "chat_template_kwargs": {"enable_thinking": False},
        # },
    )
    if response.choices[0].message.content is None:
        return None, None
    content = response.choices[0].message.content.strip()
    prompt_tokens = response.usage.prompt_tokens
    completion_tokens = response.usage.completion_tokens
    total_tokens = response.usage.total_tokens
    
    if content.startswith("```"):
        content = content.removeprefix("```markdown").removeprefix("```md")
        content = content.removeprefix("```").removesuffix("```").strip()
    finished = time.perf_counter()
    request_latency = finished - request_started
    worker_latency = finished - worker_started
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

def parse_toc_with_llm(text, client, model):
    system_prompt = PROMPT["toc"]["system_prompt"]
    prompt = PROMPT["toc"]["prompt"]
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"{prompt}\n\n{text}",
            },
        ],
        temperature=0.7,
        top_p=0.8,
        presence_penalty=1.5,
        extra_body={
            "top_k": 20,
            "chat_template_kwargs": {"enable_thinking": False},
        }, 
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content

def parse_summary_with_llm(text, client, model):
    system_prompt = PROMPT["summary"]["system_prompt"]
    prompt = PROMPT["summary"]["prompt"]
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"{prompt}\n\n{text}",
            },
        ],
        temperature=0.7,
        top_p=0.8,
        presence_penalty=1.5,
        extra_body={
            "top_k": 20,
            "chat_template_kwargs": {"enable_thinking": False},
        }, 
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content

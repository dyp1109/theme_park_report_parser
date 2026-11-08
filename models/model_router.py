import itertools
import time

from models.qwen3_8 import parse_with_llm, VLLM_INSTANCES
from models.paddle_ocr import parse_with_paddle_ocr, INSTANCES
from models.unlimited_ocr import (
    parse_with_unlimited_ocr,
    INSTANCES as UNLIMITED_OCR_INSTANCES,
)

MODEL_ROUTER = {
    "qwen3_8": {
        "parse_fn": parse_with_llm,
        "instances": itertools.cycle(VLLM_INSTANCES),
    },
    "paddle_ocr": {
        "parse_fn": parse_with_paddle_ocr,
        "instances": itertools.cycle(INSTANCES),
    },
    "unlimited_ocr": {
        "parse_fn": parse_with_unlimited_ocr,
        "instances": itertools.cycle(UNLIMITED_OCR_INSTANCES),
    },
}


def parse_with_model(model_name, pixes, executor, stem, output_dir=None):
    """Submit OCR work at the granularity required by the selected model."""
    if model_name not in MODEL_ROUTER:
        raise ValueError(f"Invalid model name: {model_name}")

    todo_tasks = []
    doc_params = {}
    backend = MODEL_ROUTER[model_name]

    if model_name == "unlimited_ocr":
        print(f"Using unlimited_ocr with {len(pixes)} pages")
        instance = next(backend["instances"])
        submitted_at = time.perf_counter()
        task = executor.submit(
            backend["parse_fn"], pixes, instance["base_url"]
        )
        todo_tasks.append(task)
        doc_params[task] = (stem, None, model_name, submitted_at)
        return todo_tasks, doc_params

    for page_no, pix in enumerate(pixes, start=1):
        instance = next(backend["instances"])
        submitted_at = time.perf_counter()

        if model_name == "qwen3_8":
            task = executor.submit(
                backend["parse_fn"],
                pix,
                instance["client"],
                instance["model"],
            )
            model_label = instance["model"]
        else:
            task = executor.submit(
                backend["parse_fn"],
                pix,
                instance["base_url"],
                output_dir,
                f"{stem}_p{page_no:04d}",
            )
            model_label = model_name

        todo_tasks.append(task)
        doc_params[task] = (stem, page_no, model_label, submitted_at)

    return todo_tasks, doc_params

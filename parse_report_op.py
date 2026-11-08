import json
import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pymupdf

from models.model_router import parse_with_model

def percentile(sorted_values, fraction):
    index = min(int(len(sorted_values) * fraction), len(sorted_values) - 1)
    return sorted_values[index]


def parse_report(pdf_dir, max_workers=4, model_name="qwen3_8"):
    start_time = time.perf_counter()
    run_id = datetime.now().strftime("%Y%m%dT%H%M%S")
    images_dir = os.path.join(pdf_dir, "images")
    parsed_dir = os.path.join(pdf_dir, f"parsed_{run_id}")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(parsed_dir, exist_ok=True)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        todo_tasks = []
        metrics_list = []
        doc_params = {}
        results = {}

        for file in os.listdir(pdf_dir):
            if not file.endswith(".pdf"):
                continue
            
            pixes = []
            pdf_path = os.path.join(pdf_dir, file)
            stem = os.path.splitext(file)[0]
            report_images_dir = os.path.join(images_dir, stem)
            os.makedirs(report_images_dir, exist_ok=True)

            with pymupdf.open(pdf_path) as pdf:
                for page in pdf:
                    page_no = page.number + 1
                    pix = page.get_pixmap()
                    image_path = os.path.join(report_images_dir, f"p{page_no:04d}.png")
                    pix.save(image_path)
                    pixes.append(pix)
            tasks, params = parse_with_model(
                model_name, pixes, executor, stem, parsed_dir
            )
            todo_tasks.extend(tasks)
            doc_params.update(params)
                  
        for completed_task in as_completed(todo_tasks):
            stem, page_no, model, submitted_at = doc_params[completed_task]
            content, metrics = completed_task.result()
            if content is None:
                continue
            completed_at = time.perf_counter()
            metrics.update(
                {
                    "run_id": run_id,
                    "max_workers": max_workers,
                    "stem": stem,
                    "page_no": page_no,
                    "model": model,
                    "queue_latency": (
                        completed_at - submitted_at - metrics["worker_latency"]
                    ),
                    "end_to_end_latency": completed_at - submitted_at,
                }
            )
            results.setdefault(stem, []).append((page_no, content, metrics))
            metrics_list.append(metrics)

    for stem, stem_results in results.items():
        stem_results.sort(
            key=lambda item: item[0] if item[0] is not None else 0
        )
        parts = [
            markdown
            if page_no is None
            else f"<!-- page {page_no} -->\n\n{markdown}"
            for page_no, markdown, _ in stem_results
        ]
        output_path = os.path.join(parsed_dir, f"{stem}.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n\n-----\n\n".join(parts))
        print(f"Wrote {output_path} ({len(parts)} result(s))")
                    
    elapsed = time.perf_counter() - start_time
    n = len(metrics_list)
    if not n:
        print("No pages completed successfully")
        return

    metrics_path = os.path.join(
        parsed_dir, f"metrics_{run_id}_workers{max_workers}.jsonl"
    )
    with open(metrics_path, "w", encoding="utf-8") as f:
        for metrics in metrics_list:
            f.write(json.dumps(metrics, ensure_ascii=False) + "\n")

    by_latency = sorted(metrics_list, key=lambda x: x["request_latency"])
    latency_values = [metrics["request_latency"] for metrics in by_latency]
    p50 = percentile(latency_values, 0.50)
    p95 = percentile(latency_values, 0.95)
    p99 = percentile(latency_values, 0.99)
    maximum = latency_values[-1]
    ppm = n / (elapsed / 60)
    total_prompt_tokens = sum(m["prompt_tokens"] for m in metrics_list)
    total_completion_tokens = sum(m["completion_tokens"] for m in metrics_list)
    aggregate_completion_tps = total_completion_tokens / elapsed

    print(f"pages={n} wall={elapsed:.1f}s  pages/min={ppm:.1f}")
    print(
        f"latency avg={sum(latency_values)/n:.2f}s  p50={p50:.2f}s  "
        f"p95={p95:.2f}s  p99={p99:.2f}s  max={maximum:.2f}s"
    )
    print(
        f"tokens prompt={total_prompt_tokens} completion={total_completion_tokens}  "
        f"aggregate completion tokens/s={aggregate_completion_tps:.2f}"
    )
    print("slowest results:")
    for metrics in reversed(by_latency[-10:]):
        result_label = (
            "document"
            if metrics["page_no"] is None
            else f"p{metrics['page_no']:04d}"
        )
        print(
            f"  {metrics['stem']} {result_label} "
            f"model={metrics['model']} latency={metrics['request_latency']:.2f}s "
            f"completion_tokens={metrics['completion_tokens']} "
            f"tokens/s={metrics['completion_tokens_per_second']:.2f} "
            f"finish={metrics['finish_reason']}"
        )
    print(f"metrics={metrics_path}")


if __name__ == "__main__":
    max_worker_search = [64]
    for max_workers in max_worker_search:
        print(f"max_workers={max_workers}")
        parse_report("./test_data", max_workers, "unlimited_ocr")
        print()

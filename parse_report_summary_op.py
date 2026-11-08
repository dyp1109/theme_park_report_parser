import os
import re
import json
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed

from models.qwen3_8 import parse_summary_with_llm, VLLM_INSTANCES

keywords = [f"年.*事.*"]
year_re = r"ophk_ar(\d{2}-\d{2})"

def get_summary(section_content, instance):
    client = instance["client"]
    model = instance["model"]
    
    summary = parse_summary_with_llm(section_content, client, model)
    summary = json.loads(summary)
    return summary

def parse_report_summary_op(path, output_path):
    summaries_json, parsed_years = read_parsed_summary(output_path)
    for filename in os.listdir(path):
        if filename.endswith(".md_toc.json"):
            filenames = sorted(
                filename
                for filename in os.listdir(path)
                if filename.endswith(".md_toc.json")
            )
    
    summaries = {}
    todo_tasks = []
    todo_results = {}
    instances = itertools.cycle(VLLM_INSTANCES)
    with ThreadPoolExecutor(max_workers=10) as executor:
        for filename in filenames:
            with open(os.path.join(path, filename), "r") as f:
                toc = json.load(f)
            for content in toc["contents"]:
                if any(re.search(keyword, content["content"]) for keyword in keywords):
                    year = re.search(year_re, filename).group(1)
                    if year in parsed_years:
                        continue
                    section_name = content["content"]
                    with open(os.path.join(path, filename.replace(".md_toc.json", ".md_sections.json")), "r") as f:
                        sections = json.load(f)
                    instance = next(instances)
                    section_content = sections[section_name]
                    future = executor.submit(get_summary, "".join(section_content), instance)

                    todo_tasks.append(future)
                    todo_results[future] = (year, section_name)

    for future in as_completed(todo_tasks):
        year, section_name = todo_results[future]
        summary = future.result()
        summaries[year] = summary
    
    summaries_json.update(summaries)
    with open(output_path, "w") as f:
        json.dump(summaries_json, f, ensure_ascii=False, indent=4)

def read_parsed_summary(path):
    years = []
    with open(path, "r") as f:
        summaries = json.load(f)
    for k in summaries.keys():
        years.append(k)
    return summaries, years

if __name__ == "__main__":
    parse_report_summary_op("./annual_report_os/parsed", "ophk_ar_summaries.json")
import argparse
import re
import json
import os
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed

from models.qwen3_8 import parse_toc_with_llm, VLLM_INSTANCES

toc_re = re.compile(
    r"<!-- page (?P<page_number>\d+) -->"
    r"(?:(?!<!-- page \d+ -->).)*?"
    r"目錄.*?\n"
    r"(?P<body>.*?)\n-----"
    r"(?P<report_body>.*)",
    re.DOTALL,
)


def read_report(path):
    with open(path, "r") as f:
        text = f.read()
    pages = re.split(r"<!-- page \d+ -->", text)
    return text, pages


def locate_toc(text):
    if "目錄" not in text:
        return None
    match = toc_re.search(text)
    if not match:
        return None
    return match.group("body"), int(match.group("page_number"))


def build_sections(pages, contents, content_page_number):
    toc_contents = {}
    content_text = None
    start_page = None
    for idx, content in enumerate(contents):
        page = content["page"] + content_page_number - 1
        if idx != 0:
            print(f"start_page: {start_page}, page: {page}")
            toc_contents[content_text] = pages[start_page:page]
        content_text = content["content"]
        start_page = page
    if content_text is not None:
        toc_contents[content_text] = pages[start_page:]
    return toc_contents


def parse_toc(path, instance):
    client = instance["client"]
    model = instance["model"]
    text, _pages = read_report(path)
    located = locate_toc(text)
    if located is None:
        print(f"No TOC found in {path}")
        return None

    body, content_page_number = located
    print(f"content_page_number: {content_page_number}")
    toc = parse_toc_with_llm(body, client, model)
    try:
        toc_parsed = json.loads(toc)
    except Exception as e:
        print(f"Error parsing TOC: {e}")
        return None

    print(f"toc_parsed: {toc_parsed}")
    with open(f"{path}_toc.json", "w") as f:
        json.dump(toc_parsed, f, ensure_ascii=False, indent=4)
    return toc_parsed


def parse_sections(path):
    sections_path = f"{path}_sections.json"
    if os.path.exists(sections_path):
        print(f"Sections already exist, skipping {path}")
        return

    text, pages = read_report(path)
    toc_path = f"{path}_toc.json"
    if not os.path.exists(toc_path):
        print(f"No TOC json found for {path}")
        return

    with open(toc_path, "r") as f:
        toc_parsed = json.load(f)

    located = locate_toc(text)
    if located is not None:
        _body, content_page_number = located
    elif toc_parsed.get("content_page_number") is not None:
        content_page_number = int(toc_parsed["content_page_number"])
    else:
        print(f"No TOC found in {path}")
        return

    print(f"content_page_number: {content_page_number}")

    contents = toc_parsed.get("contents") or []
    if not contents:
        print(f"No TOC contents in {toc_path}")
        return

    toc_contents = build_sections(pages, contents, content_page_number)
    with open(sections_path, "w") as f:
        json.dump(toc_contents, f, ensure_ascii=False, indent=4)


def parse(path, instance):
    if parse_toc(path, instance) is None:
        return
    parse_sections(path)


def parse_report_layout_op(path, sections_only=False):
    instances = itertools.cycle(VLLM_INSTANCES)
    with ThreadPoolExecutor(max_workers=10) as executor:
        todo = []
        for filename in os.listdir(path):
            if not filename.endswith(".md"):
                continue
            print(f"Parsing {filename}")
            filepath = os.path.join(path, filename)
            if sections_only:
                todo.append(executor.submit(parse_sections, filepath))
            else:
                instance = next(instances)
                todo.append(executor.submit(parse, filepath, instance))

        for future in as_completed(todo):
            future.result()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="./annual_report_os/parsed")
    parser.add_argument(
        "--sections-only",
        action="store_true",
        help="Skip the LLM TOC parse and rebuild sections from existing *_toc.json files",
    )
    args = parser.parse_args()
    parse_report_layout_op(args.path, sections_only=args.sections_only)

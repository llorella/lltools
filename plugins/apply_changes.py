# plugins/apply_changes.py
import os
import json
from typing import List, Dict, Any

from plugins import plugin
from utils.helpers import get_valid_index, path_input
from utils.file_diff import generate_diff, prompt_and_write_file

@plugin
def apply_changes(messages: List[Dict[str, Any]], args: Dict, index: int = -1) -> List[Dict[str, Any]]:
    """
    Loads JSON from:
      - The content of a message, or
      - A file (args.file)
    Each item is { "filename": "...", "content": "..." }.

    Then for each item, we show a diff vs. what's on disk and prompt to write.
    """
    if not args.load:
        project_exec_dir = os.path.join(args.exec_dir, "untitled")
    else:
        ll_dir_abs = os.path.abspath(args.ll_dir)
        load_abs = os.path.abspath(args.load)
        rel = os.path.relpath(load_abs, ll_dir_abs)  # e.g. "project/subdir.ll"

        base, ext = os.path.splitext(rel)
        if ext == ".ll":
            rel = base

        project_exec_dir = os.path.join(args.exec_dir, rel)

    os.makedirs(project_exec_dir, exist_ok=True)

    json_text = None
    if args.file:
        file_path = args.file if args.non_interactive else path_input(args.file, os.getcwd())
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            return messages
        with open(file_path, 'r', encoding='utf-8') as f:
            json_text = f.read()
    else:
        msg_index = get_valid_index(messages, "load JSON from", index)
        json_text = messages[msg_index]["content"]

    # Parse JSON
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return messages

    if not isinstance(data, list):
        print("Expected a JSON list of objects {filename, content}.")
        return messages

    modified_files = []
    skipped_files = []

    for i, item in enumerate(data):
        if not isinstance(item, dict) or "filename" not in item or "content" not in item:
            print(f"Skipping data[{i}]: must be an object with 'filename' and 'content'.")
            skipped_files.append(f"data[{i}]")
            continue

        rel_filename = item["filename"]
        new_content = item["content"]

        final_path = os.path.join(project_exec_dir, rel_filename)
        old_content = ""
        if os.path.isfile(final_path):
            try:
                with open(final_path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
            except Exception as e:
                print(f"Error reading {final_path}: {e}")
                skipped_files.append(rel_filename)
                continue

        diff_text = generate_diff(old_content, new_content, rel_filename)
        did_write = prompt_and_write_file(final_path, new_content, diff_text)
        if did_write:
            modified_files.append(rel_filename)
        else:
            skipped_files.append(rel_filename)

    # Summarize
    summary = []
    if modified_files:
        summary.append(f"Modified/Created: {modified_files}")
    if skipped_files:
        summary.append(f"Skipped: {skipped_files}")
    if not summary:
        summary.append("No changes were applied.")

    summary_msg = "Apply changes operation complete.\n" + "\n".join(summary)
    messages.append({"role": "assistant", "content": summary_msg})

    return messages

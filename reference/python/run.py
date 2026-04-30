"""
AISOP V1.0.0 — Load and inspect .aisop.json files.

Usage:
    python run.py                              # default: example.aisop.json
    python run.py my_flow.aisop.json           # custom flow
    python run.py my_flow.aisop.json --prompt "hello"  # build prompt
    python run.py --test                       # run test suite

Prerequisites:
    pip install -r requirements.txt  (none — zero dependencies)
"""

import io
import json
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from flow_runtime import load, get_metadata, get_tasks, get_functions, list_nodes, render_flow, build_prompt


def inspect_flow(path: str):
    """Load and display flow information."""
    data = load(path)
    meta = get_metadata(data)

    print(f"{'='*50}")
    print(f"  {meta.get('name')} v{meta.get('version')}")
    print(f"  Protocol: {meta.get('protocol')}")
    print(f"  ID: {meta.get('id')}")
    if meta.get("summary"):
        print(f"  Summary: {meta['summary']}")
    print(f"{'='*50}\n")

    # List all tasks
    tasks = get_tasks(data)
    for task_name in tasks:
        print(f"Task: {task_name}")
        print(render_flow(data, task_name))
        print()

    # List functions
    funcs = get_functions(data)
    print(f"Functions ({len(funcs)}):")
    for name, body in funcs.items():
        steps = ", ".join(f"{k}: {v}" for k, v in body.items())
        print(f"  {name}: {steps}")


def show_prompt(path: str, user_input: str):
    """Build and display the full prompt."""
    data = load(path)
    prompt = build_prompt(data, user_input)
    print(prompt)


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--test" in args:
        subprocess.run([sys.executable, "test_all.py"])
    elif "--prompt" in args:
        idx = args.index("--prompt")
        flow_path = args[0] if idx > 0 else "example.aisop.json"
        user_input = args[idx + 1] if idx + 1 < len(args) else "hello"
        show_prompt(flow_path, user_input)
    else:
        flow_path = args[0] if args else "example.aisop.json"
        inspect_flow(flow_path)

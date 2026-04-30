# AISOP Python Reference Implementation

Zero-dependency Python utilities for loading, validating, and running AISOP flow files.

## Files

| File | Purpose |
|------|---------|
| `flow_runtime.py` | Core library — Mermaid parser, loader, validator, flow analyzer, prompt builder |
| `run.py` | CLI tool — inspect and run `.aisop.json` files |
| `test_all.py` | Test suite — 44 tests covering Mermaid parsing, JSON flow, mixed flow, all node types, flow patterns, and sys.* system calls |
| `example.aisop.json` | Example flow file — greeting assistant |
| `example_syscalls.aisop.json` | Advanced example — deployment pipeline with sys.* calls |
| `pyproject.toml` | Python package metadata |

## Quick Start

```bash
# Inspect a flow file
python run.py example.aisop.json

# Build a prompt (simulate runtime input)
python run.py example.aisop.json --prompt "I have a billing issue"

# Run all tests
python test_all.py
```

## API (flow_runtime.py)

```python
from flow_runtime import load, validate, render_flow, build_prompt, parse_mermaid

program = load("example.aisop.json")   # Load and parse
validate(program)                       # Structural validation (raises ValueError on error)
print(render_flow(program))             # Print Mermaid flow diagram
prompt = build_prompt(program, user_input="hello")  # Build runtime prompt

# Parse Mermaid directly
parsed = parse_mermaid("graph TD\n    A[Start] --> B((End))")
print(parsed["nodes"])       # {'A': {'next': ['B']}, 'B': {}}
print(parsed["node_types"])  # {'A': 'process', 'B': 'end'}
```

## sys.* System Call API

```python
from flow_runtime import classify_step, parse_sys_call, eval_expression

# Step classification (§5.3)
classify_step("sys.io.confirm('ok?')")      # → "sys_call"
classify_step("RUN aisop.sub")              # → "sub_task"
classify_step("Analyze data")              # → "natural_language"

# Parse sys.* calls (§6.10)
result = parse_sys_call("sys.io.input('Enter path') -> target_path")
# → {"name": "sys.io.input", "args": "'Enter path'", "store": "target_path", "valid": True}

# Deterministic expression engine (§6.11)
eval_expression("count > 0 && status != null", {"count": 5, "status": "ok"})  # → True
```

## Requirements

- Python 3.10+
- Zero external dependencies (stdlib only)

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev

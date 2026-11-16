"""
AISOP V1.0.0 — Test suite for flow_runtime utilities.

Offline, no AI needed.

Usage: python test_all.py

Covers:
  1. Mermaid parsing (node shapes, edge types, chained edges)
  2. Load & validate .aisop.json files
  3. Metadata extraction
  4. Task and function listing
  5. Flow rendering (Mermaid passthrough)
  6. Prompt building
  7. Validation error detection
  8. Multiple tasks (main + sub-tasks)
  9. All node types (process, decision, end, delegate, fork)
"""

import json
import os
import tempfile
from flow_runtime import (
    load, validate, get_metadata, get_tasks, get_functions,
    list_nodes, render_flow, build_prompt, parse_mermaid, infer_node_type,
    classify_step, parse_sys_call, eval_expression,
    VALID_SYS_CALLS, SYS_ERROR_TYPES,
)


# ── Test fixtures ───────────────────────────────────────────

SIMPLE_FLOW = [
    {
        "role": "system",
        "content": {
            "protocol": "AISOP V1.0.0",
            "axiom_0": "Human_Sovereignty_and_Wellbeing",
            "id": "test_simple",
            "name": "Simple Test",
            "version": "1.0.0",
            "summary": "A simple test flow",
            "flow_format": "mermaid",
            "tools": [],
            "params": { "language": "string", "tone": "string" },
            "system_prompt": "{system_prompt}"
        }
    },
    {
        "role": "user",
        "content": {
            "instruction": "RUN aisop.main",
            "user_input": "{user_input}",
            "aisop": {
                "main": "graph TD\n    greet[Greet] --> classify{Classify}\n    classify -->|question| search[Search]\n    classify -->|chat| reply[Reply]\n    search --> end_node((End))\n    reply --> end_node"
            },
            "functions": {
                "greet":    {"step1": "Say hello"},
                "classify": {"step1": "Classify intent"},
                "search":   {"step1": "Search info"},
                "reply":    {"step1": "Chat reply"},
                "end_node": {"step1": "Final output"}
            }
        }
    }
]

MULTI_TASK_FLOW = [
    {
        "role": "system",
        "content": {
            "protocol": "AISOP V1.0.0",
            "axiom_0": "Human_Sovereignty_and_Wellbeing",
            "id": "test_multi",
            "name": "Multi Task Test",
            "version": "1.0.0",
            "flow_format": "mermaid",
            "system_prompt": "{system_prompt}"
        }
    },
    {
        "role": "user",
        "content": {
            "instruction": "RUN aisop.main",
            "user_input": "{user_input}",
            "aisop": {
                "main": "graph TD\n    start[Start] --> delegate_step[aisop.validation]\n    delegate_step --> finish[Finish]\n    finish --> end_node((End))",
                "validation": "graph TD\n    check[Check] --> verify[Verify]\n    verify --> done((Done))"
            },
            "functions": {
                "start":         {"step1": "Begin"},
                "delegate_step": {"step1": "Call validation"},
                "finish":        {"step1": "Wrap up"},
                "check":         {"step1": "Check input"},
                "verify":        {"step1": "Verify result"}
            }
        }
    }
]

PARALLEL_FLOW = [
    {
        "role": "system",
        "content": {
            "protocol": "AISOP V1.0.0",
            "axiom_0": "Human_Sovereignty_and_Wellbeing",
            "id": "test_parallel",
            "name": "Parallel Test",
            "version": "1.0.0",
            "flow_format": "mermaid",
            "system_prompt": "{system_prompt}"
        }
    },
    {
        "role": "user",
        "content": {
            "instruction": "RUN aisop.main",
            "user_input": "{user_input}",
            "aisop": {
                "main": "graph TD\n    prepare[Prepare] --> step_a[Step A]\n    prepare --> step_b[Step B]\n    step_a --> sync[Sync]\n    step_b --> sync\n    sync --> finish[Finish]\n    finish --> end_node((End))"
            },
            "functions": {
                "prepare": {"step1": "Prepare data"},
                "step_a":  {"step1": "Process A"},
                "step_b":  {"step1": "Process B"},
                "sync":    {"step1": "Merge results", "join": {"merge_strategy": "array"}},
                "finish":  {"step1": "Finalize"}
            }
        }
    }
]

ERROR_FLOW = [
    {
        "role": "system",
        "content": {
            "protocol": "AISOP V1.0.0",
            "axiom_0": "Human_Sovereignty_and_Wellbeing",
            "id": "test_error",
            "name": "Error Test",
            "version": "1.0.0",
            "flow_format": "mermaid",
            "system_prompt": "{system_prompt}"
        }
    },
    {
        "role": "user",
        "content": {
            "instruction": "RUN aisop.main",
            "user_input": "{user_input}",
            "aisop": {
                "main": "graph TD\n    risky[Risky Step] --> finish[Finish]\n    risky -.-> error_handler[Error Handler]\n    error_handler --> finish\n    finish --> end_node((End))"
            },
            "functions": {
                "risky":         {"step1": "Risky operation"},
                "error_handler": {"step1": "Handle error"},
                "finish":        {"step1": "Done"}
            }
        }
    }
]


# ── Tests ───────────────────────────────────────────────────

def test_parse_mermaid_basic():
    """Parse basic Mermaid with node shapes and edges."""
    mermaid = "graph TD\n    A[Start] --> B{Check}\n    B -->|yes| C[Do]\n    B -->|no| D((End))"
    result = parse_mermaid(mermaid)
    nodes = result["nodes"]
    types = result["node_types"]

    assert "A" in nodes and "B" in nodes and "C" in nodes and "D" in nodes
    assert types["A"] == "process"
    assert types["B"] == "decision"
    assert types["D"] == "end"
    assert nodes["A"]["next"] == ["B"]
    assert nodes["B"]["branches"] == {"yes": "C", "no": "D"}
    print("  [PASS] parse_mermaid: basic shapes and edges")


def test_parse_mermaid_error_edge():
    """Parse dashed error edge."""
    mermaid = "graph TD\n    risky[Risky] --> ok[OK]\n    risky -.-> err[Error]"
    result = parse_mermaid(mermaid)
    nodes = result["nodes"]
    assert nodes["risky"]["next"] == ["ok"]
    assert nodes["risky"]["error"] == "err"
    print("  [PASS] parse_mermaid: error edge (-.->)")


def test_parse_mermaid_delegate():
    """Parse delegate node from aisop.sub label."""
    mermaid = "graph TD\n    start[Start] --> call[aisop.validation]\n    call --> done((Done))"
    result = parse_mermaid(mermaid)
    nodes = result["nodes"]
    types = result["node_types"]
    assert types["call"] == "delegate"
    assert nodes["call"]["delegate_to"] == "validation"
    assert nodes["call"]["next"] == ["done"]
    print("  [PASS] parse_mermaid: delegate node (aisop.sub)")


def test_parse_mermaid_chained():
    """Parse chained edges on a single line."""
    mermaid = "graph TD\n    A[Start] --> B[Middle] --> C((End))"
    result = parse_mermaid(mermaid)
    nodes = result["nodes"]
    assert nodes["A"]["next"] == ["B"]
    assert nodes["B"]["next"] == ["C"]
    print("  [PASS] parse_mermaid: chained edges")


def test_parse_mermaid_parallel():
    """Parse parallel fork (one source, two targets)."""
    mermaid = "graph TD\n    P[Prepare] --> A[Task A]\n    P --> B[Task B]\n    A --> S[Sync]\n    B --> S"
    result = parse_mermaid(mermaid)
    nodes = result["nodes"]
    assert set(nodes["P"]["next"]) == {"A", "B"}
    print("  [PASS] parse_mermaid: parallel fork")


def test_infer_node_type():
    """Infer node type from parsed structure."""
    assert infer_node_type({}) == "end"
    assert infer_node_type({"branches": {"a": "b"}}) == "decision"
    assert infer_node_type({"delegate_to": "sub", "next": ["x"]}) == "delegate"
    assert infer_node_type({"next": ["a", "b"]}) == "fork"
    assert infer_node_type({"next": ["a"]}) == "process"
    print("  [PASS] infer_node_type: all patterns correct")


def test_validate_valid():
    """Valid AISOP data should pass validation."""
    validate(SIMPLE_FLOW)
    validate(MULTI_TASK_FLOW)
    validate(PARALLEL_FLOW)
    validate(ERROR_FLOW)
    print("  [PASS] validate: all valid flows pass")


def test_validate_invalid():
    """Invalid data should raise ValueError."""
    errors = 0

    # Not a list
    try:
        validate({"bad": True})
    except ValueError:
        errors += 1

    # Wrong length
    try:
        validate([{"role": "system", "content": {}}])
    except ValueError:
        errors += 1

    # Missing role
    try:
        validate([
            {"role": "wrong", "content": {"protocol": "AISOP V1.0.0", "axiom_0": "Human_Sovereignty_and_Wellbeing", "id": "x", "name": "x", "version": "1", "flow_format": "mermaid"}},
            {"role": "user", "content": {"instruction": "RUN aisop.main", "aisop": {"main": "graph TD\n    A[X] --> B((Y))"}, "functions": {}}}
        ])
    except ValueError:
        errors += 1

    # Missing required metadata (missing id, name, version)
    try:
        validate([
            {"role": "system", "content": {"protocol": "AISOP V1.0.0", "axiom_0": "Human_Sovereignty_and_Wellbeing", "flow_format": "mermaid"}},
            {"role": "user", "content": {"instruction": "RUN aisop.main", "aisop": {"main": "graph TD\n    A[X] --> B((Y))"}, "functions": {}}}
        ])
    except ValueError:
        errors += 1

    # Missing main task
    try:
        validate([
            {"role": "system", "content": {"protocol": "AISOP V1.0.0", "axiom_0": "Human_Sovereignty_and_Wellbeing", "id": "x", "name": "x", "version": "1", "flow_format": "mermaid"}},
            {"role": "user", "content": {"instruction": "RUN aisop.main", "aisop": {"other": "graph TD\n    A[X] --> B((Y))"}, "functions": {}}}
        ])
    except ValueError:
        errors += 1

    # Task is not a string or object (invalid type)
    try:
        validate([
            {"role": "system", "content": {"protocol": "AISOP V1.0.0", "axiom_0": "Human_Sovereignty_and_Wellbeing", "id": "x", "name": "x", "version": "1", "flow_format": "mermaid"}},
            {"role": "user", "content": {"instruction": "RUN aisop.main", "aisop": {"main": 123}, "functions": {}}}
        ])
    except ValueError:
        errors += 1

    # Wrong axiom_0 value
    try:
        validate([
            {"role": "system", "content": {"protocol": "AISOP V1.0.0", "axiom_0": "wrong_value", "id": "x", "name": "x", "version": "1", "flow_format": "mermaid"}},
            {"role": "user", "content": {"instruction": "RUN aisop.main", "aisop": {"main": "graph TD\n    A[X] --> B((Y))"}, "functions": {}}}
        ])
    except ValueError:
        errors += 1

    # Wrong flow_format value
    try:
        validate([
            {"role": "system", "content": {"protocol": "AISOP V1.0.0", "axiom_0": "Human_Sovereignty_and_Wellbeing", "id": "x", "name": "x", "version": "1", "flow_format": "invalid"}},
            {"role": "user", "content": {"instruction": "RUN aisop.main", "aisop": {"main": "graph TD\n    A[X] --> B((Y))"}, "functions": {}}}
        ])
    except ValueError:
        errors += 1

    assert errors == 8, f"Expected 8 validation errors, got {errors}"
    print("  [PASS] validate: all invalid inputs rejected")


def test_get_metadata():
    """Extract metadata correctly."""
    meta = get_metadata(SIMPLE_FLOW)
    assert meta["protocol"] == "AISOP V1.0.0"
    assert meta["id"] == "test_simple"
    assert meta["name"] == "Simple Test"
    assert meta["version"] == "1.0.0"
    assert meta.get("params") == {"language": "string", "tone": "string"}
    print("  [PASS] get_metadata: correct extraction")


def test_get_tasks():
    """Extract task definitions (Mermaid strings)."""
    tasks = get_tasks(SIMPLE_FLOW)
    assert "main" in tasks
    assert isinstance(tasks["main"], str)
    assert "greet" in tasks["main"]

    tasks2 = get_tasks(MULTI_TASK_FLOW)
    assert "main" in tasks2
    assert "validation" in tasks2
    print("  [PASS] get_tasks: main and sub-tasks found")


def test_get_functions():
    """Extract function definitions."""
    funcs = get_functions(SIMPLE_FLOW)
    assert "greet" in funcs
    assert funcs["greet"]["step1"] == "Say hello"
    assert "classify" in funcs
    print("  [PASS] get_functions: correct extraction")


def test_list_nodes():
    """List nodes with type and connections from Mermaid."""
    nodes = list_nodes(SIMPLE_FLOW)
    names = [n["name"] for n in nodes]
    assert "greet" in names
    assert "classify" in names
    assert "end_node" in names

    classify = [n for n in nodes if n["name"] == "classify"][0]
    assert classify["type"] == "decision"
    assert "branches" in classify
    assert classify["branches"]["question"] == "search"
    print("  [PASS] list_nodes: correct node listing")


def test_list_nodes_subtask():
    """List nodes from a sub-task."""
    nodes = list_nodes(MULTI_TASK_FLOW, "validation")
    names = [n["name"] for n in nodes]
    assert "check" in names
    assert "verify" in names
    assert "done" in names
    print("  [PASS] list_nodes: sub-task listing works")


def test_parallel_nodes():
    """Parallel fork node listed correctly."""
    nodes = list_nodes(PARALLEL_FLOW)
    prepare = [n for n in nodes if n["name"] == "prepare"][0]
    assert prepare["type"] == "fork"
    assert set(prepare["next"]) == {"step_a", "step_b"}
    print("  [PASS] list_nodes: parallel fork")


def test_error_routing_nodes():
    """Error routing node listed correctly."""
    nodes = list_nodes(ERROR_FLOW)
    risky = [n for n in nodes if n["name"] == "risky"][0]
    assert risky["error"] == "error_handler"
    print("  [PASS] list_nodes: error routing")


def test_delegate_nodes():
    """Delegate node listed correctly."""
    nodes = list_nodes(MULTI_TASK_FLOW)
    delegate = [n for n in nodes if n["name"] == "delegate_step"][0]
    assert delegate["type"] == "delegate"
    assert delegate["delegate_to"] == "validation"
    print("  [PASS] list_nodes: delegate node")


def test_render_flow():
    """Render flow returns Mermaid string."""
    output = render_flow(SIMPLE_FLOW)
    assert "graph TD" in output
    assert "greet" in output
    assert "classify" in output
    assert "question" in output
    print("  [PASS] render_flow: returns Mermaid")


def test_build_prompt():
    """Build prompt with variable substitution."""
    prompt = build_prompt(SIMPLE_FLOW, "hello", "You are a helpful assistant.")
    parsed = json.loads(prompt)
    assert parsed[0]["content"]["system_prompt"] == "You are a helpful assistant."
    assert parsed[1]["content"]["user_input"] == "hello"
    print("  [PASS] build_prompt: variable substitution works")


def test_load_file():
    """Load from actual file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".aisop.json", delete=False, encoding="utf-8") as f:
        json.dump(SIMPLE_FLOW, f, ensure_ascii=False)
        tmp_path = f.name

    try:
        data = load(tmp_path)
        assert get_metadata(data)["id"] == "test_simple"
        print("  [PASS] load: file loading works")
    finally:
        os.unlink(tmp_path)


def test_load_example():
    """Load the bundled example.aisop.json."""
    example_path = os.path.join(os.path.dirname(__file__), "example.aisop.json")
    if os.path.exists(example_path):
        data = load(example_path)
        meta = get_metadata(data)
        assert meta["protocol"] == "AISOP V1.0.0"
        assert "main" in get_tasks(data)
        print("  [PASS] load: example.aisop.json valid")
    else:
        print("  [SKIP] load: example.aisop.json not found")


def test_load_example_syscalls():
    """Load the bundled example_syscalls.aisop.json."""
    example_path = os.path.join(os.path.dirname(__file__), "example_syscalls.aisop.json")
    if os.path.exists(example_path):
        data = load(example_path)
        meta = get_metadata(data)
        assert meta["protocol"] == "AISOP V1.0.0"
        tasks = get_tasks(data)
        assert "main" in tasks
        funcs = get_functions(data)
        assert "validate" in funcs
        assert "deploy" in funcs
        # Verify syscall steps are classifiable
        assert classify_step(funcs["validate"]["step1"]) == "sys_call"
        print("  [PASS] load: example_syscalls.aisop.json valid")
    else:
        print("  [SKIP] load: example_syscalls.aisop.json not found")


def test_params():
    """params field in system.content is optional and preserved."""
    meta = get_metadata(SIMPLE_FLOW)
    assert "params" in meta
    assert meta["params"]["language"] == "string"
    assert meta["params"]["tone"] == "string"

    validate(MULTI_TASK_FLOW)
    meta2 = get_metadata(MULTI_TASK_FLOW)
    assert meta2.get("params") is None
    print("  [PASS] params: optional field correctly handled")



# ── JSON Flow Tests ────────────────────────────────────────

JSON_FLOW = [
    {
        "role": "system",
        "content": {
            "protocol": "AISOP V1.0.0",
            "axiom_0": "Human_Sovereignty_and_Wellbeing",
            "id": "test_jsonflow",
            "name": "JSON Flow Test",
            "version": "1.0.0",
            "flow_format": "jsonflow"
        }
    },
    {
        "role": "user",
        "content": {
            "instruction": "RUN aisop.main",
            "user_input": "{user_input}",
            "aisop": {
                "main": {
                    "greet":    {"next": ["classify"]},
                    "classify": {"branches": {"question": "search", "chat": "reply"}},
                    "search":   {"next": ["end"]},
                    "reply":    {"next": ["end"]},
                    "end":      {}
                }
            },
            "functions": {
                "greet":    {"step1": "Say hello"},
                "classify": {"step1": "Classify intent"},
                "search":   {"step1": "Search info"},
                "reply":    {"step1": "Chat reply"},
                "end":      {"step1": "Final output"}
            }
        }
    }
]

MIXED_FLOW = [
    {
        "role": "system",
        "content": {
            "protocol": "AISOP V1.0.0",
            "axiom_0": "Human_Sovereignty_and_Wellbeing",
            "id": "test_mixed",
            "name": "Mixed Flow Test",
            "flow_format": "hybrid",
            "version": "1.0.0"
        }
    },
    {
        "role": "user",
        "content": {
            "instruction": "RUN aisop.main",
            "user_input": "{user_input}",
            "aisop": {
                "main": "graph TD\n    start[Start] --> delegate[aisop.sub]\n    delegate --> end_node((End))",
                "sub": {
                    "check": {"next": ["done"]},
                    "done":  {}
                }
            },
            "functions": {
                "start":    {"step1": "Begin"},
                "delegate": {"step1": "Call sub"},
                "check":    {"step1": "Check"},
                "done":     {"step1": "Done"}
            }
        }
    }
]


def test_json_flow_validate():
    """JSON flow format passes validation."""
    validate(JSON_FLOW)
    print("  [PASS] json_flow: validation passes")


def test_json_flow_list_nodes():
    """JSON flow nodes are correctly listed with inferred types."""
    nodes = list_nodes(JSON_FLOW)
    names = [n["name"] for n in nodes]
    types = {n["name"]: n["type"] for n in nodes}
    assert "greet" in names
    assert "classify" in names
    assert types["classify"] == "decision"
    assert types["end"] == "end"
    assert types["greet"] == "process"
    print("  [PASS] json_flow: list_nodes correct")


def test_json_flow_render():
    """JSON flow render returns JSON string."""
    output = render_flow(JSON_FLOW)
    assert "greet" in output
    assert "classify" in output
    print("  [PASS] json_flow: render_flow correct")


def test_mixed_flow_validate():
    """Mixed flow (Mermaid main + JSON sub) passes validation."""
    validate(MIXED_FLOW)
    print("  [PASS] mixed_flow: validation passes")


def test_mixed_flow_list_nodes():
    """Mixed flow: Mermaid main and JSON sub both list correctly."""
    main_nodes = list_nodes(MIXED_FLOW, "main")
    sub_nodes = list_nodes(MIXED_FLOW, "sub")
    main_names = [n["name"] for n in main_nodes]
    sub_names = [n["name"] for n in sub_nodes]
    assert "start" in main_names
    assert "check" in sub_names
    assert {n["name"]: n["type"] for n in sub_nodes}["done"] == "end"
    print("  [PASS] mixed_flow: list_nodes both formats")


# ── sys.* System Call Tests ─────────────────────────────────

def test_classify_step_sys_call():
    """Steps starting with sys. are classified as sys_call."""
    assert classify_step("sys.io.confirm('Delete?')") == "sys_call"
    assert classify_step("sys.assert('x != null', 'fail')") == "sys_call"
    assert classify_step("sys.run('ls')") == "sys_call"
    assert classify_step("sys.code.exec('python', 'print(1)')") == "sys_call"
    print("  [PASS] classify_step: sys.* detected")


def test_classify_step_sub_task():
    """Steps starting with RUN aisop. are classified as sub_task."""
    assert classify_step("RUN aisop.extract_keywords") == "sub_task"
    assert classify_step("RUN aisop.main") == "sub_task"
    print("  [PASS] classify_step: RUN aisop.* detected")


def test_classify_step_natural_language():
    """Other steps are classified as natural_language."""
    assert classify_step("Say hello to the user") == "natural_language"
    assert classify_step("Classify user intent") == "natural_language"
    assert classify_step("Look up account details") == "natural_language"
    print("  [PASS] classify_step: natural language detected")


def test_parse_sys_call_confirm():
    """Parse sys.io.confirm call."""
    result = parse_sys_call("sys.io.confirm('Delete all data?')")
    assert result is not None
    assert result["name"] == "sys.io.confirm"
    assert "Delete all data?" in result["args"]
    assert result["store"] is None
    print("  [PASS] parse_sys_call: sys.io.confirm parsed")


def test_parse_sys_call_with_store():
    """Parse sys call with -> variable storage."""
    result = parse_sys_call("sys.io.input('Enter path') -> target_path")
    assert result is not None
    assert result["name"] == "sys.io.input"
    assert result["store"] == "target_path"
    print("  [PASS] parse_sys_call: -> store_var parsed")


def test_parse_sys_call_nested():
    """Parse three-level sys call like sys.code.exec."""
    result = parse_sys_call("sys.code.exec('python', 'data.sort()')")
    assert result is not None
    assert result["name"] == "sys.code.exec"
    assert "python" in result["args"]
    print("  [PASS] parse_sys_call: three-level name parsed")


def test_parse_sys_call_invalid():
    """Non-sys text returns None."""
    assert parse_sys_call("Say hello") is None
    assert parse_sys_call("RUN aisop.main") is None
    print("  [PASS] parse_sys_call: non-sys returns None")


def test_eval_expression_comparison():
    """Expression engine evaluates comparisons correctly."""
    ctx = {"count": 5, "threshold": 3}
    assert eval_expression("count > 0", ctx) is True
    assert eval_expression("count == 5", ctx) is True
    assert eval_expression("count < threshold", ctx) is False
    assert eval_expression("threshold >= 3", ctx) is True
    print("  [PASS] eval_expression: comparisons work")


def test_eval_expression_null_check():
    """Expression engine handles null checks."""
    ctx = {"account_id": "abc123"}
    assert eval_expression("account_id != null", ctx) is True
    ctx2 = {"account_id": None}
    assert eval_expression("account_id != null", ctx2) is False
    assert eval_expression("account_id == null", ctx2) is True
    print("  [PASS] eval_expression: null checks work")


def test_eval_expression_logical_and():
    """Expression engine handles && operator."""
    ctx = {"a": 5, "b": 10, "c": 3}
    assert eval_expression("a > 0 && b > 0", ctx) is True
    assert eval_expression("a > 0 && b < 0", ctx) is False
    assert eval_expression("a > 0 && b > 0 && c == 3", ctx) is True
    print("  [PASS] eval_expression: && operator works")


def test_eval_expression_logical_or():
    """Expression engine handles || operator."""
    ctx = {"status": 0, "fallback": 1}
    assert eval_expression("status > 0 || fallback > 0", ctx) is True
    assert eval_expression("status > 0 || fallback < 0", ctx) is False
    assert eval_expression("status == 0 || fallback == 0", ctx) is True
    print("  [PASS] eval_expression: || operator works")


def test_eval_expression_logical_not():
    """Expression engine handles ! operator."""
    ctx = {"done": False, "active": True}
    assert eval_expression("!done", ctx) is True
    assert eval_expression("!active", ctx) is False
    print("  [PASS] eval_expression: ! operator works")


def test_eval_expression_combined_logic():
    """Expression engine handles && and || together."""
    ctx = {"x": 5, "y": 0, "z": 10}
    # || has lower precedence: (x > 0 && y > 0) || z > 0
    assert eval_expression("x > 0 && y > 0 || z > 0", ctx) is True
    assert eval_expression("x > 0 && y == 0 || z < 0", ctx) is True
    print("  [PASS] eval_expression: combined && || works")


def test_parse_sys_call_validation():
    """parse_sys_call validates call names against VALID_SYS_CALLS."""
    result = parse_sys_call("sys.io.confirm('ok?')")
    assert result is not None
    assert result["valid"] is True

    result2 = parse_sys_call("sys.io.destroy('all')")
    assert result2 is not None
    assert result2["valid"] is False

    result3 = parse_sys_call("sys.run.bg('npm start') -> handle")
    assert result3 is not None
    assert result3["valid"] is True
    print("  [PASS] parse_sys_call: valid field checks VALID_SYS_CALLS")


def test_eval_expression_string_with_operators():
    """Expression engine handles strings containing || and && correctly."""
    ctx = {"msg": "ok || error"}
    assert eval_expression("msg == 'ok || error'", ctx) is True
    assert eval_expression("msg != 'ok || error'", ctx) is False
    ctx2 = {"status": "a && b"}
    assert eval_expression("status == 'a && b'", ctx2) is True
    print("  [PASS] eval_expression: strings with || && handled correctly")


def test_eval_expression_string_comparison():
    """Expression engine compares string literals correctly."""
    ctx = {"env": "production"}
    assert eval_expression("env == 'production'", ctx) is True
    assert eval_expression("env != 'staging'", ctx) is True
    assert eval_expression("env == 'staging'", ctx) is False
    print("  [PASS] eval_expression: string comparison works")


def test_valid_sys_calls_count():
    """VALID_SYS_CALLS contains exactly 24 entries."""
    from flow_runtime import VALID_SYS_CALLS
    assert len(VALID_SYS_CALLS) == 24, f"Expected 24, got {len(VALID_SYS_CALLS)}"
    assert "sys.run.bg" in VALID_SYS_CALLS
    assert "sys.io.confirm" in VALID_SYS_CALLS
    assert "sys.security.redact" in VALID_SYS_CALLS
    print("  [PASS] VALID_SYS_CALLS: contains all 24 entries")



# The exact JSON text is mirrored in the JavaScript suite; do not reorder members.
SUBGRAPH_CASES_TEXT = r'''[
{"id":"minimal","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{}}}],"standalone":true,"expected":[]},
{"id":"missing","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.missing"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_TARGET","location":"/user/content/aisop/main/start/functions/step1"}]},
{"id":"unresolved","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.missing"}}}}],"standalone":false,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_RESOLVER","location":"/user/content/aisop/main/start/functions/step1"}]},
{"id":"resolved","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.missing"}}}}],"standalone":false,"resolver":"true","expected":[]},
{"id":"not_resolved","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.missing"}}}}],"standalone":false,"resolver":"false","expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_TARGET","location":"/user/content/aisop/main/start/functions/step1"}]},
{"id":"bad_resolver","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.missing"}}}}],"standalone":false,"resolver":"invalid","expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_RESOLVER","location":"/user/content/aisop/main/start/functions/step1"}]},
{"id":"resolver_exception","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.missing"}}}}],"standalone":false,"resolver":"throw","expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_RESOLVER","location":"/user/content/aisop/main/start/functions/step1"}]},
{"id":"call_syntax","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.x trailing"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"old_index","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"aisop['x']"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"call_main","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.main"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_MAIN","location":"/user/content/aisop/main/start/functions/step1"}]},
{"id":"local_edge","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"next":["missing"]}}},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_LOCAL_EDGE","location":"/user/content/aisop/main/start/next/0"}]},
{"id":"format","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_FORMAT","location":"/user/content/aisop/main"}]},
{"id":"unused","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{}}}],"standalone":true,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_UNUSED","location":"/user/content/aisop/helper"}]},
{"id":"empty_graph","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{}},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_SHAPE","location":"/user/content/aisop/main"}]},
{"id":"single_mermaid","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nDone((End))"},"functions":{}}}],"standalone":true,"expected":[]},
{"id":"partial","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nStart((End))\nstyle Start fill:red"},"functions":{}}}],"standalone":true,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_PARSE_PARTIAL","location":"/user/content/aisop/main/line/3"}]},
{"id":"error_key","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"next":["done"]},"done":{}}},"functions":{"start":{"on_error":{"subgraph_not_found":"done"}}}}}],"standalone":true,"expected":[]},
{"id":"error_target","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"on_error":{"subgraph_not_found":"absent"}}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_LOCAL_EDGE","location":"/user/content/aisop/main/start/functions/on_error/subgraph_not_found"}]},
{"id":"null_input","data":null,"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_SHAPE","location":"/"}]},
{"id":"array_message","data":[[],{}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_SHAPE","location":"/"}]},
{"id":"null_functions","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":null}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_SHAPE","location":"/user/content/functions"}]},
{"id":"null_function","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":null}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_SHAPE","location":"/user/content/functions/start"}]},
{"id":"null_node","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":null}},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_SHAPE","location":"/user/content/aisop/main/start"}]},
{"id":"null_graph","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":null},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_SHAPE","location":"/user/content/aisop/main"}]},
{"id":"container_not_graph","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"sub":"graph TD\nA((End))"}},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_SHAPE","location":"/user/content/aisop/main/sub"}]},
{"id":"unicode_node","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"中文":{}}},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_NAME","location":"/user/content/aisop/main/中文"}]},
{"id":"invalid_graph_name","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"bad-name":{"finish":{}}},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_NAME","location":"/user/content/aisop/bad-name"},{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_UNUSED","location":"/user/content/aisop/bad-name"}]},
{"id":"missing_main","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_SHAPE","location":"/user/content/aisop"}]},
{"id":"bad_store","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.x -> bad-name"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"multiline_call","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.x\nextra"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"arbitrary_step_key","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"summary":"RUN aisop.missing"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_FUNCTION_KEY","location":"/user/content/functions/start/summary"}]},
{"id":"metadata_not_step","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow","summary":"RUN aisop.missing"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{}}}],"standalone":true,"expected":[]},
{"id":"reserved_not_step","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"context_filter":{"include":["RUN aisop.missing"]}}}}}],"standalone":true,"expected":[]},
{"id":"local_before_resolver","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"delegate_to":"helper"}},"helper":{"done":{}}},"functions":{}}}],"standalone":false,"expected":[],"resolver":"throw","expected_queries":[]},
{"id":"standalone_blocks_resolver","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.ext"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_TARGET","location":"/user/content/aisop/main/start/functions/step1"}],"resolver":"throw","expected_queries":[]},
{"id":"explicit_repeats_not_merged","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"delegate_to":"ext"}}},"functions":{"start":{"step1":"RUN aisop.ext -> value","step2":"RUN aisop.ext"}}}}],"standalone":false,"expected":[],"resolver":"true","expected_queries":["ext","ext"]},
{"id":"other_target_preparation","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"delegate_to":"ext"}}},"functions":{"start":{"step1":"RUN aisop.prepare"}}}}],"standalone":false,"expected":[],"resolver":"true","expected_queries":["prepare","ext"]},
{"id":"shared_call_ownership","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"next":["work"]},"work":{"next":["mainend"]},"mainend":{}},"helper":{"substart":{"next":["work"]},"work":{"next":["subend"]},"subend":{}}},"functions":{"start":{"step1":"RUN aisop.helper"},"work":{"step1":"RUN aisop.ext"}}}}],"standalone":false,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_NODE_REUSE","location":"/user/content/aisop/node_reuse/work"}],"resolver":"true","expected_queries":["ext","ext"]},
{"id":"active_join_suppresses","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"A":{"next":["sync"]},"B":{"next":["sync"]},"sync":{}}},"functions":{"sync":{"step1":"RUN aisop.missing","join":{}}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_TARGET","location":"/user/content/aisop/main/sync/functions/step1"}]},
{"id":"inactive_join_keeps_call","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"A":{"next":["sync"]},"sync":{}}},"functions":{"sync":{"step1":"RUN aisop.missing","join":{}}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_TARGET","location":"/user/content/aisop/main/sync/functions/step1"}]},
{"id":"map_suppresses","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.missing","map":{"items_path":"items","iterator":"work"}},"work":{"step1":"Read the item"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_TARGET","location":"/user/content/aisop/main/start/functions/step1"}]},
{"id":"suppressed_syntax_still_checked","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.missing trailing","map":{"iterator":"work"}},"work":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"delegate_map_conflict","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"delegate_to":"helper"}},"helper":{"done":{}}},"functions":{"start":{"map":{"iterator":"work"}},"work":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CONFLICT","location":"/user/content/aisop/main/start"}]},
{"id":"shared_error_target_local","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"mstart":{"next":["same"]},"same":{},"recover":{}},"helper":{"same":{},"hend":{}}},"functions":{"mstart":{"step1":"RUN aisop.helper"},"same":{"on_error":{"default":"recover"}}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_LOCAL_EDGE","location":"/user/content/aisop/helper/same/functions/on_error/default"}]},
{"id":"self_call_cycle","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"delegate_to":"helper"}},"helper":{"hn":{}}},"functions":{"hn":{"step1":"RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CYCLE","location":"/user/content/aisop/helper/calls/helper"}]},
{"id":"mutual_call_cycle","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"delegate_to":"alpha"}},"alpha":{"a":{}},"beta":{"b":{}}},"functions":{"a":{"step1":"RUN aisop.beta"},"b":{"step1":"RUN aisop.alpha"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CYCLE","location":"/user/content/aisop/alpha/calls/beta"},{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CYCLE","location":"/user/content/aisop/beta/calls/alpha"}]},
{"id":"control_flow_loop","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"A":{"next":["B"]},"B":{"next":["A"]}}},"functions":{}}}],"standalone":true,"expected":[]},
{"id":"all_entry_reuse","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"shared":{"next":["mend"]},"mend":{}},"helper":{"shared":{"next":["send"]},"send":{}}},"functions":{"mend":{"step1":"RUN aisop.helper"}}}}],"standalone":true,"expected":[]},
{"id":"all_end_single_node_reuse","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"next":["shared"]},"shared":{}},"helper":{"shared":{}}},"functions":{"start":{"step1":"RUN aisop.helper"}}}}],"standalone":true,"expected":[]},
{"id":"mixed_role_reuse","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"shared":{"next":["mend"]},"mend":{}},"helper":{"hstart":{"next":["shared"]},"shared":{"next":["hend"]},"hend":{}}},"functions":{"mend":{"step1":"RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_NODE_REUSE","location":"/user/content/aisop/node_reuse/shared"}]},
{"id":"unknown_entry_no_exemption","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nunsupported line\nShared[Read]\nEnd((End))","helper":"graph TD\nShared[Read]\nDone((End))"},"functions":{}}}],"standalone":true,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_PARSE_PARTIAL","location":"/user/content/aisop/main/line/2"},{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_PARSE_PARTIAL","location":"/user/content/aisop/node_reuse/Shared"}]},
{"id":"partial_missing_graph_still_error","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nStart[Read]\nstyle Start fill:red"},"functions":{"Start":{"step1":"RUN aisop.missing"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_TARGET","location":"/user/content/aisop/main/line/2/node/Start/functions/step1"},{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_PARSE_PARTIAL","location":"/user/content/aisop/main/line/3"}]},
{"id":"quoted_mermaid_tokens","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nA[\"a --> b & c | [x]\"] --> B((End))"},"functions":{}}}],"standalone":true,"expected":[]},
{"id":"quoted_long_edge","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nA -- \"x|& --> y\" --> B((End))"},"functions":{}}}],"standalone":true,"expected":[]},
{"id":"grouped_endpoints","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nA & B --> C & D"},"functions":{}}}],"standalone":true,"expected":[]},
{"id":"run_label_rejected","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nA[RUN aisop.helper]"},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/aisop/main/line/2/node/A"}]},
{"id":"prefixed_delegate_rejected","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"delegate_to":"aisop.helper"}}},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/aisop/main/start/delegate_to"}]},
{"id":"valid_call_store","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"Prepare","step2":"RUN aisop.helper -> result","step3":"Use result"}}}}],"standalone":true,"expected":[]},
{"id":"wait_for_local","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"wait_for":["missing"]}}},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_LOCAL_EDGE","location":"/user/content/aisop/main/start/wait_for/0"}]},
{"id":"bad_branch_type","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"branches":[]}}},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_SHAPE","location":"/user/content/aisop/main/start/branches"}]},
{"id":"blank_lines_crlf","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"\r\n\r\ngraph TD\r\nA((End))\r\nstyle A fill:red"},"functions":{}}}],"standalone":true,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_PARSE_PARTIAL","location":"/user/content/aisop/main/line/5"}]},
{"id":"json_safe_own_keys","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"__proto__":{"next":["toString"]},"toString":{}},"constructor":{"done":{}}},"functions":{"__proto__":{"step1":"RUN aisop.constructor"}}}}],"standalone":true,"expected":[]},
{"id":"end_function_steps_preserved","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"subgraph_test","name":"Subgraph Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"next":["done"]},"done":{}}},"functions":{"done":{"step1":"sys.io.confirm('Confirm completion?')","step2":"Publish final output"}}}}],"standalone":true,"expected":[]}
,
{"id":"rev_apostrophe_node","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nask[Don't stop] --> done((End))"},"functions":{"ask":{"step1":"Read"},"done":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_apostrophe_pipe","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[Read] -->|user's pick| b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_apostrophe_long","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na -- it's ok --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_internal_double","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[He said \"go\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_plan_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"say \\\"go\\\"\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_plan_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"path\\\\\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_plan_3","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[ \"x ] y\" ] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_plan_4","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na -- \" x \" --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_plan_5","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"path\\\"] --> b((End))\nkept((End))"},"functions":{"kept":{"step1":"Finish"}}}}],"standalone":true,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_PARSE_PARTIAL","location":"/user/content/aisop/main/line/2"}]},
{"id":"rev_empty_partial","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"path\\\"] --> b((End))"},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_SHAPE","location":"/user/content/aisop/main"},{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_PARSE_PARTIAL","location":"/user/content/aisop/main/line/2"}]},
{"id":"rev_missing_handler","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nask[Don't stop] --> done((End))"},"functions":{"ask":{"step1":"Read","on_error":{"default":"missing_handler"}},"done":{"step1":"Finish"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_LOCAL_EDGE","location":"/user/content/aisop/main/line/2/node/ask/functions/on_error/default"}]},
{"id":"rev_present_handler","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nask[Don't stop] --> done((End))"},"functions":{"ask":{"step1":"Read","on_error":{"default":"done"}},"done":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_unused_restored","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nask[Don't stop] --> done((End))","helper":"graph TD\nhEnd((End))"},"functions":{"ask":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_UNUSED","location":"/user/content/aisop/helper"}]},
{"id":"rev_delegate_preserved","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nintake[User's request] --> d[aisop.diag]","diag":"graph TD\ndiagEnd((End))"},"functions":{"intake":{"step1":"Read"},"d":{"step1":"Prepare"}}}}],"standalone":true,"expected":[],"resolver":"throw","expected_queries":[]},
{"id":"rev_partial_preserved","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[Don't stop] --> b((End))\nstyle a fill:red"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_PARSE_PARTIAL","location":"/user/content/aisop/main/line/3"}]},
{"id":"rev_partial_definite","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[Don't stop] --> b((End))\nstyle a fill:red"},"functions":{"a":{"step1":"RUN aisop.absent"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_TARGET","location":"/user/content/aisop/main/line/2/node/a/functions/step1"},{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_PARSE_PARTIAL","location":"/user/content/aisop/main/line/3"}]},
{"id":"rev_cross_graph_error","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[Don't stop] --> b((End))\nstyle a fill:red","helper":"graph TD\nh[Work] --> hend((End))"},"functions":{"a":{"step1":"RUN aisop.helper"},"h":{"on_error":{"default":"absent"}}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_LOCAL_EDGE","location":"/user/content/aisop/helper/line/2/node/h/functions/on_error/default"},{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_PARSE_PARTIAL","location":"/user/content/aisop/main/line/3"}]},
{"id":"rev_bad_delegate_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[aisop.helper extra] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/aisop/main/line/2/node/a"}]},
{"id":"rev_bad_delegate_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[aisop.my-graph] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/aisop/main/line/2/node/a"}]},
{"id":"rev_bad_delegate_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"aisop.helper extra\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/aisop/main/line/2/node/a"}]},
{"id":"rev_good_delegate_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[aisop.helper] --> b((End))","helper":"graph TD\nhEnd((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[],"resolver":"throw","expected_queries":[]},
{"id":"rev_good_delegate_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"aisop.helper\"] --> b((End))","helper":"graph TD\nhEnd((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[],"resolver":"throw","expected_queries":[]},
{"id":"rev_ordinary_label_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[Review aisop.helper] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ordinary_label_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na{aisop.helper extra} --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ordinary_label_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na((aisop.helper extra)) --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ordinary_label_3","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[ \"aisop.helper\" ] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/aisop/main/line/2/node/a"}]},
{"id":"rev_ordinary_label_4","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"x\" ] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ordinary_label_5","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"'x'\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_bad_wrapper_34","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"x\" extra] --> b((End))\nkept((End))"},"functions":{"kept":{"step1":"Finish"}}}}],"standalone":true,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_PARSE_PARTIAL","location":"/user/content/aisop/main/line/2"}]},
{"id":"rev_bad_wrapper_39","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na['x' extra] --> b((End))\nkept((End))"},"functions":{"kept":{"step1":"Finish"}}}}],"standalone":true,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_PARSE_PARTIAL","location":"/user/content/aisop/main/line/2"}]},
{"id":"rev_mixed_0_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch,RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_mixed_0_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch,\u00a0RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_mixed_0_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch,\ufeffRUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_mixed_1_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch;RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_mixed_1_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch;\u00a0RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_mixed_1_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch;\ufeffRUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_mixed_2_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch\uff0cRUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_mixed_2_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch\uff0c\u00a0RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_mixed_2_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch\uff0c\ufeffRUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_mixed_3_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch\uff1bRUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_mixed_3_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch\uff1b\u00a0RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_mixed_3_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch\uff1b\ufeffRUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_mixed_4_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch\u3001RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_mixed_4_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch\u3001\u00a0RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_mixed_4_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Fetch\u3001\ufeffRUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_literal_prose","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Explain the literal \"RUN aisop.helper\""}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_9","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\tRUN aisop.helper -> result\t"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_10","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\nRUN aisop.helper -> result\n"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_11","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u000bRUN aisop.helper -> result\u000b"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_12","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\fRUN aisop.helper -> result\f"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_13","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\rRUN aisop.helper -> result\r"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_32","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":" RUN aisop.helper -> result "}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_160","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u00a0RUN aisop.helper -> result\u00a0"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_5760","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u1680RUN aisop.helper -> result\u1680"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8192","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u2000RUN aisop.helper -> result\u2000"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8193","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u2001RUN aisop.helper -> result\u2001"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8194","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u2002RUN aisop.helper -> result\u2002"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8195","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u2003RUN aisop.helper -> result\u2003"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8196","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u2004RUN aisop.helper -> result\u2004"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8197","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u2005RUN aisop.helper -> result\u2005"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8198","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u2006RUN aisop.helper -> result\u2006"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8199","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u2007RUN aisop.helper -> result\u2007"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8200","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u2008RUN aisop.helper -> result\u2008"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8201","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u2009RUN aisop.helper -> result\u2009"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8202","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u200aRUN aisop.helper -> result\u200a"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8232","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u2028RUN aisop.helper -> result\u2028"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8233","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u2029RUN aisop.helper -> result\u2029"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8239","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u202fRUN aisop.helper -> result\u202f"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_8287","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u205fRUN aisop.helper -> result\u205f"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_call_12288","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"\u3000RUN aisop.helper -> result\u3000"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_graph_9","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph\tTD\n\ta[Read] --> b((End))\t"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_graph_11","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph\u000bTD\n\u000ba[Read] --> b((End))\u000b"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_graph_12","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph\fTD\n\fa[Read] --> b((End))\f"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_graph_160","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph\u00a0TD\n\u00a0a[Read] --> b((End))\u00a0"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_graph_12288","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph\u3000TD\n\u3000a[Read] --> b((End))\u3000"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_graph_8232","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph\u2028TD\n\u2028a[Read] --> b((End))\u2028"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_ws_graph_8233","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph\u2029TD\n\u2029a[Read] --> b((End))\u2029"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_bad_gap_9","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN\taisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_bad_gap_160","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN\u00a0aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_bad_gap_12288","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN\u3000aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_bad_gap_8232","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN\u2028aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_bad_gap_8233","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN\u2029aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_bad_double_space","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN  aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_bad_store_gap","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.helper ->\u00a0result"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_bad_boundary_28","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"\u001cRUN aisop.helper\u001c"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_bad_token_28","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN\u001caisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_label_data_28","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"left\u001cright\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_bad_boundary_29","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"\u001dRUN aisop.helper\u001d"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_bad_token_29","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN\u001daisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_label_data_29","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"left\u001dright\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_bad_boundary_30","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"\u001eRUN aisop.helper\u001e"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_bad_token_30","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN\u001eaisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_label_data_30","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"left\u001eright\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_bad_boundary_31","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"\u001fRUN aisop.helper\u001f"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_bad_token_31","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN\u001faisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_label_data_31","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"left\u001fright\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_bad_boundary_133","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"\u0085RUN aisop.helper\u0085"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_bad_token_133","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN\u0085aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_label_data_133","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"left\u0085right\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_bad_boundary_65279","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"\ufeffRUN aisop.helper\ufeff"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_bad_token_65279","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN\ufeffaisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"rev_label_data_65279","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"left\ufeffright\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_bad_name_bom","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nbad\ufeffid[Read] --> b((End))"},"functions":{}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_NAME","location":"/user/content/aisop/main/line/2/node/bad\ufeffid"}]},
{"id":"rev_label_space_160","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"left\u00a0right\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_label_space_12288","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"left\u3000right\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_label_space_8232","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"left\u2028right\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"rev_label_space_8233","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"smallfix_test","name":"Small Fix Test","version":"1.0.0","flow_format":"mermaid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"left\u2029right\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{"step1":"Finish"}}}}],"standalone":true,"expected":[]},
{"id":"semantic_join_local","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"semantic_test","name":"Semantic Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"A":{"next":["sync"]},"B":{"next":["sync"]},"sync":{}},"helper":{"done":{}}},"functions":{"sync":{"step1":"RUN aisop.helper","join":{}}}}}],"standalone":true,"expected":[]},
{"id":"semantic_join_cycle","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"semantic_test","name":"Semantic Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"A":{"next":["sync"]},"B":{"next":["sync"]},"sync":{}},"helper":{"helper_node":{}}},"functions":{"sync":{"step1":"RUN aisop.helper","join":{}},"helper_node":{"step1":"RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CYCLE","location":"/user/content/aisop/helper/calls/helper"}]},
{"id":"semantic_map_local","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"semantic_test","name":"Semantic Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"step1":"RUN aisop.helper","map":{"items_path":"items","iterator":"work"}},"work":{"step1":"Read the item"}}}}],"standalone":true,"expected":[]},
{"id":"semantic_map_default_resolver","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"semantic_test","name":"Semantic Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.missing","map":{"items_path":"items","iterator":"work"}},"work":{"step1":"Read the item"}}}}],"standalone":false,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_RESOLVER","location":"/user/content/aisop/main/start/functions/step1"}]},
{"id":"semantic_partial_join_step","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"semantic_test","name":"Semantic Test","version":"1.0.0","flow_format":"hybrid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\nstart[Read] --> done((End))\nclassDef custom fill:red","helper":{"helper_node":{}}},"functions":{"start":{"step1":"RUN aisop.missing","join":{}}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_TARGET","location":"/user/content/aisop/main/line/2/node/start/functions/step1"},{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_PARSE_PARTIAL","location":"/user/content/aisop/main/line/3"}]},
{"id":"semantic_map_indirect","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"semantic_test","name":"Semantic Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}},"other":{"other_node":{}}},"functions":{"start":{"step1":"RUN aisop.helper","map":{"items_path":"items","iterator":"work"}},"work":{"step1":"RUN aisop.other"}}}}],"standalone":true,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_PARSE_PARTIAL","location":"/user/content/aisop/main/start"}]},
{"id":"semantic_conflict_and_target","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"semantic_test","name":"Semantic Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{"delegate_to":"helper"}},"helper":{"done":{}}},"functions":{"start":{"step1":"RUN aisop.missing","map":{"items_path":"items","iterator":"work"}},"work":{"step1":"Read the item"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CONFLICT","location":"/user/content/aisop/main/start"},{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_TARGET","location":"/user/content/aisop/main/start/functions/step1"}]},
{"id":"semantic_map_resolver_false","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"semantic_test","name":"Semantic Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.missing","map":{"items_path":"items","iterator":"work"}},"work":{"step1":"Read the item"}}}}],"standalone":false,"resolver":"false","expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_TARGET","location":"/user/content/aisop/main/start/functions/step1"}]},
{"id":"semantic_map_resolver_true","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"semantic_test","name":"Semantic Test","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"RUN aisop.missing","map":{"items_path":"items","iterator":"work"}},"work":{"step1":"Read the item"}}}}],"standalone":false,"resolver":"true","expected":[]},
{"id":"semantic_join_edge_cycle","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"join_edge_cycle","name":"Join Edge Cycle","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"launch":{"delegate_to":"alpha","next":["main_done"]},"main_done":{}},"alpha":{"alpha_entry":{"next":["alpha_left","alpha_right"]},"alpha_left":{"next":["alpha_join"]},"alpha_right":{"next":["alpha_join"]},"alpha_join":{"next":["alpha_done"]},"alpha_done":{}},"beta":{"beta_entry":{"next":["beta_done"]},"beta_done":{}}},"functions":{"alpha_join":{"step1":"RUN aisop.beta","join":{}},"beta_entry":{"step1":"RUN aisop.alpha"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CYCLE","location":"/user/content/aisop/alpha/calls/beta"},{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CYCLE","location":"/user/content/aisop/beta/calls/alpha"}]}
,
{"id":"stage1_step_numeric_order","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step10":"RUN aisop.ten","step2":"RUN aisop.two"}}}}],"standalone":false,"expected":[],"resolver":"true","expected_queries":["two","ten"]},
{"id":"stage1_step_large_order","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step999999999999999999999999999999":"RUN aisop.large","step100":"RUN aisop.middle","step9":"RUN aisop.small"}}}}],"standalone":false,"expected":[],"resolver":"true","expected_queries":["small","middle","large"]},
{"id":"stage1_unknown_step0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step0":"RUN aisop.missing"}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_FUNCTION_KEY","location":"/user/content/functions/start/step0"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_unknown_step01","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step01":"RUN aisop.missing"}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_FUNCTION_KEY","location":"/user/content/functions/start/step01"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_unknown_Step1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"Step1":"RUN aisop.missing"}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_FUNCTION_KEY","location":"/user/content/functions/start/Step1"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_unknown_summary","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"summary":"RUN aisop.missing"}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_FUNCTION_KEY","location":"/user/content/functions/start/summary"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_unknown_step","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step":"RUN aisop.missing"}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_FUNCTION_KEY","location":"/user/content/functions/start/step"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_unknown_step1x","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1x":"RUN aisop.missing"}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_FUNCTION_KEY","location":"/user/content/functions/start/step1x"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_unknown_stepx2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step-2":"RUN aisop.missing"}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_FUNCTION_KEY","location":"/user/content/functions/start/step-2"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_unknown_step_newline","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1\n":"RUN aisop.missing"}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_FUNCTION_KEY","location":"/user/content/functions/start/step1\n"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_step_value_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":null}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_STEP_VALUE","location":"/user/content/functions/start/step1"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_step_value_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":1}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_STEP_VALUE","location":"/user/content/functions/start/step1"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_step_value_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":false}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_STEP_VALUE","location":"/user/content/functions/start/step1"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_step_value_3","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":{}}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_STEP_VALUE","location":"/user/content/functions/start/step1"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_step_value_4","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":[]}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_STEP_VALUE","location":"/user/content/functions/start/step1"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_step_value_5","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":""}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_STEP_VALUE","location":"/user/content/functions/start/step1"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_step_value_6","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":" \t\n"}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_STEP_VALUE","location":"/user/content/functions/start/step1"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_step_value_7","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"\u00a0\u3000"}}}}],"standalone":false,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_STEP_VALUE","location":"/user/content/functions/start/step1"}],"resolver":"true","expected_queries":[]},
{"id":"stage1_invalid_unknown_independent","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}},"helper":{"done":{}}},"functions":{"start":{"summary":"RUN aisop.helper","step2":"RUN aisop.missing"}}}}],"standalone":true,"expected":[{"severity":"WARNING","code":"AISOP_W_SUBGRAPH_UNUSED","location":"/user/content/aisop/helper"},{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_TARGET","location":"/user/content/aisop/main/start/functions/step2"},{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_FUNCTION_KEY","location":"/user/content/functions/start/summary"}]},
{"id":"stage1_unknown_confirmation","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"confirm":"sys.io.confirm('Approve?')"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_FUNCTION_KEY","location":"/user/content/functions/start/confirm"}]},
{"id":"stage1_mode_inline","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"execute_mode":"inline"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mode_agent","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"execute_mode":"agent"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mode_missing_zero_steps","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mode_bad_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"execute_mode":null}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_EXECUTE_MODE","location":"/user/content/functions/start/execute_mode"}]},
{"id":"stage1_mode_bad_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"execute_mode":0}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_EXECUTE_MODE","location":"/user/content/functions/start/execute_mode"}]},
{"id":"stage1_mode_bad_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"execute_mode":false}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_EXECUTE_MODE","location":"/user/content/functions/start/execute_mode"}]},
{"id":"stage1_mode_bad_3","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"execute_mode":[]}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_EXECUTE_MODE","location":"/user/content/functions/start/execute_mode"}]},
{"id":"stage1_mode_bad_4","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"execute_mode":{}}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_EXECUTE_MODE","location":"/user/content/functions/start/execute_mode"}]},
{"id":"stage1_mode_bad_5","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"execute_mode":""}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_EXECUTE_MODE","location":"/user/content/functions/start/execute_mode"}]},
{"id":"stage1_mode_bad_6","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"execute_mode":"INLINE"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_EXECUTE_MODE","location":"/user/content/functions/start/execute_mode"}]},
{"id":"stage1_mode_bad_7","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"execute_mode":"Agent"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_EXECUTE_MODE","location":"/user/content/functions/start/execute_mode"}]},
{"id":"stage1_mode_bad_8","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"execute_mode":" agent "}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_EXECUTE_MODE","location":"/user/content/functions/start/execute_mode"}]},
{"id":"stage1_mode_bad_9","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"execute_mode":"inline\n"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_EXECUTE_MODE","location":"/user/content/functions/start/execute_mode"}]},
{"id":"stage1_mode_unreachable","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"},"uncalled":{"execute_mode":null}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_EXECUTE_MODE","location":"/user/content/functions/uncalled/execute_mode"}]},
{"id":"stage1_params_empty","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_params_string","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":"string"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_params_number","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":"number"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_params_boolean","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":"boolean"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_params_array","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":"array"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_params_object","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":"object"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_params_null","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":"null"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_params_container_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":null}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params"}]},
{"id":"stage1_params_container_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":[]}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params"}]},
{"id":"stage1_params_container_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":0}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params"}]},
{"id":"stage1_params_container_3","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":false}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params"}]},
{"id":"stage1_params_container_4","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":"string"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params"}]},
{"id":"stage1_params_value_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":null}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/value"}]},
{"id":"stage1_params_value_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":0}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/value"}]},
{"id":"stage1_params_value_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":true}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/value"}]},
{"id":"stage1_params_value_3","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":[]}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/value"}]},
{"id":"stage1_params_value_4","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":{}}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/value"}]},
{"id":"stage1_params_value_5","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":"integer"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/value"}]},
{"id":"stage1_params_value_6","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":"String"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/value"}]},
{"id":"stage1_params_value_7","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":" string "}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/value"}]},
{"id":"stage1_params_value_8","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":"en"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/value"}]},
{"id":"stage1_params_value_9","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":"friendly"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/value"}]},
{"id":"stage1_params_value_10","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"value":"production"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/value"}]},
{"id":"stage1_params_name_null","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"null":"string"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/null"}]},
{"id":"stage1_params_name_true","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"true":"string"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/true"}]},
{"id":"stage1_params_name_false","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"false":"string"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/false"}]},
{"id":"stage1_params_name_bad-name","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"bad-name":"string"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/bad-name"}]},
{"id":"stage1_params_name_0name","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"0name":"string"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/0name"}]},
{"id":"stage1_params_name_empty","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"":"string"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_PARAMS","location":"/system/content/params/"}]},
{"id":"stage1_params_own_safe_keys","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow","params":{"__proto__":"object","constructor":"string"}}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Read"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_delegate_bad_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"hybrid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[ aisop.helper ] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/aisop/main/line/2/node/a"}]},
{"id":"stage1_delegate_bad_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"hybrid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[ \"aisop.helper\" ] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/aisop/main/line/2/node/a"}]},
{"id":"stage1_delegate_bad_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"hybrid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\ufeffaisop.helper] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/aisop/main/line/2/node/a"}]},
{"id":"stage1_delegate_bad_3","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"hybrid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[aisop.helper extra] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/aisop/main/line/2/node/a"}]},
{"id":"stage1_delegate_bad_4","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"hybrid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[' aisop.helper '] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/aisop/main/line/2/node/a"}]},
{"id":"stage1_delegate_quote_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"hybrid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\"'aisop.helper'\"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{}}}}],"standalone":true,"expected":[]},
{"id":"stage1_delegate_quote_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"hybrid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[\" aisop.helper \"] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/aisop/main/line/2/node/a"}]},
{"id":"stage1_delegate_quote_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"hybrid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na[left aisop.helper] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{}}}}],"standalone":true,"expected":[]},
{"id":"stage1_delegate_quote_3","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"hybrid"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":"graph TD\na['\"aisop.helper\"'] --> b((End))"},"functions":{"a":{"step1":"Read"},"b":{}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mixed_bad_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Explain then RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"stage1_mixed_bad_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Prepare.RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"stage1_mixed_bad_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"\u5148\u51c6\u5907\u3002RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"stage1_mixed_bad_3","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"\u8bf4\u660e\uff1aRUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"stage1_mixed_bad_4","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"\u5148\u51c6\u5907RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"stage1_mixed_bad_5","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Don't deploy RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"stage1_mixed_bad_6","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"sys.io.print('ok'); RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"stage1_mixed_bad_7","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Say \"unclosed RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"stage1_mixed_bad_8","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Explain RUN aisop.helper -> 0bad"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"stage1_mixed_bad_9","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Explain RUN aisop.helper.tail"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"stage1_mixed_bad_10","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Say \\\"RUN aisop.helper\\\""}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"stage1_mixed_literal_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Explain the literal \"RUN aisop.helper\""}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mixed_literal_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Explain the literal 'RUN aisop.helper'"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mixed_literal_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"sys.io.print(\"\u8bf4\u660e\uff1aRUN aisop.helper\")"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mixed_literal_3","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"fooRUN aisop.helper"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mixed_literal_4","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"foo_RUN aisop.helper"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mixed_literal_5","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"https://example.test/file:1.2"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mixed_literal_6","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Don't stop"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mixed_literal_7","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"user's text"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mixed_literal_8","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Say \"escaped \\\"RUN aisop.helper\\\" text\""}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mixed_literal_9","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Say \"path\\\\\" and continue"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mixed_escape_0","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Say \"path\\\\\" RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"stage1_mixed_escape_1","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Say \"path\\\\\\\" RUN aisop.helper\""}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mixed_escape_2","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Say 'it\\'s RUN aisop.helper'"}}}}],"standalone":true,"expected":[]},
{"id":"stage1_mixed_escape_3","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Say 'path\\\\' RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]},
{"id":"stage1_mixed_escape_4","data":[{"role":"system","content":{"protocol":"AISOP V1.0.0","axiom_0":"Human_Sovereignty_and_Wellbeing","id":"stage1_test","name":"Stage One","version":"1.0.0","flow_format":"jsonflow"}},{"role":"user","content":{"instruction":"RUN aisop.main","aisop":{"main":{"start":{}}},"functions":{"start":{"step1":"Say 'unfinished RUN aisop.helper"}}}}],"standalone":true,"expected":[{"severity":"ERROR","code":"AISOP_E_SUBGRAPH_CALL_SYNTAX","location":"/user/content/functions/start/step1"}]}
]'''
SUBGRAPH_CASES = json.loads(SUBGRAPH_CASES_TEXT)


def test_subgraph_contract_cases():
    from flow_runtime import check
    for case in SUBGRAPH_CASES:
        queries = []
        def resolver(target):
            queries.append(target)
            if case.get("resolver") == "throw":
                raise ValueError("Expected resolver exception")
            return {"true": True, "false": False, "invalid": "true"}.get(case.get("resolver"))
        before = json.dumps(case["data"], ensure_ascii=False)
        actual = check(case["data"], resolver if "resolver" in case else None, case["standalone"])
        diagnostics = [{key: item[key] for key in ("severity", "code", "location")} for item in actual]
        assert all(isinstance(item.get("message"), str) for item in actual), case["id"]
        assert diagnostics == case["expected"], (case["id"], diagnostics, case["expected"])
        assert before == json.dumps(case["data"], ensure_ascii=False), case["id"]
        if "expected_queries" in case:
            assert queries == case["expected_queries"], (case["id"], queries)
    print(f"  [PASS] subgraphs: {len(SUBGRAPH_CASES)} independent diagnostic cases and resolver positions")


def test_subgraph_call_api():
    from flow_runtime import parse_call, list_graphs
    assert parse_call(" RUN aisop.extract -> result ") == {"target": "extract", "store": "result"}
    assert parse_call("RUN aisop.extract") == {"target": "extract", "store": None}
    for value in (None, [], "RUN aisop.中文", "RUN aisop.x extra", "RUN aisop.x -> 0bad", "RUN aisop.x\nRUN aisop.y"):
        assert parse_call(value) is None, value
    data = json.loads(SUBGRAPH_CASES_TEXT)[12]["data"]
    assert list_graphs(data) == [{"name": "main", "format": "jsonflow"}, {"name": "helper", "format": "jsonflow"}]
    for case in SUBGRAPH_CASES:
        if case["id"].startswith("rev_ws_call_"):
            step = case["data"][1]["content"]["functions"]["start"]["step1"]
            assert parse_call(step) == {"target": "helper", "store": "result"}, case["id"]
        elif case["id"].startswith(("rev_bad_gap_", "rev_bad_boundary_", "rev_bad_token_", "rev_mixed_")) or case["id"] in ("rev_bad_double_space", "rev_bad_store_gap"):
            step = case["data"][1]["content"]["functions"]["start"]["step1"]
            assert parse_call(step) is None, case["id"]
    print("  [PASS] subgraphs: call and graph-list APIs")


def test_subgraph_mermaid_subset():
    for edge, key in (("-->", "next"), ("-->|yes|", "branches"), ("--> |yes|", "branches"), ("-- yes -->", "branches"), ("-.->", "error")):
        parsed = parse_mermaid("graph TD\nA[Read] " + edge + " B((End))")
        value = parsed["nodes"]["A"][key]
        assert value == (["B"] if key == "next" else {"yes": "B"} if key == "branches" else "B")
        assert parsed["node_types"]["B"] == "end"
    grouped = parse_mermaid("graph TD\nA & B --> C & D")["nodes"]
    assert grouped["A"]["next"] == grouped["B"]["next"] == ["C", "D"]
    quoted = parse_mermaid('graph TD\nA["a --> b & c | [x]"] --> B((End))')
    assert quoted["node_labels"]["A"] == "a --> b & c | [x]"
    assert list(parse_mermaid("graph TD\nOnly((End))")["nodes"]) == ["Only"]
    for case_id, label in (
        ("rev_plan_1", "say \\\"go\\\""),
        ("rev_plan_2", "path\\\\"),
        ("rev_plan_3", ' "x ] y" '),
        ("rev_internal_double", 'He said "go"'),
        ("rev_apostrophe_long", None),
    ):
        case = next(item for item in SUBGRAPH_CASES if item["id"] == case_id)
        parsed = parse_mermaid(case["data"][1]["content"]["aisop"]["main"])
        assert list(parsed["nodes"]) == ["a", "b"], case_id
        if label is not None:
            assert parsed["node_labels"]["a"] == label, case_id
            assert parsed["nodes"]["a"]["next"] == ["b"], case_id
        else:
            assert parsed["nodes"]["a"]["branches"] == {"it's ok": "b"}, case_id
    for case_id, label in (("rev_plan_4", " x "), ("rev_apostrophe_pipe", "user's pick")):
        case = next(item for item in SUBGRAPH_CASES if item["id"] == case_id)
        parsed = parse_mermaid(case["data"][1]["content"]["aisop"]["main"])
        assert list(parsed["nodes"]) == ["a", "b"], case_id
        assert parsed["nodes"]["a"]["branches"] == {label: "b"}, case_id
    case = next(item for item in SUBGRAPH_CASES if item["id"] == "rev_plan_5")
    assert list(parse_mermaid(case["data"][1]["content"]["aisop"]["main"])["nodes"]) == ["kept"]
    for case in SUBGRAPH_CASES:
        if case["id"].startswith(("rev_label_space_", "rev_label_data_")):
            point = int(case["id"].rsplit("_", 1)[1])
            parsed = parse_mermaid(case["data"][1]["content"]["aisop"]["main"])
            assert parsed["node_labels"]["a"] == "left" + chr(point) + "right", case["id"]
            assert parsed["nodes"]["a"]["next"] == ["b"], case["id"]
        elif case["id"].startswith("rev_ws_graph_"):
            parsed = parse_mermaid(case["data"][1]["content"]["aisop"]["main"])
            assert list(parsed["nodes"]) == ["a", "b"], case["id"]
            assert parsed["nodes"]["a"]["next"] == ["b"], case["id"]
    print("  [PASS] subgraphs: five arrows, groups, quotes and standalone nodes")


def test_subgraph_safe_keys():
    parsed = parse_mermaid('graph TD\n__proto__[Start] --> constructor[Work]\nconstructor -- "__proto__" --> toString[Handler]\n__proto__ -.-> toString')
    nodes = parsed["nodes"]
    assert nodes["__proto__"]["next"] == ["constructor"]
    assert nodes["__proto__"]["error"] == "toString"
    assert nodes["constructor"]["branches"]["__proto__"] == "toString"
    case = next(item for item in SUBGRAPH_CASES if item["id"] == "json_safe_own_keys")
    assert "__proto__" in case["data"][1]["content"]["aisop"]["main"]
    print("  [PASS] subgraphs: safe keys preserve next, error and branches")


def test_subgraph_validate_warning_boundary():
    from flow_runtime import check
    warning = next(item for item in SUBGRAPH_CASES if item["id"] == "unused")["data"]
    assert validate(warning) is None
    assert any(item["severity"] == "WARNING" for item in check(warning))
    invalid = next(item for item in SUBGRAPH_CASES if item["id"] == "call_syntax")["data"]
    try:
        validate(invalid)
    except ValueError:
        pass
    else:
        assert False, "Expected ValueError for malformed call"
    for case_id in ("rev_plan_1", "rev_plan_2", "rev_plan_3", "rev_plan_4", "rev_plan_5", "rev_present_handler"):
        case = next(item for item in SUBGRAPH_CASES if item["id"] == case_id)
        assert validate(case["data"]) is None, case_id
    for case_id in ("rev_empty_partial", "rev_missing_handler"):
        case = next(item for item in SUBGRAPH_CASES if item["id"] == case_id)
        try:
            validate(case["data"])
        except ValueError:
            pass
        else:
            assert False, case_id
    print("  [PASS] subgraphs: validate raises only for errors")


def test_subgraph_invalid_local_no_fallback():
    from flow_runtime import check
    data = json.loads(SUBGRAPH_CASES_TEXT)[1]["data"]
    data[1]["content"]["aisop"]["missing"] = None
    queries = []
    def resolver(target):
        queries.append(target)
        return True
    result = check(data, resolver)
    assert not queries
    assert any(item["code"] == "AISOP_E_SUBGRAPH_TARGET" for item in result)
    assert any(item["code"] == "AISOP_E_SUBGRAPH_SHAPE" for item in result)
    print("  [PASS] subgraphs: invalid local graph cannot use external fallback")


def test_subgraph_delegate_branches():
    from flow_runtime import check
    for body, fmt in (({"Start": {"delegate_to": "helper", "branches": {"ok": "End"}}, "End": {}}, "jsonflow"),
                      ("graph TD\nStart[aisop.helper] -->|ok| End((End))", "hybrid")):
        data = json.loads(SUBGRAPH_CASES_TEXT)[0]["data"]
        data[0]["content"]["flow_format"] = fmt
        data[1]["content"]["aisop"] = {"main": body, "helper": {"done": {}}}
        assert not check(data, standalone=True)
        info = list_nodes(data)[0]
        assert info["type"] == "delegate" and info["branches"] == {"ok": "End"}
    print("  [PASS] subgraphs: delegation precedes but preserves branches")


def test_subgraph_join_calls_counted():
    from flow_runtime import check
    data = json.loads(SUBGRAPH_CASES_TEXT)[0]["data"]
    data[1]["content"]["aisop"] = {"main": {"A": {"next": ["sync"]}, "B": {"next": ["sync"]}, "sync": {}}, "helper": {"done": {}}}
    data[1]["content"]["functions"] = {"sync": {"step1": "RUN aisop.helper", "join": {}}}
    queries = []
    result = check(data, lambda target: queries.append(target) or True)
    assert not queries
    assert result == []
    for case_id in ("semantic_join_local", "semantic_map_local", "semantic_map_default_resolver", "semantic_map_indirect"):
        case = next(item for item in SUBGRAPH_CASES if item["id"] == case_id)
        assert validate(case["data"]) is None, case_id
    for case_id in ("delegate_map_conflict", "semantic_join_cycle", "semantic_conflict_and_target", "semantic_join_edge_cycle"):
        case = next(item for item in SUBGRAPH_CASES if item["id"] == case_id)
        try:
            validate(case["data"])
        except ValueError:
            pass
        else:
            assert False, case_id
    cycle = next(item for item in SUBGRAPH_CASES if item["id"] == "semantic_join_edge_cycle")["data"]
    without_join = json.loads(json.dumps(cycle))
    without_join[1]["content"]["functions"]["alpha_join"]["step1"] = "Read the merged result"
    issues = check(without_join, standalone=True)
    assert [{key: item[key] for key in ("severity", "code", "location")} for item in issues] == [
        {"severity": "WARNING", "code": "AISOP_W_SUBGRAPH_UNUSED", "location": "/user/content/aisop/beta"}
    ]
    assert validate(without_join) is None
    without_back = json.loads(json.dumps(cycle))
    without_back[1]["content"]["functions"]["beta_entry"]["step1"] = "Read the context"
    assert check(without_back, standalone=True) == []
    assert validate(without_back) is None
    print("  [PASS] subgraphs: join/map steps count as references; error and warning boundaries remain")


def test_example_config_status_literal():
    filename = os.path.join(os.path.dirname(__file__), "example_syscalls.aisop.json")
    with open(filename, encoding="utf-8") as stream:
        data = json.load(stream)
    step = data[1]["content"]["functions"]["validate"]["step4"]
    assert step == """sys.assert('config_status == "valid"', 'Invalid configuration')"""
    assert eval_expression('config_status == "valid"', {"config_status": "valid"}) is True
    assert eval_expression('config_status == "valid"', {"config_status": "invalid"}) is False
    print("  [PASS] example: config_status compares with a quoted string")

def test_stage1_static_contract():
    for case_id, suffix in (
        ("stage1_unknown_confirmation", "FUNCTION_KEY"),
        ("stage1_step_value_0", "STEP_VALUE"),
        ("stage1_mode_unreachable", "EXECUTE_MODE"),
        ("stage1_params_value_8", "PARAMS"),
        ("stage1_delegate_bad_0", "CALL_SYNTAX"),
        ("stage1_mixed_bad_5", "CALL_SYNTAX"),
    ):
        case = next(item for item in SUBGRAPH_CASES if item["id"] == case_id)
        try:
            validate(case["data"])
        except ValueError as error:
            assert str(error).startswith("AISOP_E_SUBGRAPH_" + suffix), case_id
        else:
            assert False, case_id
    for case_id in ("stage1_mode_missing_zero_steps", "stage1_mode_agent", "stage1_params_null", "stage1_params_own_safe_keys", "stage1_mixed_literal_0"):
        case = next(item for item in SUBGRAPH_CASES if item["id"] == case_id)
        assert validate(case["data"]) is None, case_id
    case = next(item for item in SUBGRAPH_CASES if item["id"] == "stage1_delegate_quote_0")
    parsed = parse_mermaid(case["data"][1]["content"]["aisop"]["main"])
    assert parsed["node_labels"]["a"] == "'aisop.helper'"
    assert "delegate_to" not in parsed["nodes"]["a"]
    assert set(parsed) == {"nodes", "node_types", "node_labels"}
    print("  [PASS] stage one: strict fields, validate boundary and original label projection")



# Common inputs stay ASCII-escaped in source; decoding belongs to the tests.
EXPRESSION_CASES_TEXT = r'''[
{"id":"probe_01_missing","expression":"account_id != null","context":{},"error":"AISOP_E_EXPR_UNDEFINED"},
{"id":"probe_02_null","expression":"account_id != null","context":{"account_id":null},"value":false},
{"id":"probe_03_unquoted","expression":"config_status == valid","context":{"config_status":"valid"},"error":"AISOP_E_EXPR_UNDEFINED"},
{"id":"probe_04_quoted","expression":"config_status == \"valid\"","context":{"config_status":"valid"},"value":true},
{"id":"probe_05_bool_number","expression":"1 == true","context":{},"value":false},
{"id":"probe_06_exponent","expression":"1e3 == 1000","context":{},"value":true},
{"id":"probe_07_bare_array","expression":"items","context":{"items":[]},"error":"AISOP_E_EXPR_TYPE"},
{"id":"probe_08_prototype","expression":"x.constructor","context":{"x":{}},"error":"AISOP_E_EXPR_UNDEFINED"},
{"id":"probe_09_unary","expression":"!a == b","context":{"a":true,"b":false},"value":true},
{"id":"probe_10_operators","expression":"s == 'a&&b'","context":{"s":"a&&b"},"value":true},
{"id":"probe_11_quote","expression":"s == 'it\\'s'","context":{"s":"it's"},"value":true},
{"id":"probe_12_deployment","expression":"was_deployed == true","context":{"was_deployed":true},"value":true},
{"id":"unary_precedence","expression":"!a == b","context":{"a":true,"b":1},"value":false},
{"id":"not_number","expression":"!a","context":{"a":1},"error":"AISOP_E_EXPR_TYPE"},
{"id":"not_twice","expression":"!!a","context":{"a":true},"value":true},
{"id":"not_null","expression":"!a","context":{"a":null},"error":"AISOP_E_EXPR_TYPE"},
{"id":"logical_and_type","expression":"true && 1","context":{},"error":"AISOP_E_EXPR_TYPE"},
{"id":"logical_or_type","expression":"false || 0","context":{},"error":"AISOP_E_EXPR_TYPE"},
{"id":"and_left_type","expression":"0 && missing","context":{},"error":"AISOP_E_EXPR_TYPE"},
{"id":"or_left_type","expression":"1 || missing","context":{},"error":"AISOP_E_EXPR_TYPE"},
{"id":"final_string","expression":"'ok'","context":{},"error":"AISOP_E_EXPR_TYPE"},
{"id":"final_number","expression":"1","context":{},"error":"AISOP_E_EXPR_TYPE"},
{"id":"final_object","expression":"x","context":{"x":{}},"error":"AISOP_E_EXPR_TYPE"},
{"id":"final_null","expression":"null","context":{},"error":"AISOP_E_EXPR_TYPE"},
{"id":"short_and","expression":"false && missing","context":{},"value":false},
{"id":"short_or","expression":"true || missing.value","context":{},"value":true},
{"id":"priority","expression":"true || false && false","context":{},"value":true},
{"id":"comparison_priority","expression":"1 == 1 && 2 > 1 || false","context":{},"value":true},
{"id":"left_missing","expression":"missing || true","context":{},"error":"AISOP_E_EXPR_UNDEFINED"},
{"id":"member_missing","expression":"x.value == null","context":{"x":{}},"error":"AISOP_E_EXPR_UNDEFINED"},
{"id":"null_receiver","expression":"x.value == null","context":{"x":null},"error":"AISOP_E_EXPR_TYPE"},
{"id":"array_receiver","expression":"items.length == 0","context":{"items":[]},"error":"AISOP_E_EXPR_TYPE"},
{"id":"nested_own","expression":"x.value == 1","context":{"x":{"value":1}},"value":true},
{"id":"member_keyword","expression":"x.true == false","context":{"x":{"true":false}},"value":true},
{"id":"own_prototype_name","expression":"x.constructor == 'data'","context":{"x":{"constructor":"data"}},"value":true},
{"id":"root_keyword","expression":"true","context":{"true":false},"value":true},
{"id":"ordinary_True","expression":"True","context":{"True":true},"value":true},
{"id":"ordinary_None","expression":"None == null","context":{"None":null},"value":true},
{"id":"ordinary_undefined","expression":"undefined","context":{"undefined":false},"value":false},
{"id":"keyword_prefix","expression":"true_value","context":{"true_value":true},"value":true},
{"id":"null_context","expression":"true","context":null,"value":true},
{"id":"root_array","expression":"true","context":[],"error":"AISOP_E_EXPR_TYPE"},
{"id":"root_string","expression":"true","context":"x","error":"AISOP_E_EXPR_TYPE"},
{"id":"root_boolean","expression":"true","context":false,"error":"AISOP_E_EXPR_TYPE"},
{"id":"root_number","expression":"true","context":1,"error":"AISOP_E_EXPR_TYPE"},
{"id":"different_types","expression":"'1' != 1","context":{},"value":true},
{"id":"object_null","expression":"x == null","context":{"x":{}},"value":false},
{"id":"array_null","expression":"x != null","context":{"x":[]},"value":true},
{"id":"null_null","expression":"null == null","context":{},"value":true},
{"id":"same_object_kind","expression":"a == b","context":{"a":{},"b":{}},"error":"AISOP_E_EXPR_TYPE"},
{"id":"same_array_kind","expression":"a != b","context":{"a":[],"b":[]},"error":"AISOP_E_EXPR_TYPE"},
{"id":"different_containers","expression":"a == b","context":{"a":{},"b":[]},"value":false},
{"id":"string_order","expression":"'a' < 'b'","context":{},"error":"AISOP_E_EXPR_TYPE"},
{"id":"bool_order","expression":"true > false","context":{},"error":"AISOP_E_EXPR_TYPE"},
{"id":"negative_zero","expression":"-0 == 0","context":{},"value":true},
{"id":"decimal","expression":"0.1 == 0.1","context":{},"value":true},
{"id":"underflow","expression":"1e-400 == 0","context":{},"value":true},
{"id":"max_literal","expression":"9007199254740991 == 9007199254740991","context":{},"value":true},
{"id":"min_literal","expression":"-9007199254740991 < 0","context":{},"value":true},
{"id":"max_context","expression":"x == 9007199254740991","context":{"x":9007199254740991},"value":true},
{"id":"range_context","expression":"x == 0","context":{"x":9007199254740992},"error":"AISOP_E_EXPR_RANGE"},
{"id":"min_range_context","expression":"x < 0","context":{"x":-9007199254740992},"error":"AISOP_E_EXPR_RANGE"},
{"id":"lazy_bad_context","expression":"true || x","context":{"x":"\ud800"},"value":true},
{"id":"lazy_context_range","expression":"false && x","context":{"x":1e+300},"value":false},
{"id":"bad_context_unicode","expression":"s == 'x'","context":{"s":"\ud800"},"error":"AISOP_E_EXPR_TYPE"},
{"id":"paired_context","expression":"s == '\ud83d\ude00'","context":{"s":"\ud83d\ude00"},"value":true},
{"id":"data_control","expression":"s == '\\u0000\\n'","context":{"s":"\u0000\n"},"value":true},
{"id":"unicode_escape","expression":"s == '\\u4e2d\\u6587'","context":{"s":"\u4e2d\u6587"},"value":true},
{"id":"paired_escape","expression":"s == '\\ud83d\\ude00'","context":{"s":"\ud83d\ude00"},"value":true},
{"id":"backslash","expression":"s == 'a\\\\b'","context":{"s":"a\\b"},"value":true},
{"id":"double_quote","expression":"s == \"a\\\"b\"","context":{"s":"a\"b"},"value":true},
{"id":"all_escapes","expression":"s == \"\\b\\f\\n\\r\\t\\/\"","context":{"s":"\b\f\n\r\t/"},"value":true},
{"id":"single_double_quote","expression":"s == 'a\"b'","context":{"s":"a\"b"},"value":true},
{"id":"no_normalization","expression":"s == '\u00e9'","context":{"s":"e\u0301"},"value":false},
{"id":"no_casefold","expression":"s == 'X'","context":{"s":"x"},"value":false},
{"id":"space_W","expression":"\u1680 true \u3000","context":{},"value":true},
{"id":"bom_B","expression":"\ufefftrue","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"zero_width_B","expression":"true\u200b","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"empty","expression":"","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"W_only","expression":" \t","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"parentheses","expression":"(true)","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"arithmetic","expression":"1 + 1 == 2","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"function","expression":"fn()","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"index","expression":"x[0] == 1","context":{"x":[1]},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"assignment","expression":"x = true","context":{"x":true},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"chained","expression":"1 < 2 < 3","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"dangling","expression":"true &&","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"extra_token","expression":"true false","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"lone_not","expression":"!","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"unknown_escape","expression":"'a\\q' == 'a'","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"unclosed_string","expression":"'abc","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"raw_control","expression":"s == 'a\nb'","context":{"s":"a\nb"},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"lone_literal","expression":"'\\ud800' == 'x'","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"bad_low_literal","expression":"'\\udc00' == 'x'","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"raw_lone_literal","expression":"'\ud800' == 'x'","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"lazy_syntax","expression":"true || fn()","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"lazy_literal","expression":"true || '\\q'","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"lazy_literal_range","expression":"true || 1e300 == 0","context":{},"error":"AISOP_E_EXPR_RANGE"},
{"id":"hex","expression":"0x10 == 16","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"plus","expression":"+1 == 1","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"leading_zero","expression":"01 == 1","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"underscore","expression":"1_0 == 10","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"fraction_no_lead","expression":".5 == 0.5","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"fraction_no_tail","expression":"1. == 1","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"null_member","expression":"null.x == 1","context":{},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"bad_dot","expression":"x. == 1","context":{"x":{}},"error":"AISOP_E_EXPR_SYNTAX"},
{"id":"not_source","expression":1,"context":{},"error":"AISOP_E_EXPR_TYPE"},
{"id":"range_9007199254740992","expression":"9007199254740992 == 0","context":{},"error":"AISOP_E_EXPR_RANGE"},
{"id":"range_-9007199254740992","expression":"-9007199254740992 == 0","context":{},"error":"AISOP_E_EXPR_RANGE"},
{"id":"range_9007199254740992.0","expression":"9007199254740992.0 == 0","context":{},"error":"AISOP_E_EXPR_RANGE"},
{"id":"range_9.007199254740992e15","expression":"9.007199254740992e15 == 0","context":{},"error":"AISOP_E_EXPR_RANGE"},
{"id":"range_1e20","expression":"1e20 == 0","context":{},"error":"AISOP_E_EXPR_RANGE"},
{"id":"range_1e300","expression":"1e300 == 0","context":{},"error":"AISOP_E_EXPR_RANGE"},
{"id":"range_1e309","expression":"1e309 == 0","context":{},"error":"AISOP_E_EXPR_RANGE"}
]'''
RAW_JSON_CASES_TEXT = r'''[
{"id":"minimal","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_1","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":0}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_2","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":-0}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_3","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":1.5}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_4","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":0.1}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_5","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":1e3}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_6","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":1e-400}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_7","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":9007199254740991}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_8","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":-9007199254740991}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_9","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":9.007199254740991e15}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_10","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":true}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_11","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":null}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_12","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":\"\u4e2d\u6587\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_13","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":\"\\ud83d\\ude00\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_14","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":{\"__proto__\":{\"x\":1},\"constructor\":\"data\"}}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_15","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":[{\"a\":1},{\"a\":2}]}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_16","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":{\"a\":{\"a\":1},\"b\":[{\"a\":2}]}}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"accept_17","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":{\"a\":\"comma,brace} and escaped \\\" quote\",\"b\":[[],{}]}}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true},
{"id":"reject_18","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":9007199254740992}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_19","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":-9007199254740992}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_20","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":9007199254740992.0}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_21","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":9.007199254740992e15}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_22","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":1e20}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_23","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":1e300}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_24","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":1e309}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_25","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":NaN}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_26","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":Infinity}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_27","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":-Infinity}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_28","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":01}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_29","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":+1}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_30","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":0x10}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_31","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":1_0}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_32","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":\"\\ud800\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_33","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":\"\\udc00\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_34","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":{\"\\ud800\":1}}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_35","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":{\"a\":1,\"a\":2}}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_36","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":{\"a\":1,\"\\u0061\":2}}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_37","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":{\"a\":{\"x\":1,\"x\":2}}}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_38","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":{\"__proto__\":1,\"__proto__\":2}}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"reject_39","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":{\"\ud83d\ude00\":1,\"\\ud83d\\ude00\":2}}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"single_bom","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true,"prefix_hex":"efbbbf"},
{"id":"double_bom","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT","prefix_hex":"efbbbfefbbbf"},
{"id":"internal_bom","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":\"a\\ufeffb\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true,"probe":"a\ufeffb"},
{"id":"bad_utf8_prefix","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT","prefix_hex":"ff"},
{"id":"bad_utf8_string","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":\"<BAD>\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT","replace_hex":"c328"},
{"id":"truncated_utf8","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT","suffix_hex":"e282"},
{"id":"utf8_surrogate","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":\"<BAD>\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT","replace_hex":"eda080"},
{"id":"trailing","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]x","error":"AISOP_E_JSON_INPUT"},
{"id":"trailing_comma","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{},}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_JSON_INPUT"},
{"id":"mode_structure","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"execute_mode\":null}}}}]","error":"AISOP_E_SUBGRAPH_EXECUTE_MODE"},
{"id":"params_structure","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"params\":null}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","error":"AISOP_E_SUBGRAPH_PARAMS"},
{"id":"key_structure","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\"}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"typo\":\"Read\"}}}}]","error":"AISOP_E_SUBGRAPH_FUNCTION_KEY"},
{"id":"root_structure","text":"null","error":"AISOP_E_SUBGRAPH_SHAPE"},
{"id":"case_sensitive","text":"[{\"role\":\"system\",\"content\":{\"protocol\":\"AISOP V1.0.0\",\"axiom_0\":\"Human_Sovereignty_and_Wellbeing\",\"id\":\"strict_input\",\"name\":\"Strict Input\",\"version\":\"1.0.0\",\"flow_format\":\"jsonflow\",\"_probe\":{\"a\":1,\"A\":2,\"\u00e9\":3,\"e\\u0301\":4}}},{\"role\":\"user\",\"content\":{\"instruction\":\"RUN aisop.main\",\"aisop\":{\"main\":{\"start\":{}}},\"functions\":{\"start\":{\"step1\":\"Read\"}}}}]","ok":true}
]'''
EXPRESSION_CASES = json.loads(EXPRESSION_CASES_TEXT)
RAW_JSON_CASES = json.loads(RAW_JSON_CASES_TEXT)


def test_stage2_expression_contract():
    for case in EXPRESSION_CASES:
        try:
            result = eval_expression(case["expression"], case["context"])
        except ValueError as error:
            assert "error" in case, case["id"]
            assert getattr(error, "code", None) == case["error"], case["id"]
            assert str(error) == case["error"], case["id"]
        else:
            assert "value" in case and type(result) is bool, case["id"]
            assert result is case["value"], case["id"]
    assert eval_expression("true") is True
    print(f"  [PASS] stage two: {len(EXPRESSION_CASES)} shared expression cases")


def test_stage2_raw_json_contract():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "strict.aisop.json")
        for case in RAW_JSON_CASES:
            raw = case["text"].encode("utf-8")
            if "replace_hex" in case:
                raw = raw.replace(b"<BAD>", bytes.fromhex(case["replace_hex"]))
            raw = bytes.fromhex(case.get("prefix_hex", "")) + raw + bytes.fromhex(case.get("suffix_hex", ""))
            with open(path, "wb") as stream:
                stream.write(raw)
            try:
                data = load(path)
            except ValueError as error:
                assert "error" in case, case["id"]
                actual = getattr(error, "code", str(error).split(" ", 1)[0])
                assert actual == case["error"], case["id"]
                if actual == "AISOP_E_JSON_INPUT":
                    assert error.code == str(error) == actual, case["id"]
                else:
                    assert not hasattr(error, "code"), case["id"]
            else:
                assert case.get("ok"), case["id"]
                if "probe" in case:
                    assert data[0]["content"]["_probe"] == case["probe"], case["id"]
    print(f"  [PASS] stage two: {len(RAW_JSON_CASES)} shared raw-byte JSON cases")


def test_stage2_api_boundaries():
    from flow_runtime import check
    for value in (float("nan"), float("inf"), -float("inf"), 10 ** 10000):
        try:
            eval_expression("x == 0", {"x": value})
        except ValueError as error:
            assert error.code == "AISOP_E_EXPR_RANGE"
        else:
            assert False, "Invalid numeric context was accepted"
        assert eval_expression("true || x", {"x": value}) is True
    assert eval_expression("s == '\U0001f600'", {"s": "\ud83d\ude00"}) is True
    assert eval_expression("x.__proto__ == 1", {"x": {"__proto__": 1}}) is True
    assert eval_expression("true || x", {"x": object()}) is True
    try:
        eval_expression("x", {"x": object()})
    except ValueError as error:
        assert error.code == "AISOP_E_EXPR_TYPE"
    else:
        assert False, "Host object was accepted"
    for region in ("functions", "aisop"):
        data = json.loads(RAW_JSON_CASES[0]["text"])
        data[1]["content"][region]["\ud800"] = {}
        assert check(data) == [{"severity": "ERROR", "code": "AISOP_E_SUBGRAPH_SHAPE",
                               "location": "/", "message": "Invalid Unicode in diagnostic key"}]
    data = json.loads(RAW_JSON_CASES[0]["text"])
    data[0]["content"]["_probe"] = "\ud800"
    assert check(data) == []  # check is not full arbitrary-payload JSON certification.
    with tempfile.TemporaryDirectory() as directory:
        try:
            load(os.path.join(directory, "missing.aisop.json"))
        except FileNotFoundError as error:
            assert getattr(error, "code", None) != "AISOP_E_JSON_INPUT"
        else:
            assert False, "Native IO error was swallowed"
        nested = "leaf"
        for _ in range(128):
            nested = [nested]
        data[0]["content"]["_probe"] = nested
        path = os.path.join(directory, "nested.aisop.json")
        with open(path, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream)
        assert load(path)[0]["content"]["_probe"] == nested
    print("  [PASS] stage two: actual-value, Unicode-location, native-IO and fresh-tree boundaries")

if __name__ == "__main__":
    print("AISOP V1.0.0 — Testing all utilities:\n")
    test_parse_mermaid_basic()
    test_parse_mermaid_error_edge()
    test_parse_mermaid_delegate()
    test_parse_mermaid_chained()
    test_parse_mermaid_parallel()
    test_infer_node_type()
    test_validate_valid()
    test_validate_invalid()
    test_get_metadata()
    test_params()
    test_get_tasks()
    test_get_functions()
    test_list_nodes()
    test_list_nodes_subtask()
    test_parallel_nodes()
    test_error_routing_nodes()
    test_delegate_nodes()
    test_render_flow()
    test_build_prompt()
    test_load_file()
    test_load_example()
    test_load_example_syscalls()
    test_json_flow_validate()
    test_json_flow_list_nodes()
    test_json_flow_render()
    test_mixed_flow_validate()
    test_mixed_flow_list_nodes()
    print(f"\nAll tests passed!")

    print("\nsys.* System Call Tests:\n")
    test_classify_step_sys_call()
    test_classify_step_sub_task()
    test_classify_step_natural_language()
    test_parse_sys_call_confirm()
    test_parse_sys_call_with_store()
    test_parse_sys_call_nested()
    test_parse_sys_call_invalid()
    test_eval_expression_comparison()
    test_eval_expression_null_check()
    test_eval_expression_logical_and()
    test_eval_expression_logical_or()
    test_eval_expression_logical_not()
    test_eval_expression_combined_logic()
    test_parse_sys_call_validation()
    test_eval_expression_string_with_operators()
    test_eval_expression_string_comparison()
    test_valid_sys_calls_count()
    print(f"\nAll sys.* tests passed!")

    print("\nSubgraph contract tests:\n")
    test_subgraph_contract_cases()
    test_subgraph_call_api()
    test_subgraph_mermaid_subset()
    test_subgraph_safe_keys()
    test_subgraph_validate_warning_boundary()
    test_subgraph_invalid_local_no_fallback()
    test_subgraph_delegate_branches()
    test_subgraph_join_calls_counted()
    test_example_config_status_literal()
    test_stage1_static_contract()
    test_stage2_expression_contract()
    test_stage2_raw_json_contract()
    test_stage2_api_boundaries()
    print("\nAll subgraph tests passed!")

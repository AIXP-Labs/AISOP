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
            "params": { "language": "en", "tone": "friendly" },
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
    assert meta.get("params") == {"language": "en", "tone": "friendly"}
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
    assert meta["params"]["language"] == "en"
    assert meta["params"]["tone"] == "friendly"

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

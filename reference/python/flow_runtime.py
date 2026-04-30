"""
AISOP Runtime — AI Standard Operating Protocol V1.0.0

Loads .aisop.json files, validates structure, and provides utilities
for working with AISOP flow definitions.

AISOP uses Mermaid for flow graph definition:
  - name[text]    → process node (rectangle)
  - name{text}    → decision node (diamond)
  - name((text))  → end node (circle)
  - name[aisop.x] → delegate node (calls sub-task x)
  - -->            → normal edge (next)
  - -->|label|     → branch edge (conditional)
  - -.->           → error edge

Zero dependencies beyond Python stdlib.
"""

import json
import re
from pathlib import Path


# ── Mermaid Parser ─────────────────────────────────────────

def _extract_node_shape(text: str, node_types: dict, node_labels: dict, delegate_targets: dict) -> str | None:
    """Extract node ID from text with optional Mermaid shape. Records type and label."""
    text = text.strip()
    if not text:
        return None

    # name((text)) → end
    m = re.match(r'^(\w+)\(\((.+?)\)\)$', text)
    if m:
        name, label = m.group(1), m.group(2)
        node_types[name] = "end"
        node_labels[name] = label
        return name

    # name{text} → decision
    m = re.match(r'^(\w+)\{(.+?)\}$', text)
    if m:
        name, label = m.group(1), m.group(2)
        node_types[name] = "decision"
        node_labels[name] = label
        return name

    # name[text] → process or delegate
    m = re.match(r'^(\w+)\[(.+?)\]$', text)
    if m:
        name, label = m.group(1), m.group(2)
        if label.startswith("aisop."):
            node_types[name] = "delegate"
            delegate_targets[name] = label[len("aisop."):]
        else:
            node_types[name] = "process"
        node_labels[name] = label
        return name

    # plain name (no shape)
    m = re.match(r'^(\w+)$', text)
    if m:
        return m.group(1)

    return None


def parse_mermaid(mermaid_str: str) -> dict:
    """Parse a Mermaid graph string into a structured node dictionary.

    Returns a dict with keys:
      - nodes: {name: {next: [...], branches: {...}, error: "...", delegate_to: "..."}}
      - node_types: {name: "process"|"decision"|"end"|"delegate"}
      - node_labels: {name: "display text"}
    """
    nodes = {}
    node_types = {}
    node_labels = {}
    delegate_targets = {}

    lines = mermaid_str.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line or line.startswith("graph ") or line.startswith("%%"):
            continue

        # Split line by edge patterns: -->|label|, -->, -.->
        parts = re.split(r'\s*(-->\|[^|]+\||-->|-\.->)\s*', line)

        if len(parts) < 3:
            # Standalone node definition (no edge)
            _extract_node_shape(parts[0].strip(), node_types, node_labels, delegate_targets)
            continue

        # Process edge pairs: (source, edge, target, edge, target, ...)
        for i in range(0, len(parts) - 2, 2):
            src_raw = parts[i].strip()
            edge_raw = parts[i + 1].strip()
            dst_raw = parts[i + 2].strip()

            src = _extract_node_shape(src_raw, node_types, node_labels, delegate_targets)
            dst = _extract_node_shape(dst_raw, node_types, node_labels, delegate_targets)

            if not src or not dst:
                continue

            if src not in nodes:
                nodes[src] = {}
            if dst not in nodes:
                nodes[dst] = {}

            if "-.->" in edge_raw:
                # Error edge
                nodes[src]["error"] = dst
            elif "|" in edge_raw:
                # Branch edge
                label = re.search(r'\|(.+?)\|', edge_raw).group(1)
                nodes[src].setdefault("branches", {})[label] = dst
            else:
                # Normal edge (next)
                nodes[src].setdefault("next", [])
                if dst not in nodes[src]["next"]:
                    nodes[src]["next"].append(dst)

    # Add delegate_to to nodes
    for name, target in delegate_targets.items():
        if name in nodes:
            nodes[name]["delegate_to"] = target

    return {
        "nodes": nodes,
        "node_types": node_types,
        "node_labels": node_labels,
    }


def infer_node_type(node: dict) -> str:
    """Infer node behavior from its parsed structure.

    Priority order (highest to lowest):
      1. {} (empty)        → end
      2. has branches      → decision
      3. has delegate_to   → delegate
      4. has next (2+)     → fork
      5. has next (1)      → process
    """
    if not node:
        return "end"
    if "branches" in node:
        return "decision"
    if "delegate_to" in node:
        return "delegate"
    if "next" in node:
        return "fork" if len(node["next"]) > 1 else "process"
    return "end"


# ── Load & Validate ─────────────────────────────────────────

def load(path: str) -> list:
    """Load an .aisop.json file and return parsed JSON."""
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    validate(data)
    return data


def validate(data: list) -> None:
    """Validate AISOP V1.0.0 structure. Raises ValueError on invalid input."""
    if not isinstance(data, list) or len(data) != 2:
        raise ValueError("AISOP file must be a JSON array with exactly 2 elements")

    system, user = data
    if system.get("role") != "system":
        raise ValueError("First element must have role='system'")
    if user.get("role") != "user":
        raise ValueError("Second element must have role='user'")

    sc = system.get("content", {})
    for field in ("protocol", "axiom_0", "id", "name", "version", "flow_format"):
        if field not in sc:
            raise ValueError(f"system.content missing required field: {field}")

    if sc.get("axiom_0") != "Human_Sovereignty_and_Wellbeing":
        raise ValueError('axiom_0 must be "Human_Sovereignty_and_Wellbeing"')

    if sc.get("flow_format") not in ("mermaid", "jsonflow", "hybrid"):
        raise ValueError('flow_format must be "mermaid", "jsonflow", or "hybrid"')

    uc = user.get("content", {})
    for field in ("instruction", "aisop", "functions"):
        if field not in uc:
            raise ValueError(f"user.content missing required field: {field}")
    if "main" not in uc["aisop"]:
        raise ValueError("aisop must contain a 'main' task")

    # Validate each task — Mermaid string or JSON flow object
    for task_name, task_body in uc["aisop"].items():
        if isinstance(task_body, str):
            # Mermaid format
            parsed = parse_mermaid(task_body)
            if not parsed["nodes"]:
                raise ValueError(f"Task '{task_name}' has no parseable nodes")
        elif isinstance(task_body, dict):
            # JSON flow format
            if not task_body:
                raise ValueError(f"Task '{task_name}' is empty")
        else:
            raise ValueError(f"Task '{task_name}' must be Mermaid string or JSON flow object, got {type(task_body).__name__}")


# ── Metadata ────────────────────────────────────────────────

def get_metadata(data: list) -> dict:
    """Extract program metadata from AISOP data."""
    return data[0]["content"]


def get_tasks(data: list) -> dict:
    """Extract all tasks (Mermaid flow strings) from AISOP data."""
    return data[1]["content"].get("aisop", {})


def get_functions(data: list) -> dict:
    """Extract all function definitions from AISOP data."""
    return data[1]["content"].get("functions", {})


# ── Flow Analysis ───────────────────────────────────────────

def _infer_json_flow_type(node: dict) -> str:
    """Infer node type from JSON flow structure."""
    if not node:
        return "end"
    if "branches" in node:
        return "decision"
    if "delegate_to" in node:
        return "delegate"
    if "wait_for" in node:
        return "join"
    if "next" in node:
        return "fork" if len(node["next"]) > 1 else "process"
    return "end"


def list_nodes(data: list, task: str = "main") -> list[dict]:
    """List all nodes in a task with their inferred type and connections."""
    tasks = get_tasks(data)
    task_body = tasks.get(task, "")
    if not task_body:
        return []

    # Mermaid format (string)
    if isinstance(task_body, str):
        parsed = parse_mermaid(task_body)
        nodes_dict = parsed["nodes"]
        shape_types = parsed["node_types"]

        result = []
        for name, node in nodes_dict.items():
            ntype = shape_types.get(name, infer_node_type(node))
            if "next" in node and len(node["next"]) > 1 and ntype == "process":
                ntype = "fork"

            info = {"name": name, "type": ntype}
            if "next" in node:
                info["next"] = node["next"]
            if "branches" in node:
                info["branches"] = node["branches"]
            if "delegate_to" in node:
                info["delegate_to"] = node["delegate_to"]
            if "error" in node:
                info["error"] = node["error"]
            result.append(info)
        return result

    # JSON flow format (dict)
    if isinstance(task_body, dict):
        result = []
        for name, node in task_body.items():
            info = {"name": name, "type": _infer_json_flow_type(node)}
            for key in ("next", "branches", "delegate_to", "error", "wait_for"):
                if key in node:
                    info[key] = node[key]
            result.append(info)
        return result

    return []


def render_flow(data: list, task: str = "main") -> str:
    """Return the flow diagram for a task (Mermaid string or JSON flow repr)."""
    tasks = get_tasks(data)
    task_body = tasks.get(task, "(empty)")
    if isinstance(task_body, str):
        return task_body
    if isinstance(task_body, dict):
        import json as _json
        return _json.dumps(task_body, indent=2, ensure_ascii=False)
    return "(empty)"


# ── sys.* System Call Parsing ───────────────────────────────

# Matches sys calls: sys.io.confirm('msg') -> var
# Groups: (1) full_name  (2) args_text  (3) store_var or None
SYS_CALL_RE = re.compile(
    r"^(sys(?:\.\w+){1,3})\((.*)?\)\s*(?:->\s*(\w+))?$"
)

# All valid sys call names (§6)
VALID_SYS_CALLS = frozenset([
    "sys.io.confirm", "sys.io.input", "sys.io.select",
    "sys.io.notify", "sys.io.print", "sys.io.read", "sys.io.write",
    "sys.run", "sys.run.timeout", "sys.run.bg",
    "sys.assert",
    "sys.llm", "sys.llm.json", "sys.llm.classify",
    "sys.code.exec", "sys.code.eval",
    "sys.state.get", "sys.state.set", "sys.state.save", "sys.state.load",
    "sys.event.emit", "sys.event.wait",
    "sys.security.audit", "sys.security.redact",
])

# sys call error types (§6.12)
SYS_ERROR_TYPES = frozenset([
    "confirm_rejected", "confirm_timeout", "assertion_error",
    "command_error", "command_timeout", "io_error",
])


def classify_step(step_text: str) -> str:
    """Classify a step text into one of three modes (§5.3).

    Returns:
      - 'sys_call'          if step starts with 'sys.'
      - 'sub_task'          if step starts with 'RUN aisop.'
      - 'natural_language'  otherwise
    """
    stripped = step_text.strip()
    if stripped.startswith("sys."):
        return "sys_call"
    if stripped.startswith("RUN aisop."):
        return "sub_task"
    return "natural_language"


def parse_sys_call(step_text: str) -> dict | None:
    """Parse a sys.* call from step text (§6.10).

    Returns a dict with keys:
      - name: str       full call name (e.g. 'sys.io.confirm')
      - args: str       raw argument text
      - store: str|None variable name for -> storage
      - valid: bool     whether name is in VALID_SYS_CALLS

    Returns None if the step is not a sys call syntax.
    """
    m = SYS_CALL_RE.match(step_text.strip())
    if not m:
        return None
    name = m.group(1)
    args = m.group(2) or ""
    store = m.group(3)
    return {
        "name": name,
        "args": args.strip(),
        "store": store,
        "valid": name in VALID_SYS_CALLS,
    }


def _split_outside_quotes(expr: str, delimiter: str) -> list[str] | None:
    """Split expression on a delimiter, but only outside quoted strings.

    Returns list of parts if delimiter found outside quotes, else None.
    """
    parts = []
    current = []
    in_quote = None  # None, "'", or '"'
    i = 0
    while i < len(expr):
        ch = expr[i]
        # Track quote state
        if ch in ("'", '"') and in_quote is None:
            in_quote = ch
        elif ch == in_quote:
            in_quote = None
        # Check for delimiter only outside quotes
        if in_quote is None and expr[i:i + len(delimiter)] == delimiter:
            parts.append("".join(current))
            current = []
            i += len(delimiter)
            continue
        current.append(ch)
        i += 1
    parts.append("".join(current))
    return parts if len(parts) > 1 else None


def _find_operator_outside_quotes(expr: str, op: str) -> int:
    """Find first occurrence of operator outside quoted strings. Returns -1 if not found."""
    in_quote = None
    for i in range(len(expr)):
        ch = expr[i]
        if ch in ("'", '"') and in_quote is None:
            in_quote = ch
        elif ch == in_quote:
            in_quote = None
        if in_quote is None and expr[i:i + len(op)] == op:
            return i
    return -1


def eval_expression(expr: str, context: dict | None = None) -> object:
    """Evaluate a deterministic expression (§6.11).

    Supports: ==, !=, >, <, >=, <=, &&, ||, !, null checks, member access.
    Does NOT go through LLM. Respects quoted string boundaries.

    Args:
        expr: expression string (e.g. 'count > 0', 'a > 1 && b < 10')
        context: variable context dict

    Returns:
        Evaluation result (typically bool for comparisons)

    Raises:
        ValueError: if expression is invalid or references undefined variables
    """
    if context is None:
        context = {}

    expr = expr.strip()

    # Handle member access: result.exit_code -> context resolution
    def resolve_var(name: str) -> object:
        parts = name.strip().split(".")
        obj = context
        for part in parts:
            if isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                raise ValueError(f"Undefined variable: {name}")
        return obj

    def resolve_token(token: str) -> object:
        token = token.strip()
        if _is_literal(token):
            return _parse_literal(token)
        return resolve_var(token)

    def eval_comparison(sub_expr: str) -> object:
        """Evaluate a single comparison (no &&/||)."""
        sub_expr = sub_expr.strip()
        # Handle unary NOT: !var
        if sub_expr.startswith("!"):
            inner = sub_expr[1:].strip()
            return not eval_comparison(inner)
        for op in ("!=", "==", ">=", "<=", ">", "<"):
            idx = _find_operator_outside_quotes(sub_expr, op)
            if idx != -1:
                left = sub_expr[:idx]
                right = sub_expr[idx + len(op):]
                left_val = resolve_token(left)
                right_val = resolve_token(right)
                if op == "!=": return left_val != right_val
                if op == "==": return left_val == right_val
                if op == ">=": return left_val >= right_val
                if op == "<=": return left_val <= right_val
                if op == ">":  return left_val > right_val
                if op == "<":  return left_val < right_val
        # Single token — resolve as truthy/falsy
        return bool(resolve_token(sub_expr))

    # Handle || (lowest precedence) — split outside quotes only
    parts = _split_outside_quotes(expr, "||")
    if parts is not None:
        return any(eval_expression(p.strip(), context) for p in parts)

    # Handle && (higher precedence than ||) — split outside quotes only
    parts = _split_outside_quotes(expr, "&&")
    if parts is not None:
        return all(eval_expression(p.strip(), context) for p in parts)

    return eval_comparison(expr)


def _is_literal(token: str) -> bool:
    """Check if a token is a literal value."""
    if token == "None" or token == "null":
        return True
    if token in ("true", "false", "True", "False"):
        return True
    try:
        float(token)
        return True
    except ValueError:
        pass
    if (token.startswith("'") and token.endswith("'")) or \
       (token.startswith('"') and token.endswith('"')):
        return True
    return False


def _parse_literal(token: str) -> object:
    """Parse a literal token into a Python value."""
    if token in ("None", "null"):
        return None
    if token in ("true", "True"):
        return True
    if token in ("false", "False"):
        return False
    try:
        if "." in token:
            return float(token)
        return int(token)
    except ValueError:
        pass
    if (token.startswith("'") and token.endswith("'")) or \
       (token.startswith('"') and token.endswith('"')):
        return token[1:-1]
    return token


# ── Prompt Builder ──────────────────────────────────────────

def build_prompt(data: list, user_input: str, system_prompt: str = "") -> str:
    """Build a complete prompt string from AISOP data and user input.

    Replaces {system_prompt} and {user_input} variables.
    Returns the full JSON string ready for use.
    """
    import copy
    result = copy.deepcopy(data)

    if system_prompt:
        result[0]["content"]["system_prompt"] = system_prompt
    result[1]["content"]["user_input"] = user_input

    return json.dumps(result, ensure_ascii=False, indent=2)


# ── CLI ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python flow_runtime.py <file.aisop.json> [task]")
        sys.exit(1)

    path = sys.argv[1]
    task = sys.argv[2] if len(sys.argv) > 2 else "main"

    data = load(path)
    meta = get_metadata(data)

    print(f"AISOP: {meta.get('name')} v{meta.get('version')}")
    print(f"Protocol: {meta.get('protocol')}")
    print(f"Summary: {meta.get('summary', '-')}")
    print()
    print(f"Flow ({task}):")
    print(render_flow(data, task))
    print()
    print(f"Functions: {', '.join(get_functions(data).keys())}")

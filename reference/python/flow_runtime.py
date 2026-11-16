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
import math
import re
from pathlib import Path


# ── Mermaid Parser ─────────────────────────────────────────

IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
STEP_KEY = re.compile(r"step[1-9][0-9]*\Z")
CALL = re.compile(r"RUN aisop\.([A-Za-z_][A-Za-z0-9_]*)(?:[ \t]+->[ \t]*([A-Za-z_][A-Za-z0-9_]*))?\Z")
_WS = "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"
_BAD_WS = "\u001c\u001d\u001e\u001f\u0085\ufeff"
_WS_CLASS = "[" + re.escape(_WS) + "]"
RESERVED_KEYS = frozenset((
    "join", "map", "on_error", "retry_policy", "context_filter",
    "output_mapping", "constraints", "execute_mode",
))


def parse_call(step):
    """Recognize one whole RUN step; this does not execute it."""
    if not isinstance(step, str):
        return None
    match = CALL.fullmatch(step.strip(_WS))
    return {"target": match[1], "store": match[2]} if match else None


def _unquote(text):
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1]
    return text


def _label_end(text, start, closing):
    """Find a delimiter without interpreting ordinary label punctuation."""
    pos = start
    while pos < len(text) and text[pos] in _WS:
        pos += 1
    if pos < len(text) and text[pos] in ("'", '"'):
        quote, escaped = text[pos], False
        pos += 1
        while pos < len(text):
            char = text[pos]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                pos += 1
                while pos < len(text) and text[pos] in _WS:
                    pos += 1
                if text.startswith(closing, pos):
                    return pos
                raise ValueError("Text after quoted label")
            pos += 1
        raise ValueError("Unclosed quoted label")
    stack, pos = [], start
    while pos < len(text):
        if not stack and text.startswith(closing, pos):
            return pos
        char = text[pos]
        if char in "[{(":
            stack.append(char)
        elif char in "]})":
            if not stack or "[{("["]})".index(char)] != stack.pop():
                raise ValueError("Unbalanced node shape")
        pos += 1
    raise ValueError("Unclosed label")


def _outside(text):
    """Yield connection positions; label protection does not trim its value."""
    pos = 0
    while pos < len(text):
        char = text[pos]
        if char in "[{(":
            left = "((" if text.startswith("((", pos) else char
            closing = {"[": "]", "{": "}", "(": ")", "((": "))"}[left]
            pos = _label_end(text, pos + len(left), closing) + len(closing)
            continue
        if text.startswith("-- ", pos):
            yield from range(pos, pos + 3)
            end = _label_end(text, pos + 3, "-->")
            yield from range(end, end + 3)
            pos = end + 3
            continue
        if text.startswith("-->", pos):
            yield from range(pos, pos + 3)
            pos += 3
            cursor = pos
            while cursor < len(text) and text[cursor] in " \t":
                cursor += 1
            if cursor < len(text) and text[cursor] == "|":
                yield from range(pos, cursor + 1)
                end = _label_end(text, cursor + 1, "|")
                yield end
                pos = end + 1
            continue
        if char in "]})":
            raise ValueError("Unbalanced node shape")
        yield pos
        pos += 1


def _bad_call(step):
    # Candidate recognition only; never use this normalization to execute a step.
    candidate = step.strip(_WS + _BAD_WS)
    gap = "[" + re.escape(_WS + _BAD_WS) + "]"
    if (candidate.startswith("RUN ")
            or re.match(r"^RUN" + gap + r"+aisop\.", candidate)
            or re.match(r"^aisop" + _WS_CLASS + r"*\[", candidate)):
        return True
    pos = 0
    while pos < len(step):
        boundary = pos == 0 or step[pos - 1] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
        back = pos - 1
        while back >= 0 and step[back] == "\\":
            back -= 1
        if step[pos] in ("'", '"') and boundary and (pos - back - 1) % 2 == 0:
            quote, end, escaped = step[pos], pos + 1, False
            while end < len(step):
                if escaped:
                    escaped = False
                elif step[end] == "\\":
                    escaped = True
                elif step[end] == quote:
                    break
                end += 1
            if end < len(step):
                pos = end + 1
                continue
        if boundary and step.startswith("RUN aisop.", pos):
            return True
        pos += 1
    return False


def _endpoints(text):
    cuts = [i for i in _outside(text) if text[i] == "&"]
    parts, start = [], 0
    for end in cuts + [len(text)]:
        raw = text[start:end].strip(_WS)
        match = re.fullmatch(r"([^" + re.escape(_WS) + r"\[\]{}()&|]+)(.*)", raw)
        if not match:
            raise ValueError("Unsupported endpoint")
        name, tail = match.groups()
        label, kind, raw_label = None, None, None
        if tail:
            shapes = (("((", "))", "end"), ("[", "]", "process"), ("{", "}", "decision"))
            for left, right, candidate in shapes:
                if tail.startswith(left) and tail.endswith(right):
                    raw_label = tail[len(left):-len(right)]
                    label, kind = _unquote(raw_label), candidate
                    break
            if label is None:
                raise ValueError("Unsupported node shape")
            if kind == "process" and re.fullmatch(r"aisop\.[A-Za-z_][A-Za-z0-9_]*", label):
                kind = "delegate"
        parts.append((name, label, kind, raw_label))
        start = end + 1
    return parts


def _mermaid_line(line):
    outside = set(_outside(line))
    segments, edges, start, pos = [], [], 0, 0
    while pos < len(line):
        if pos not in outside:
            pos += 1
            continue
        error, label, end = False, None, None
        if line.startswith("-.->", pos):
            error, end = True, pos + 4
        elif line.startswith("-->", pos):
            end = pos + 3
            cursor = end
            while cursor < len(line) and line[cursor] in " \t":
                cursor += 1
            if cursor < len(line) and line[cursor] == "|":
                closing = next((i for i in range(cursor + 1, len(line))
                                if i in outside and line[i] == "|"), None)
                if closing is None:
                    raise ValueError("Unclosed edge label")
                label, end = _unquote(line[cursor + 1:closing].strip(_WS)), closing + 1
        elif line.startswith("-- ", pos):
            closing = next((i for i in range(pos + 3, len(line))
                            if i in outside and line.startswith("-->", i)), None)
            if closing is None:
                raise ValueError("Unclosed long edge")
            label, end = _unquote(line[pos + 3:closing].strip(_WS)), closing + 3
        if end is None:
            pos += 1
            continue
        segments.append(_endpoints(line[start:pos]))
        edges.append((error, label))
        start, pos = end, end
    segments.append(_endpoints(line[start:]))
    return segments, edges


def _parse_mermaid(text):
    nodes, types, labels, raw_labels, lines, partial = {}, {}, {}, {}, {}, []
    for number, raw in enumerate(re.split(r"\r\n|\n|\r", text), 1):
        line = raw.strip(_WS)
        if not line or line.startswith("%%") or re.fullmatch(r"(?:graph|flowchart)" + _WS_CLASS + r"+(?:TD|TB|BT|LR|RL);?", line):
            continue
        try:
            segments, edges = _mermaid_line(line)
        except ValueError:
            partial.append(number)
            continue
        for group in segments:
            for name, label, kind, raw_label in group:
                nodes.setdefault(name, {})
                lines.setdefault(name, number)
                if label is not None:
                    types[name], labels[name] = kind, label
                    raw_labels[name] = raw_label
                    if kind == "delegate":
                        nodes[name]["delegate_to"] = label[6:]
        for i, (error, label) in enumerate(edges):
            for source, _, _, _ in segments[i]:
                for target, _, _, _ in segments[i + 1]:
                    node = nodes[source]
                    if error:
                        node["error"] = target
                    elif label is not None:
                        node.setdefault("branches", {})[label] = target
                    elif target not in node.setdefault("next", []):
                        node["next"].append(target)
    return {"nodes": nodes, "node_types": types, "node_labels": labels}, lines, partial, raw_labels


def parse_mermaid(mermaid_str: str) -> dict:
    """Parse the supported Mermaid subset; check() reports unsupported lines."""
    return _parse_mermaid(mermaid_str)[0]


def infer_node_type(node: dict) -> str:
    """Delegate takes precedence over its return-time conditional branches."""
    if not node:
        return "end"
    if "delegate_to" in node:
        return "delegate"
    if "branches" in node:
        return "decision"
    if "wait_for" in node:
        return "join"
    if "next" in node:
        return "fork" if len(node["next"]) > 1 else "process"
    return "end"


def _pointer(value):
    return _unicode_scalar(str(value), "_AISOP_LOCATION_UNICODE").replace("~", "~0").replace("/", "~1")


def list_graphs(data):
    """List graph declarations in input member order without executing them."""
    graphs = data[1]["content"]["aisop"]
    return [{"name": name, "format": "mermaid" if isinstance(body, str) else "jsonflow"}
            for name, body in graphs.items()]


def check(data, resolver=None, standalone=False):
    """Check only visited structure, not an arbitrary object's entire payload."""
    try:
        return _check_structure(data, resolver, standalone)
    except ValueError as error:
        if getattr(error, "code", None) != "_AISOP_LOCATION_UNICODE":
            raise
        return [{"severity": "ERROR", "code": "AISOP_E_SUBGRAPH_SHAPE",
                 "location": "/", "message": "Invalid Unicode in diagnostic key"}]


def _check_structure(data, resolver=None, standalone=False):
    """Check structure and local calls only; never load or execute a target."""
    issues = []

    def issue(suffix, location, message, warning=False):
        severity = "WARNING" if warning else "ERROR"
        prefix = "AISOP_W_SUBGRAPH_" if warning else "AISOP_E_SUBGRAPH_"
        issues.append({"severity": severity, "code": prefix + suffix,
                       "location": location, "message": message})

    def shape(location, message):
        issue("SHAPE", location, message)

    if not isinstance(data, list) or len(data) != 2 or not all(isinstance(x, dict) for x in data):
        shape("/", "Expected exactly two message objects")
        return issues
    for i, role in enumerate(("system", "user")):
        if data[i].get("role") != role or not isinstance(data[i].get("content"), dict):
            shape("/" + role, "Expected role and object content")
    if issues:
        return issues
    meta, user = data[0]["content"], data[1]["content"]
    for key in ("protocol", "axiom_0", "id", "name", "version", "flow_format"):
        if not isinstance(meta.get(key), str):
            shape("/system/content/" + key, "Required string field")
    if meta.get("axiom_0") != "Human_Sovereignty_and_Wellbeing":
        shape("/system/content/axiom_0", "Invalid foundation value")
    if meta.get("flow_format") not in ("mermaid", "jsonflow", "hybrid"):
        issue("FORMAT", "/system/content/flow_format", "Required graph format")
    if "params" in meta:
        if not isinstance(meta["params"], dict):
            issue("PARAMS", "/system/content/params", "Expected simple parameter type declarations")
        else:
            for name, value in meta["params"].items():
                if (not isinstance(name, str) or not IDENTIFIER.fullmatch(name)
                        or name in ("null", "true", "false")
                        or not isinstance(value, str)
                        or value not in ("string", "number", "boolean", "array", "object", "null")):
                    issue("PARAMS", "/system/content/params/" + _pointer(name), "Invalid parameter name or type")
    if not isinstance(user.get("instruction"), str):
        shape("/user/content/instruction", "Required string field")
    graphs, functions = user.get("aisop"), user.get("functions")
    if not isinstance(graphs, dict) or "main" not in graphs:
        shape("/user/content/aisop", "Expected graph object containing main")
    if not isinstance(functions, dict):
        shape("/user/content/functions", "Expected function object")
    if not isinstance(graphs, dict) or "main" not in graphs or not isinstance(functions, dict):
        return issues

    # Check lexical validity before collecting potential call references.
    steps = {}
    for name, function in functions.items():
        loc = "/user/content/functions/" + _pointer(name)
        if not IDENTIFIER.fullmatch(name):
            issue("NAME", loc, "Invalid function name")
        if not isinstance(function, dict):
            shape(loc, "Expected function object")
            continue
        steps[name] = []
        valid_steps = []
        for key, value in function.items():
            if key in RESERVED_KEYS:
                if key in ("join", "map", "on_error") and not isinstance(value, dict):
                    shape(loc + "/" + key, "Expected configuration object")
                if key == "execute_mode" and value not in ("inline", "agent"):
                    issue("EXECUTE_MODE", loc + "/" + key, "Expected inline or agent")
                continue
            if not STEP_KEY.fullmatch(key):
                issue("FUNCTION_KEY", loc + "/" + _pointer(key), "Expected stepN or a reserved function key")
                continue
            if not isinstance(value, str) or not value.strip(_WS):
                issue("STEP_VALUE", loc + "/" + key, "Expected a nonempty string step")
                continue
            valid_steps.append((key, value))
        for key, value in sorted(valid_steps, key=lambda item: (len(item[0][4:]), item[0][4:])):
            call = parse_call(value)
            if call:
                steps[name].append((key, call))
            elif _bad_call(value):
                issue("CALL_SYNTAX", loc + "/" + _pointer(key), "Expected one whole RUN step")

    details, partial_any, reuse = {}, False, {}
    for graph, body in graphs.items():
        loc = "/user/content/aisop/" + _pointer(graph)
        if not IDENTIFIER.fullmatch(graph):
            issue("NAME", loc, "Invalid graph name")
        actual = "mermaid" if isinstance(body, str) else "jsonflow"
        if not isinstance(body, (str, dict)):
            shape(loc, "Expected Mermaid string or JSON flow object")
            details[graph] = None
            continue
        if meta.get("flow_format") in ("mermaid", "jsonflow") and actual != meta["flow_format"]:
            issue("FORMAT", loc, "Graph does not match flow_format")
        if isinstance(body, str):
            parsed, source_lines, partial, raw_labels = _parse_mermaid(body)
            nodes, types = parsed["nodes"], parsed["node_types"]
            for line in partial:
                issue("PARSE_PARTIAL", loc + "/line/" + str(line), "Unsupported Mermaid line", True)
            partial_any = partial_any or bool(partial)
        else:
            nodes, types, source_lines, partial = body, {}, {}, []
        if not nodes:
            shape(loc, "Graph has no supported nodes")
            details[graph] = None
            continue
        details[graph] = (nodes, loc, source_lines, bool(partial))
        entry = next(iter(nodes))
        entry_known = not partial or (source_lines and min(partial) > source_lines[entry])
        incoming = {name: set() for name in nodes}
        for name, node in nodes.items():
            nl = loc + ("/line/" + str(source_lines[name]) + "/node" if isinstance(body, str) else "") + "/" + _pointer(name)
            if not IDENTIFIER.fullmatch(name):
                issue("NAME", nl, "Invalid node name")
            if not isinstance(node, dict):
                shape(nl, "Expected node object")
                continue
            if isinstance(body, str) and parsed["node_labels"].get(name, "").startswith("RUN "):
                issue("CALL_SYNTAX", nl, "RUN belongs in a function step, not a node label")
            if (isinstance(body, str) and types.get(name) == "process"
                    and _unquote(raw_labels.get(name, "").strip(_WS + _BAD_WS)).strip(_WS + _BAD_WS).startswith("aisop.")):
                issue("CALL_SYNTAX", nl, "Delegate label requires exactly aisop.<name>")
            end = types.get(name) == "end" if isinstance(body, str) else not node
            end_known = (name in types or bool(node)) if isinstance(body, str) else (
                not node or any(key in node for key in ("next", "branches", "error", "delegate_to", "wait_for")))
            reuse.setdefault(name, []).append((name == entry if entry_known else None,
                                               end if end_known else None))
            targets = []
            for key in ("next", "wait_for"):
                if key in node:
                    if not isinstance(node[key], list):
                        shape(nl + "/" + key, "Expected target list")
                    else:
                        targets.extend((v, nl + "/" + key + "/" + str(i), key == "next")
                                       for i, v in enumerate(node[key]))
            if "branches" in node:
                if not isinstance(node["branches"], dict):
                    shape(nl + "/branches", "Expected branch object")
                else:
                    targets.extend((v, nl + "/branches/" + _pointer(k), True)
                                   for k, v in node["branches"].items())
            if "error" in node:
                targets.append((node["error"], nl + "/error", False))
            function = functions.get(name, {})
            if isinstance(function, dict) and isinstance(function.get("on_error"), dict):
                targets.extend((v, nl + "/functions/on_error/" + _pointer(k), False)
                               for k, v in function["on_error"].items())
            for target, tl, normal in targets:
                if not isinstance(target, str):
                    shape(tl, "Expected target name")
                elif target not in nodes:
                    if not partial:
                        issue("LOCAL_EDGE", tl, "Target is not in the current graph")
                elif normal:
                    incoming[target].add(name)
        details[graph] += (incoming,)

    edges = {name: set() for name in graphs}
    inbound = set()
    for graph, info in details.items():
        if info is None:
            continue
        nodes, loc, source_lines, partial, incoming = info
        for name, node in nodes.items():
            if not isinstance(node, dict):
                continue
            nl = loc + ("/line/" + str(source_lines[name]) + "/node" if source_lines else "") + "/" + _pointer(name)
            function = functions.get(name, {})
            if not isinstance(function, dict):
                continue
            delegate = node.get("delegate_to")
            if "delegate_to" in node and (not isinstance(delegate, str) or not IDENTIFIER.fullmatch(delegate)):
                issue("CALL_SYNTAX", nl + "/delegate_to", "Delegate requires a bare graph name")
                delegate = None
            join = "join" in function and len(incoming.get(name, ())) > 1
            mapped = "map" in function
            if delegate and (join or mapped) or join and mapped:
                issue("CONFLICT", nl, "Delegate, active join and map are mutually exclusive")
            if mapped:
                iterator = function.get("map", {}).get("iterator") if isinstance(function.get("map"), dict) else None
                if iterator and steps.get(iterator):
                    issue("PARSE_PARTIAL", nl, "Indirect map calls are not expanded", True)
                    partial_any = True
            calls = [(key, call) for key, call in steps.get(name, ())]
            if delegate and not any(call["target"] == delegate for _, call in calls):
                calls.append(("delegate_to", {"target": delegate, "store": None}))
            for key, call in calls:
                cl = nl + ("/delegate_to" if key == "delegate_to" else "/functions/" + _pointer(key))
                target = call["target"]
                if target == "main":
                    issue("CALL_MAIN", cl, "main is only the top-level entry")
                elif target in graphs:
                    if details.get(target) is None:
                        issue("TARGET", cl, "Local target is invalid; no external fallback")
                    else:
                        edges[graph].add(target)
                        inbound.add(target)
                elif standalone:
                    issue("TARGET", cl, "Target missing in standalone program")
                elif resolver is None:
                    issue("RESOLVER", cl, "No consumer resolver; target not verified", True)
                else:
                    try:
                        found = resolver(target)
                        if type(found) is not bool:
                            issue("RESOLVER", cl, "Resolver must return a boolean")
                        elif not found:
                            issue("TARGET", cl, "Consumer reports target missing")
                    except Exception:
                        issue("RESOLVER", cl, "Consumer resolver raised an exception")

    # An edge belongs to a cycle iff its target can reach its source.
    for graph, targets in edges.items():
        for target in sorted(targets):
            pending, seen = [target], set()
            while pending:
                current = pending.pop()
                if current == graph:
                    issue("CYCLE", "/user/content/aisop/" + _pointer(graph) + "/calls/" + _pointer(target),
                          "Local subgraph call cycle")
                    break
                if current not in seen:
                    seen.add(current)
                    pending.extend(edges.get(current, ()))
    if not partial_any:
        for graph in graphs:
            if graph != "main" and graph not in inbound:
                issue("UNUSED", "/user/content/aisop/" + _pointer(graph), "No valid local incoming call", True)
    for name, roles in reuse.items():
        if len(roles) > 1 and not all(x[0] is True for x in roles) and not all(x[1] is True for x in roles):
            if all(x[0] is not None and x[1] is not None for x in roles):
                issue("NODE_REUSE", "/user/content/aisop/node_reuse/" + _pointer(name),
                      "Shared function has non-entry/non-end roles", True)
            else:
                issue("PARSE_PARTIAL", "/user/content/aisop/node_reuse/" + _pointer(name),
                      "Shared node roles cannot be established", True)
    return sorted(issues, key=lambda x: (x["location"].encode("utf-8"), x["code"], x["severity"]))


_MAX_NUMBER = 9007199254740991


def _reject(code):
    error = ValueError(code)
    error.code = code
    raise error


def _unicode_scalar(value, code):
    try:
        return value.encode("utf-16-le", "surrogatepass").decode("utf-16-le")
    except UnicodeError:
        _reject(code)


def _number_in_range(value):
    if type(value) is int:
        return abs(value) <= _MAX_NUMBER
    return math.isfinite(value) and abs(value) <= _MAX_NUMBER


def _fresh_json_tree(data):
    # Private entry: only a new standard-decoder tree, never caller objects.
    pending = [data]
    while pending:
        value = pending.pop()
        if isinstance(value, str):
            _unicode_scalar(value, "AISOP_E_JSON_INPUT")
        elif isinstance(value, dict):
            for key, child in value.items():
                _unicode_scalar(key, "AISOP_E_JSON_INPUT")
                pending.append(child)
        elif isinstance(value, list):
            pending.extend(value)
        elif type(value) in (int, float) and not _number_in_range(value):
            _reject("AISOP_E_JSON_INPUT")


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _reject("AISOP_E_JSON_INPUT")
        result[key] = value
    return result


def load(path: str) -> list:
    """Strict original-file input, then ordinary AISOP structural validation."""
    raw = Path(path).read_bytes()  # Keep native file IO errors outside input mapping.
    try:
        text = raw.decode("utf-8-sig")
        data = json.loads(text, object_pairs_hook=_unique_json_object,
                          parse_constant=lambda _: _reject("AISOP_E_JSON_INPUT"))
    except (UnicodeError, ValueError, OverflowError, RecursionError):
        _reject("AISOP_E_JSON_INPUT")
    _fresh_json_tree(data)
    validate(data)
    return data


def validate(data: list) -> None:
    """Preserve the original API: warnings do not raise ValueError."""
    errors = [item for item in check(data) if item["severity"] == "ERROR"]
    if errors:
        raise ValueError(errors[0]["code"] + " at " + errors[0]["location"] + ": " + errors[0]["message"])


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
    if "delegate_to" in node:
        return "delegate"
    if "branches" in node:
        return "decision"
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


def _expression_string(source, start):
    quote, pos, encoded = source[start], start + 1, ['"']
    while pos < len(source):
        char = source[pos]
        if char == quote:
            encoded.append('"')
            try:
                value = json.loads("".join(encoded))
            except ValueError:
                _reject("AISOP_E_EXPR_SYNTAX")
            return _unicode_scalar(value, "AISOP_E_EXPR_SYNTAX"), pos + 1
        if ord(char) < 32:
            _reject("AISOP_E_EXPR_SYNTAX")
        if char == "\\":
            if pos + 1 >= len(source):
                _reject("AISOP_E_EXPR_SYNTAX")
            escape = source[pos + 1]
            if escape == "'" and quote == "'":
                encoded.append("'")
                pos += 2
                continue
            if escape == "u":
                digits = source[pos + 2:pos + 6]
                if len(digits) != 4 or not re.fullmatch("[0-9A-Fa-f]{4}", digits):
                    _reject("AISOP_E_EXPR_SYNTAX")
                encoded.append(source[pos:pos + 6])
                pos += 6
                continue
            if escape not in '"\\/bfnrt':
                _reject("AISOP_E_EXPR_SYNTAX")
            encoded.append(source[pos:pos + 2])
            pos += 2
            continue
        encoded.append('\\"' if char == '"' else char)
        pos += 1
    _reject("AISOP_E_EXPR_SYNTAX")


def _expression_value(value):
    if value is None:
        return "null", None
    if type(value) is bool:
        return "boolean", value
    if type(value) in (int, float):
        if not _number_in_range(value):
            _reject("AISOP_E_EXPR_RANGE")
        return "number", value
    if type(value) is str:
        return "string", _unicode_scalar(value, "AISOP_E_EXPR_TYPE")
    if type(value) is dict:
        return "object", value
    if type(value) is list:
        return "array", value
    _reject("AISOP_E_EXPR_TYPE")


def _expression_tree(source):
    nodes, values, operators = [], [], []
    precedence = {"||": 1, "&&": 2, "==": 3, "!=": 3,
                  "<": 3, ">": 3, "<=": 3, ">=": 3}

    def reduce_operator():
        if len(values) < 2 or not operators:
            raise RuntimeError("Expression parser invariant")
        right, left = values.pop(), values.pop()
        nodes.append((operators.pop(), left, right))
        values.append(len(nodes) - 1)

    pos, operand, compared = 0, True, False
    while pos < len(source):
        if source[pos] in _WS:
            pos += 1
            continue
        if operand:
            bangs = 0
            while pos < len(source) and (source[pos] == "!" or source[pos] in _WS):
                if source[pos] == "!":
                    bangs += 1
                pos += 1
            if pos >= len(source):
                _reject("AISOP_E_EXPR_SYNTAX")
            char = source[pos]
            if char in ("'", '"'):
                value, pos = _expression_string(source, pos)
                node = ("literal", value)
            elif char in "-0123456789":
                match = re.match(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", source[pos:])
                if not match:
                    _reject("AISOP_E_EXPR_SYNTAX")
                token = match[0]
                value = float(token)
                if not _number_in_range(value):
                    _reject("AISOP_E_EXPR_RANGE")
                node, pos = ("literal", value), pos + len(token)
            else:
                match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", source[pos:])
                if not match:
                    _reject("AISOP_E_EXPR_SYNTAX")
                name, pos = match[0], pos + len(match[0])
                if name in ("null", "true", "false"):
                    node = ("literal", {"null": None, "true": True, "false": False}[name])
                else:
                    path = [name]
                    while pos < len(source) and source[pos] == ".":
                        match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", source[pos + 1:])
                        if not match:
                            _reject("AISOP_E_EXPR_SYNTAX")
                        path.append(match[0])
                        pos += len(match[0]) + 1
                    node = ("path", path)
            nodes.append(node)
            index = len(nodes) - 1
            for _ in range(bangs):
                nodes.append(("!", index))
                index = len(nodes) - 1
            values.append(index)
            operand = False
        else:
            match = re.match(r"!=|==|>=|<=|&&|\|\||[<>]", source[pos:])
            if not match:
                _reject("AISOP_E_EXPR_SYNTAX")
            op = match[0]
            if precedence[op] == 3:
                if compared:
                    _reject("AISOP_E_EXPR_SYNTAX")
                compared = True
            else:
                compared = False
            while operators and precedence[operators[-1]] >= precedence[op]:
                reduce_operator()
            operators.append(op)
            pos += len(op)
            operand = True
    if operand:
        _reject("AISOP_E_EXPR_SYNTAX")
    while operators:
        reduce_operator()
    if len(values) != 1:
        raise RuntimeError("Expression parser invariant")
    return nodes, values[0]


def eval_expression(expr: str, context: dict | None = None) -> bool:
    """Evaluate only the shared boolean grammar, with stable reason codes."""
    if not isinstance(expr, str):
        _reject("AISOP_E_EXPR_TYPE")
    if context is None:
        context = {}
    if type(context) is not dict:
        _reject("AISOP_E_EXPR_TYPE")
    nodes, root = _expression_tree(expr)
    results, pending = {}, [(root, 0)]
    while pending:
        index, phase = pending.pop()
        node, op = nodes[index], nodes[index][0]
        if op == "literal":
            results[index] = _expression_value(node[1])
        elif op == "path":
            value = context
            for name in node[1]:
                if type(value) is not dict:
                    _reject("AISOP_E_EXPR_TYPE")
                if name not in value:
                    _reject("AISOP_E_EXPR_UNDEFINED")
                value = value[name]
            results[index] = _expression_value(value)
        elif phase == 0:
            pending.extend(((index, 1), (node[1], 0)))
        elif phase == 1:
            kind, left = results[node[1]]
            if op == "!":
                if kind != "boolean":
                    _reject("AISOP_E_EXPR_TYPE")
                results[index] = "boolean", not left
            elif op in ("&&", "||") and kind != "boolean":
                _reject("AISOP_E_EXPR_TYPE")
            elif (op == "&&" and not left) or (op == "||" and left):
                results[index] = "boolean", left
            else:
                pending.extend(((index, 2), (node[2], 0)))
        else:
            left_kind, left = results[node[1]]
            right_kind, right = results[node[2]]
            if op in ("&&", "||"):
                if right_kind != "boolean":
                    _reject("AISOP_E_EXPR_TYPE")
                value = right
            elif op in ("==", "!="):
                if left_kind != right_kind:
                    value = False
                elif left_kind in ("array", "object"):
                    _reject("AISOP_E_EXPR_TYPE")
                else:
                    value = left == right
                if op == "!=":
                    value = not value
            else:
                if left_kind != "number" or right_kind != "number":
                    _reject("AISOP_E_EXPR_TYPE")
                value = {"<": lambda: left < right, ">": lambda: left > right,
                         "<=": lambda: left <= right, ">=": lambda: left >= right}[op]()
            results[index] = "boolean", value
    kind, value = results[root]
    if kind != "boolean":
        _reject("AISOP_E_EXPR_TYPE")
    return value


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

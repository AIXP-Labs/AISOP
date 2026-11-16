/**
 * AISOP Runtime — AI Standard Operating Protocol V1.0.0
 *
 * Loads .aisop.json files, validates structure, and provides utilities
 * for working with AISOP flow definitions.
 *
 * AISOP supports two flow graph formats:
 *   Mermaid (string):
 *     - name[text]    → process node (rectangle)
 *     - name{text}    → decision node (diamond)
 *     - name((text))  → end node (circle)
 *     - name[aisop.x] → delegate node (calls sub-task x)
 *     - -->            → normal edge (next)
 *     - -->|label|     → branch edge (conditional)
 *     - -.->           → error edge
 *   JSON flow (object):
 *     - { "next": [...] }       → process / fork
 *     - { "branches": {...} }   → decision
 *     - { "delegate_to": "..." } → delegate
 *     - { "wait_for": [...] }   → join
 *     - {}                      → end
 *
 * Zero dependencies beyond Node.js stdlib.
 */

const fs = require("fs");
const path = require("path");

// ── Mermaid Parser ─────────────────────────────────────────

const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*(?![\s\S])/;
const STEP_KEY = /^step[1-9][0-9]*(?![\s\S])/;
const CALL = /^RUN aisop\.([A-Za-z_][A-Za-z0-9_]*)(?:[ \t]+->[ \t]*([A-Za-z_][A-Za-z0-9_]*))?$/;
const WS = "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000";
const BAD_WS = "\u001c\u001d\u001e\u001f\u0085\ufeff";
const WS_CLASS = "[" + WS + "]";
const RESERVED_KEYS = new Set([
  "join", "map", "on_error", "retry_policy", "context_filter",
  "output_mapping", "constraints", "execute_mode",
]);
const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
const record = (obj) => obj !== null && typeof obj === "object" && !Array.isArray(obj);
const dictionary = () => Object.create(null);

function parseCall(step) {
  if (typeof step !== "string") return null;
  const m = CALL.exec(trimWhitespace(step));
  return m && !m[0].includes("\n") ? {target: m[1], store: m[2] || null} : null;
}

function unquote(text) {
  return text.length >= 2 && text[0] === text.at(-1) && ["'", '"'].includes(text[0])
    ? text.slice(1, -1) : text;
}

function trimWhitespace(text, chars = WS) {
  let start = 0, end = text.length;
  while (start < end && chars.includes(text[start])) start++;
  while (end > start && chars.includes(text[end - 1])) end--;
  return text.slice(start, end);
}

function labelEnd(text, start, closing) {
  let pos = start;
  while (pos < text.length && WS.includes(text[pos])) pos++;
  if (pos < text.length && ["'", '"'].includes(text[pos])) {
    const quote = text[pos++];
    let escaped = false;
    while (pos < text.length) {
      const char = text[pos];
      if (escaped) escaped = false;
      else if (char === "\\") escaped = true;
      else if (char === quote) {
        pos++;
        while (pos < text.length && WS.includes(text[pos])) pos++;
        if (text.startsWith(closing, pos)) return pos;
        throw new Error("Text after quoted label");
      }
      pos++;
    }
    throw new Error("Unclosed quoted label");
  }
  const stack = [];
  for (pos = start; pos < text.length; pos++) {
    if (!stack.length && text.startsWith(closing, pos)) return pos;
    const char = text[pos];
    if ("[{(".includes(char)) stack.push(char);
    else if ("]})".includes(char)) {
      if (!stack.length || "[{("["]})".indexOf(char)] !== stack.pop())
        throw new Error("Unbalanced node shape");
    }
  }
  throw new Error("Unclosed label");
}

function outside(text) {
  const result = new Set();
  let pos = 0;
  while (pos < text.length) {
    const char = text[pos];
    if ("[{(".includes(char)) {
      const left = text.startsWith("((", pos) ? "((" : char;
      const closing = {"[": "]", "{": "}", "(": ")", "((": "))"}[left];
      pos = labelEnd(text, pos + left.length, closing) + closing.length;
      continue;
    }
    if (text.startsWith("-- ", pos)) {
      for (let i = pos; i < pos + 3; i++) result.add(i);
      const end = labelEnd(text, pos + 3, "-->");
      for (let i = end; i < end + 3; i++) result.add(i);
      pos = end + 3;
      continue;
    }
    if (text.startsWith("-->", pos)) {
      for (let i = pos; i < pos + 3; i++) result.add(i);
      pos += 3;
      let cursor = pos;
      while (cursor < text.length && " \t".includes(text[cursor])) cursor++;
      if (text[cursor] === "|") {
        for (let i = pos; i <= cursor; i++) result.add(i);
        const end = labelEnd(text, cursor + 1, "|");
        result.add(end);
        pos = end + 1;
      }
      continue;
    }
    if ("]})".includes(char)) throw new Error("Unbalanced node shape");
    result.add(pos++);
  }
  return result;
}

function badCall(step) {
  // Candidate recognition only; never execute this normalized text.
  const candidate = trimWhitespace(step, WS + BAD_WS), gap = "[" + WS + BAD_WS + "]";
  if (candidate.startsWith("RUN ")
    || new RegExp("^RUN" + gap + "+aisop\\.").test(candidate)
    || new RegExp("^aisop" + WS_CLASS + "*\\[").test(candidate)) return true;
  let pos = 0;
  while (pos < step.length) {
    const boundary = pos === 0 || !/[A-Za-z0-9_]/.test(step[pos - 1]);
    let back = pos - 1;
    while (back >= 0 && step[back] === "\\") back--;
    if (["'", '"'].includes(step[pos]) && boundary && (pos - back - 1) % 2 === 0) {
      const quote = step[pos];
      let end = pos + 1, escaped = false;
      while (end < step.length) {
        if (escaped) escaped = false;
        else if (step[end] === "\\") escaped = true;
        else if (step[end] === quote) break;
        end++;
      }
      if (end < step.length) { pos = end + 1; continue; }
    }
    if (boundary && step.startsWith("RUN aisop.", pos)) return true;
    pos++;
  }
  return false;
}

function endpoints(text) {
  const cuts = [...outside(text)].filter(i => text[i] === "&");
  const parts = [];
  let start = 0;
  for (const end of [...cuts, text.length]) {
    const m = new RegExp("^([^" + WS + "\\[\\]{}()&|]+)([\\s\\S]*)$").exec(trimWhitespace(text.slice(start, end)));
    if (!m) throw new Error("Unsupported endpoint");
    const [, name, tail] = m;
    let label = null, kind = null, rawLabel = null;
    if (tail) {
      for (const [left, right, candidate] of [["((", "))", "end"], ["[", "]", "process"], ["{", "}", "decision"]]) {
        if (tail.startsWith(left) && tail.endsWith(right)) {
          rawLabel = tail.slice(left.length, -right.length);
          label = unquote(rawLabel); kind = candidate; break;
        }
      }
      if (label === null) throw new Error("Unsupported node shape");
      if (kind === "process" && /^aisop\.[A-Za-z_][A-Za-z0-9_]*$/.test(label)) kind = "delegate";
    }
    parts.push([name, label, kind, rawLabel]); start = end + 1;
  }
  return parts;
}

function mermaidLine(line) {
  const positions = outside(line), segments = [], edges = [];
  let start = 0, pos = 0;
  while (pos < line.length) {
    if (!positions.has(pos)) { pos++; continue; }
    let error = false, label = null, end = null;
    if (line.startsWith("-.->", pos)) { error = true; end = pos + 4; }
    else if (line.startsWith("-->", pos)) {
      end = pos + 3;
      let cursor = end;
      while (cursor < line.length && " \t".includes(line[cursor])) cursor++;
      if (line[cursor] === "|") {
        let closing = cursor + 1;
        while (closing < line.length && !(positions.has(closing) && line[closing] === "|")) closing++;
        if (closing === line.length) throw new Error("Unclosed edge label");
        label = unquote(trimWhitespace(line.slice(cursor + 1, closing))); end = closing + 1;
      }
    } else if (line.startsWith("-- ", pos)) {
      let closing = pos + 3;
      while (closing < line.length && !(positions.has(closing) && line.startsWith("-->", closing))) closing++;
      if (closing === line.length) throw new Error("Unclosed long edge");
      label = unquote(trimWhitespace(line.slice(pos + 3, closing))); end = closing + 3;
    }
    if (end === null) { pos++; continue; }
    segments.push(endpoints(line.slice(start, pos))); edges.push([error, label]);
    start = end; pos = end;
  }
  segments.push(endpoints(line.slice(start)));
  return [segments, edges];
}

function parseMermaidDetails(text) {
  const nodes = dictionary(), types = dictionary(), labels = dictionary(), rawLabels = dictionary(), lines = dictionary(), partial = [];
  for (const [index, raw] of text.split(/\r\n|\n|\r/).entries()) {
    const number = index + 1, line = trimWhitespace(raw);
    if (!line || line.startsWith("%%") || new RegExp("^(?:graph|flowchart)" + WS_CLASS + "+(?:TD|TB|BT|LR|RL);?$").test(line)) continue;
    let segments, edges;
    try { [segments, edges] = mermaidLine(line); }
    catch { partial.push(number); continue; }
    for (const group of segments) for (const [name, label, kind, rawLabel] of group) {
      if (!own(nodes, name)) nodes[name] = dictionary();
      if (!own(lines, name)) lines[name] = number;
      if (label !== null) {
        types[name] = kind; labels[name] = label; rawLabels[name] = rawLabel;
        if (kind === "delegate") nodes[name].delegate_to = label.slice(6);
      }
    }
    for (const [i, [error, label]] of edges.entries()) {
      for (const [source] of segments[i]) for (const [target] of segments[i + 1]) {
        const node = nodes[source];
        if (error) node.error = target;
        else if (label !== null) {
          if (!own(node, "branches")) node.branches = dictionary();
          node.branches[label] = target;
        } else {
          if (!own(node, "next")) node.next = [];
          if (!node.next.includes(target)) node.next.push(target);
        }
      }
    }
  }
  return [{nodes, node_types: types, node_labels: labels}, lines, partial, rawLabels];
}

function parseMermaid(text) {
  const parsed = parseMermaidDetails(text)[0];
  // Preserve ordinary public objects without using prototype-sensitive assignment.
  const nodes = Object.fromEntries(Object.entries(parsed.nodes).map(([name, node]) => [name,
    Object.fromEntries(Object.entries(node).map(([key, value]) => [key,
      key === "branches" ? Object.fromEntries(Object.entries(value)) : value]))]));
  return {nodes, node_types: Object.fromEntries(Object.entries(parsed.node_types)),
    node_labels: Object.fromEntries(Object.entries(parsed.node_labels))};
}

function inferNodeType(node) {
  if (!node || Object.keys(node).length === 0) return "end";
  if (own(node, "delegate_to")) return "delegate";
  if (own(node, "branches")) return "decision";
  if (own(node, "wait_for")) return "join";
  if (own(node, "next")) return node.next.length > 1 ? "fork" : "process";
  return "end";
}

function _inferJsonFlowType(node) { return inferNodeType(node); }
function pointer(value) { return unicodeScalar(String(value), "_AISOP_LOCATION_UNICODE").replace(/~/g, "~0").replace(/\//g, "~1"); }

function listGraphs(data) {
  return Object.entries(data[1].content.aisop).map(([name, body]) =>
    ({name, format: typeof body === "string" ? "mermaid" : "jsonflow"}));
}

function check(data, resolver = null, standalone = false) {
  try { return checkStructure(data, resolver, standalone); }
  catch (error) {
    if (error.code !== "_AISOP_LOCATION_UNICODE") throw error;
    return [{severity: "ERROR", code: "AISOP_E_SUBGRAPH_SHAPE", location: "/", message: "Invalid Unicode in diagnostic key"}];
  }
}

function checkStructure(data, resolver = null, standalone = false) {
  const issues = [];
  function issue(suffix, location, message, warning = false) {
    issues.push({severity: warning ? "WARNING" : "ERROR",
      code: (warning ? "AISOP_W_SUBGRAPH_" : "AISOP_E_SUBGRAPH_") + suffix, location, message});
  }
  function shape(location, message) { issue("SHAPE", location, message); }
  if (!Array.isArray(data) || data.length !== 2 || !data.every(record)) {
    shape("/", "Expected exactly two message objects"); return issues;
  }
  for (const [i, role] of ["system", "user"].entries()) {
    if (data[i].role !== role || !record(data[i].content)) shape("/" + role, "Expected role and object content");
  }
  if (issues.length) return issues;
  const meta = data[0].content, user = data[1].content;
  for (const key of ["protocol", "axiom_0", "id", "name", "version", "flow_format"]) {
    if (typeof meta[key] !== "string") shape("/system/content/" + key, "Required string field");
  }
  if (meta.axiom_0 !== "Human_Sovereignty_and_Wellbeing") shape("/system/content/axiom_0", "Invalid foundation value");
  if (!["mermaid", "jsonflow", "hybrid"].includes(meta.flow_format)) issue("FORMAT", "/system/content/flow_format", "Required graph format");
  if (own(meta, "params")) {
    if (!record(meta.params)) issue("PARAMS", "/system/content/params", "Expected simple parameter type declarations");
    else for (const [name, value] of Object.entries(meta.params)) {
      if (!IDENTIFIER.test(name) || ["null", "true", "false"].includes(name)
        || typeof value !== "string" || !["string", "number", "boolean", "array", "object", "null"].includes(value))
        issue("PARAMS", "/system/content/params/" + pointer(name), "Invalid parameter name or type");
    }
  }
  if (typeof user.instruction !== "string") shape("/user/content/instruction", "Required string field");
  const graphs = user.aisop, functions = user.functions;
  if (!record(graphs) || !own(graphs, "main")) shape("/user/content/aisop", "Expected graph object containing main");
  if (!record(functions)) shape("/user/content/functions", "Expected function object");
  if (!record(graphs) || !own(graphs, "main") || !record(functions)) return issues;
  const steps = dictionary();
  for (const [name, fn] of Object.entries(functions)) {
    const loc = "/user/content/functions/" + pointer(name);
    if (!IDENTIFIER.test(name)) issue("NAME", loc, "Invalid function name");
    if (!record(fn)) { shape(loc, "Expected function object"); continue; }
    steps[name] = [];
    const validSteps = [];
    for (const [key, value] of Object.entries(fn)) {
      if (RESERVED_KEYS.has(key)) {
        if (["join", "map", "on_error"].includes(key) && !record(value)) shape(loc + "/" + key, "Expected configuration object");
        if (key === "execute_mode" && !["inline", "agent"].includes(value)) issue("EXECUTE_MODE", loc + "/" + key, "Expected inline or agent");
        continue;
      }
      if (!STEP_KEY.test(key)) { issue("FUNCTION_KEY", loc + "/" + pointer(key), "Expected stepN or a reserved function key"); continue; }
      if (typeof value !== "string" || !trimWhitespace(value)) { issue("STEP_VALUE", loc + "/" + key, "Expected a nonempty string step"); continue; }
      validSteps.push([key, value]);
    }
    validSteps.sort(([a], [b]) => a.length - b.length || (a < b ? -1 : a > b ? 1 : 0));
    for (const [key, value] of validSteps) {
      const call = parseCall(value);
      if (call) steps[name].push([key, call]);
      else if (badCall(value)) issue("CALL_SYNTAX", loc + "/" + pointer(key), "Expected one whole RUN step");
    }
  }
  const details = dictionary(), reuse = dictionary();
  let partialAny = false;
  for (const [graph, body] of Object.entries(graphs)) {
    const loc = "/user/content/aisop/" + pointer(graph);
    if (!IDENTIFIER.test(graph)) issue("NAME", loc, "Invalid graph name");
    const actual = typeof body === "string" ? "mermaid" : "jsonflow";
    if (typeof body !== "string" && !record(body)) { shape(loc, "Expected Mermaid string or JSON flow object"); details[graph] = null; continue; }
    if (["mermaid", "jsonflow"].includes(meta.flow_format) && actual !== meta.flow_format) issue("FORMAT", loc, "Graph does not match flow_format");
    let nodes, types, labels, rawLabels, lines, partial;
    if (typeof body === "string") {
      const parsed = parseMermaidDetails(body);
      nodes = parsed[0].nodes; types = parsed[0].node_types; lines = parsed[1]; partial = parsed[2];
      labels = parsed[0].node_labels;
      rawLabels = parsed[3];
      for (const line of partial) issue("PARSE_PARTIAL", loc + "/line/" + line, "Unsupported Mermaid line", true);
      partialAny = partialAny || partial.length > 0;
    } else { nodes = body; types = dictionary(); lines = dictionary(); partial = []; }
    if (!Object.keys(nodes).length) { shape(loc, "Graph has no supported nodes"); details[graph] = null; continue; }
    const entry = Object.keys(nodes)[0];
    const entryKnown = !partial.length || Math.min(...partial) > lines[entry];
    const incoming = dictionary();
    for (const name of Object.keys(nodes)) incoming[name] = new Set();
    for (const [name, node] of Object.entries(nodes)) {
      const nl = loc + (typeof body === "string" ? "/line/" + lines[name] + "/node" : "") + "/" + pointer(name);
      if (!IDENTIFIER.test(name)) issue("NAME", nl, "Invalid node name");
      if (!record(node)) { shape(nl, "Expected node object"); continue; }
      if (typeof body === "string" && own(labels, name) && labels[name].startsWith("RUN "))
        issue("CALL_SYNTAX", nl, "RUN belongs in a function step, not a node label");
      if (typeof body === "string" && types[name] === "process" && own(rawLabels, name)
          && trimWhitespace(unquote(trimWhitespace(rawLabels[name], WS + BAD_WS)), WS + BAD_WS).startsWith("aisop."))
        issue("CALL_SYNTAX", nl, "Delegate label requires exactly aisop.<name>");
      const end = typeof body === "string" ? types[name] === "end" : Object.keys(node).length === 0;
      const endKnown = typeof body === "string" ? own(types, name) || Object.keys(node).length > 0
        : !Object.keys(node).length || ["next", "branches", "error", "delegate_to", "wait_for"].some(k => own(node, k));
      if (!own(reuse, name)) reuse[name] = [];
      reuse[name].push([entryKnown ? name === entry : null, endKnown ? end : null]);
      const targets = [];
      for (const key of ["next", "wait_for"]) if (own(node, key)) {
        if (!Array.isArray(node[key])) shape(nl + "/" + key, "Expected target list");
        else node[key].forEach((v, i) => targets.push([v, nl + "/" + key + "/" + i, key === "next"]));
      }
      if (own(node, "branches")) {
        if (!record(node.branches)) shape(nl + "/branches", "Expected branch object");
        else for (const [k, v] of Object.entries(node.branches)) targets.push([v, nl + "/branches/" + pointer(k), true]);
      }
      if (own(node, "error")) targets.push([node.error, nl + "/error", false]);
      const fn = own(functions, name) ? functions[name] : dictionary();
      if (record(fn) && record(fn.on_error)) for (const [k, v] of Object.entries(fn.on_error))
        targets.push([v, nl + "/functions/on_error/" + pointer(k), false]);
      for (const [target, tl, normal] of targets) {
        if (typeof target !== "string") shape(tl, "Expected target name");
        else if (!own(nodes, target)) { if (!partial.length) issue("LOCAL_EDGE", tl, "Target is not in the current graph"); }
        else if (normal) incoming[target].add(name);
      }
    }
    details[graph] = {nodes, loc, lines, partial: partial.length > 0, incoming};
  }
  const edges = dictionary(), inbound = new Set();
  for (const graph of Object.keys(graphs)) edges[graph] = new Set();
  for (const [graph, info] of Object.entries(details)) {
    if (info === null) continue;
    const {nodes, loc, lines, partial, incoming} = info;
    for (const [name, node] of Object.entries(nodes)) {
      if (!record(node)) continue;
      const nl = loc + (Object.keys(lines).length ? "/line/" + lines[name] + "/node" : "") + "/" + pointer(name);
      const fn = own(functions, name) ? functions[name] : dictionary();
      if (!record(fn)) continue;
      let delegate = own(node, "delegate_to") ? node.delegate_to : null;
      if (own(node, "delegate_to") && (typeof delegate !== "string" || !IDENTIFIER.test(delegate))) {
        issue("CALL_SYNTAX", nl + "/delegate_to", "Delegate requires a bare graph name"); delegate = null;
      }
      const join = own(fn, "join") && incoming[name].size > 1, mapped = own(fn, "map");
      if ((delegate && (join || mapped)) || (join && mapped)) issue("CONFLICT", nl, "Delegate, active join and map are mutually exclusive");
      if (mapped) {
        const iterator = record(fn.map) ? fn.map.iterator : null;
        if (iterator && own(steps, iterator) && steps[iterator].length) {
          issue("PARSE_PARTIAL", nl, "Indirect map calls are not expanded", true); partialAny = true;
        }
      }
      const calls = own(steps, name) ? [...steps[name]] : [];
      if (delegate && !calls.some(([, call]) => call.target === delegate)) calls.push(["delegate_to", {target: delegate, store: null}]);
      for (const [key, call] of calls) {
        const cl = nl + (key === "delegate_to" ? "/delegate_to" : "/functions/" + pointer(key));
        const target = call.target;
        if (target === "main") issue("CALL_MAIN", cl, "main is only the top-level entry");
        else if (own(graphs, target)) {
          if (details[target] === null) issue("TARGET", cl, "Local target is invalid; no external fallback");
          else { edges[graph].add(target); inbound.add(target); }
        } else if (standalone) issue("TARGET", cl, "Target missing in standalone program");
        else if (resolver === null) issue("RESOLVER", cl, "No consumer resolver; target not verified", true);
        else {
          try {
            const found = resolver(target);
            if (typeof found !== "boolean") issue("RESOLVER", cl, "Resolver must return a boolean");
            else if (!found) issue("TARGET", cl, "Consumer reports target missing");
          } catch { issue("RESOLVER", cl, "Consumer resolver raised an exception"); }
        }
      }
    }
  }
  for (const [graph, targets] of Object.entries(edges)) for (const target of [...targets].sort()) {
    const pending = [target], seen = new Set();
    while (pending.length) {
      const current = pending.pop();
      if (current === graph) { issue("CYCLE", "/user/content/aisop/" + pointer(graph) + "/calls/" + pointer(target), "Local subgraph call cycle"); break; }
      if (!seen.has(current)) { seen.add(current); pending.push(...edges[current]); }
    }
  }
  if (!partialAny) for (const graph of Object.keys(graphs))
    if (graph !== "main" && !inbound.has(graph)) issue("UNUSED", "/user/content/aisop/" + pointer(graph), "No valid local incoming call", true);
  for (const [name, roles] of Object.entries(reuse)) {
    if (roles.length > 1 && !roles.every(x => x[0] === true) && !roles.every(x => x[1] === true)) {
      if (roles.every(x => x[0] !== null && x[1] !== null)) issue("NODE_REUSE", "/user/content/aisop/node_reuse/" + pointer(name), "Shared function has non-entry/non-end roles", true);
      else issue("PARSE_PARTIAL", "/user/content/aisop/node_reuse/" + pointer(name), "Shared node roles cannot be established", true);
    }
  }
  return issues.sort((a, b) => {
    for (const key of ["location", "code", "severity"]) {
      const order = Buffer.compare(Buffer.from(a[key]), Buffer.from(b[key]));
      if (order) return order;
    }
    return 0;
  });
}

const MAX_NUMBER = 9007199254740991;
function reject(code) { const error = new Error(code); error.code = code; throw error; }
function unicodeScalar(value, code) {
  for (let i = 0; i < value.length; i++) {
    const c = value.charCodeAt(i);
    if (c >= 0xd800 && c <= 0xdbff) {
      const next = value.charCodeAt(i + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) reject(code);
      i++;
    } else if (c >= 0xdc00 && c <= 0xdfff) reject(code);
  }
  return value;
}
function freshJsonTree(data) {
  // Private entry: only the new standard-decoder tree, never caller objects.
  const pending = [data];
  while (pending.length) {
    const value = pending.pop();
    if (typeof value === "string") unicodeScalar(value, "AISOP_E_JSON_INPUT");
    else if (typeof value === "number") {
      if (!Number.isFinite(value) || Math.abs(value) > MAX_NUMBER) reject("AISOP_E_JSON_INPUT");
    } else if (Array.isArray(value)) {
      for (const child of value) pending.push(child);
    } else if (value !== null && typeof value === "object") {
      for (const [key, child] of Object.entries(value)) {
        unicodeScalar(key, "AISOP_E_JSON_INPUT"); pending.push(child);
      }
    }
  }
}
function uniqueJsonKeys(text) {
  const stack = [];
  let pos = 0;
  while (pos < text.length) {
    const before = pos, c = text[pos];
    if (c === '"') {
      const start = pos++;
      let escaped = false;
      while (pos < text.length) {
        if (escaped) escaped = false;
        else if (text[pos] === "\\") escaped = true;
        else if (text[pos] === '"') break;
        pos++;
      }
      if (pos === text.length) throw new Error("JSON scanner invariant");
      pos++;
      const frame = stack.at(-1);
      if (frame && frame.object && frame.key) {
        const key = JSON.parse(text.slice(start, pos));
        if (frame.keys.has(key)) reject("AISOP_E_JSON_INPUT");
        frame.keys.add(key); frame.key = false;
      }
    } else if (c === "{" || c === "[") {
      stack.push({object: c === "{", key: c === "{", keys: new Set()}); pos++;
    } else if (c === "}" || c === "]") {
      const frame = stack.pop();
      if (!frame || frame.object !== (c === "}")) throw new Error("JSON scanner invariant");
      pos++;
    } else {
      if (c === "," && stack.length && stack.at(-1).object) stack.at(-1).key = true;
      pos++;
    }
    if (pos <= before) throw new Error("JSON scanner did not advance");
  }
  if (stack.length) throw new Error("JSON scanner invariant");
}
function load(filePath) {
  const bytes = fs.readFileSync(filePath); // Native IO errors retain their identity.
  let text, data;
  try { text = new TextDecoder("utf-8", {fatal: true, ignoreBOM: true}).decode(bytes); }
  catch (error) { if (error instanceof TypeError) reject("AISOP_E_JSON_INPUT"); throw error; }
  if (text.startsWith("\ufeff")) text = text.slice(1);
  try { data = JSON.parse(text); }
  catch (error) { if (error instanceof SyntaxError) reject("AISOP_E_JSON_INPUT"); throw error; }
  uniqueJsonKeys(text);
  freshJsonTree(data);
  validate(data); // Do not map structural AISOP errors to JSON_INPUT.
  return data;
}

function validate(data) {
  const errors = check(data).filter(x => x.severity === "ERROR");
  if (errors.length) throw new Error(errors[0].code + " at " + errors[0].location + ": " + errors[0].message);
}

// ── Metadata ────────────────────────────────────────────────

function getMetadata(data) {
  return data[0].content;
}

function getTasks(data) {
  return (data[1].content || {}).aisop || {};
}

function getFunctions(data) {
  return (data[1].content || {}).functions || {};
}

// ── Flow Analysis ───────────────────────────────────────────

function listNodes(data, task = "main") {
  const tasks = getTasks(data);
  const taskBody = tasks[task];
  if (!taskBody) return [];

  // Mermaid format (string)
  if (typeof taskBody === "string") {
    const parsed = parseMermaid(taskBody);
    const nodesDict = parsed.nodes;
    const shapeTypes = parsed.node_types;

    const result = [];
    for (const [name, node] of Object.entries(nodesDict)) {
      let ntype = shapeTypes[name] || inferNodeType(node);
      if (node.next && node.next.length > 1 && ntype === "process") ntype = "fork";

      const info = { name, type: ntype };
      if (node.next) info.next = node.next;
      if (node.branches) info.branches = node.branches;
      if (node.delegate_to) info.delegate_to = node.delegate_to;
      if (node.error) info.error = node.error;
      result.push(info);
    }
    return result;
  }

  // JSON flow format (object)
  if (typeof taskBody === "object") {
    const result = [];
    for (const [name, node] of Object.entries(taskBody)) {
      const info = { name, type: _inferJsonFlowType(node) };
      for (const key of ["next", "branches", "delegate_to", "error", "wait_for"]) {
        if (key in node) info[key] = node[key];
      }
      result.push(info);
    }
    return result;
  }

  return [];
}

function renderFlow(data, task = "main") {
  const tasks = getTasks(data);
  const taskBody = tasks[task];
  if (typeof taskBody === "string") return taskBody;
  if (typeof taskBody === "object") return JSON.stringify(taskBody, null, 2);
  return "(empty)";
}

// ── sys.* System Call Parsing ─────────────────────────────────

// Matches sys calls: sys.io.confirm('msg') -> var
const SYS_CALL_RE = /^(sys(?:\.\w+){1,3})\((.*)?\)\s*(?:->\s*(\w+))?$/;

const VALID_SYS_CALLS = new Set([
  "sys.io.confirm", "sys.io.input", "sys.io.select",
  "sys.io.notify", "sys.io.print", "sys.io.read", "sys.io.write",
  "sys.run", "sys.run.timeout", "sys.run.bg",
  "sys.assert",
  "sys.llm", "sys.llm.json", "sys.llm.classify",
  "sys.code.exec", "sys.code.eval",
  "sys.state.get", "sys.state.set", "sys.state.save", "sys.state.load",
  "sys.event.emit", "sys.event.wait",
  "sys.security.audit", "sys.security.redact",
]);

const SYS_ERROR_TYPES = new Set([
  "confirm_rejected", "confirm_timeout", "assertion_error",
  "command_error", "command_timeout", "io_error",
]);

/**
 * Classify a step text into one of three modes (§5.3).
 * @param {string} stepText
 * @returns {'sys_call'|'sub_task'|'natural_language'}
 */
function classifyStep(stepText) {
  const stripped = stepText.trim();
  if (stripped.startsWith("sys.")) return "sys_call";
  if (stripped.startsWith("RUN aisop.")) return "sub_task";
  return "natural_language";
}

/**
 * Parse a sys.* call from step text (§6.10).
 * @param {string} stepText
 * @returns {{name: string, args: string, store: string|null, valid: boolean}|null}
 */
function parseSysCall(stepText) {
  const m = stepText.trim().match(SYS_CALL_RE);
  if (!m) return null;
  const name = m[1];
  return {
    name,
    args: (m[2] || "").trim(),
    store: m[3] || null,
    valid: VALID_SYS_CALLS.has(name),
  };
}

/**
 * Split expression on delimiter, but only outside quoted strings.
 * Returns array of parts if delimiter found outside quotes, else null.
 * @param {string} expr
 * @param {string} delimiter
 * @returns {string[]|null}
 */
function splitOutsideQuotes(expr, delimiter) {
  const parts = [];
  let current = [];
  let inQuote = null; // null, "'", or '"'
  let i = 0;
  while (i < expr.length) {
    const ch = expr[i];
    if ((ch === "'" || ch === '"') && inQuote === null) {
      inQuote = ch;
    } else if (ch === inQuote) {
      inQuote = null;
    }
    if (inQuote === null && expr.slice(i, i + delimiter.length) === delimiter) {
      parts.push(current.join(""));
      current = [];
      i += delimiter.length;
      continue;
    }
    current.push(ch);
    i++;
  }
  parts.push(current.join(""));
  return parts.length > 1 ? parts : null;
}

/**
 * Find first occurrence of operator outside quoted strings. Returns -1 if not found.
 * @param {string} expr
 * @param {string} op
 * @returns {number}
 */
function findOperatorOutsideQuotes(expr, op) {
  let inQuote = null;
  for (let i = 0; i < expr.length; i++) {
    const ch = expr[i];
    if ((ch === "'" || ch === '"') && inQuote === null) {
      inQuote = ch;
    } else if (ch === inQuote) {
      inQuote = null;
    }
    if (inQuote === null && expr.slice(i, i + op.length) === op) {
      return i;
    }
  }
  return -1;
}

/**
 * Evaluate a deterministic expression (§6.11).
 * Supports: ==, !=, >, <, >=, <=, &&, ||, !, null checks, member access.
 * Does NOT go through LLM. Respects quoted string boundaries.
 * @param {string} expr
 * @param {object} context
 * @returns {*}
 */
function expressionString(source, start) {
  const quote = source[start], encoded = ['"'];
  let pos = start + 1;
  while (pos < source.length) {
    const c = source[pos];
    if (c === quote) {
      encoded.push('"');
      let value;
      try { value = JSON.parse(encoded.join("")); }
      catch { reject("AISOP_E_EXPR_SYNTAX"); }
      return [unicodeScalar(value, "AISOP_E_EXPR_SYNTAX"), pos + 1];
    }
    if (c.charCodeAt(0) < 32) reject("AISOP_E_EXPR_SYNTAX");
    if (c === "\\") {
      if (pos + 1 >= source.length) reject("AISOP_E_EXPR_SYNTAX");
      const escape = source[pos + 1];
      if (escape === "'" && quote === "'") { encoded.push("'"); pos += 2; continue; }
      if (escape === "u") {
        const digits = source.slice(pos + 2, pos + 6);
        if (!/^[0-9a-fA-F]{4}$/.test(digits)) reject("AISOP_E_EXPR_SYNTAX");
        encoded.push(source.slice(pos, pos + 6)); pos += 6; continue;
      }
      if (!'"\\/bfnrt'.includes(escape)) reject("AISOP_E_EXPR_SYNTAX");
      encoded.push(source.slice(pos, pos + 2)); pos += 2; continue;
    }
    encoded.push(c === '"' ? '\\"' : c); pos++;
  }
  reject("AISOP_E_EXPR_SYNTAX");
}
function dataObject(value) {
  if (!record(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}
function expressionValue(value) {
  if (value === null) return ["null", null];
  if (typeof value === "boolean") return ["boolean", value];
  if (typeof value === "number") {
    if (!Number.isFinite(value) || Math.abs(value) > MAX_NUMBER) reject("AISOP_E_EXPR_RANGE");
    return ["number", value];
  }
  if (typeof value === "string") return ["string", unicodeScalar(value, "AISOP_E_EXPR_TYPE")];
  if (Array.isArray(value)) return ["array", value];
  if (dataObject(value)) return ["object", value];
  reject("AISOP_E_EXPR_TYPE");
}
function expressionTree(source) {
  const nodes = [], values = [], operators = [];
  const precedence = {"||": 1, "&&": 2, "==": 3, "!=": 3, "<": 3, ">": 3, "<=": 3, ">=": 3};
  function reduce() {
    if (values.length < 2 || !operators.length) throw new Error("Expression parser invariant");
    const right = values.pop(), left = values.pop();
    nodes.push([operators.pop(), left, right]); values.push(nodes.length - 1);
  }
  let pos = 0, operand = true, compared = false;
  while (pos < source.length) {
    if (WS.includes(source[pos])) { pos++; continue; }
    if (operand) {
      let bangs = 0;
      while (pos < source.length && (source[pos] === "!" || WS.includes(source[pos]))) {
        if (source[pos] === "!") bangs++;
        pos++;
      }
      if (pos === source.length) reject("AISOP_E_EXPR_SYNTAX");
      const c = source[pos];
      let node;
      if (["'", '"'].includes(c)) {
        const parsed = expressionString(source, pos); node = ["literal", parsed[0]]; pos = parsed[1];
      } else if ("-0123456789".includes(c)) {
        const m = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(source.slice(pos));
        if (!m) reject("AISOP_E_EXPR_SYNTAX");
        const value = Number(m[0]);
        if (!Number.isFinite(value) || Math.abs(value) > MAX_NUMBER) reject("AISOP_E_EXPR_RANGE");
        node = ["literal", value]; pos += m[0].length;
      } else {
        const m = /^[A-Za-z_][A-Za-z0-9_]*/.exec(source.slice(pos));
        if (!m) reject("AISOP_E_EXPR_SYNTAX");
        const name = m[0]; pos += name.length;
        if (["null", "true", "false"].includes(name)) node = ["literal", {null: null, true: true, false: false}[name]];
        else {
          const parts = [name];
          while (source[pos] === ".") {
            const part = /^[A-Za-z_][A-Za-z0-9_]*/.exec(source.slice(pos + 1));
            if (!part) reject("AISOP_E_EXPR_SYNTAX");
            parts.push(part[0]); pos += part[0].length + 1;
          }
          node = ["path", parts];
        }
      }
      nodes.push(node); let index = nodes.length - 1;
      for (let i = 0; i < bangs; i++) { nodes.push(["!", index]); index = nodes.length - 1; }
      values.push(index); operand = false;
    } else {
      const m = /^(?:!=|==|>=|<=|&&|\|\||[<>])/.exec(source.slice(pos));
      if (!m) reject("AISOP_E_EXPR_SYNTAX");
      const op = m[0];
      if (precedence[op] === 3) { if (compared) reject("AISOP_E_EXPR_SYNTAX"); compared = true; }
      else compared = false;
      while (operators.length && precedence[operators.at(-1)] >= precedence[op]) reduce();
      operators.push(op); pos += op.length; operand = true;
    }
  }
  if (operand) reject("AISOP_E_EXPR_SYNTAX");
  while (operators.length) reduce();
  if (values.length !== 1) throw new Error("Expression parser invariant");
  return [nodes, values[0]];
}
function evalExpression(expr, context = null) {
  if (typeof expr !== "string") reject("AISOP_E_EXPR_TYPE");
  if (context === null) context = {};
  if (!dataObject(context)) reject("AISOP_E_EXPR_TYPE");
  const [nodes, root] = expressionTree(expr), results = new Map(), pending = [[root, 0]];
  while (pending.length) {
    const [index, phase] = pending.pop(), node = nodes[index], op = node[0];
    if (op === "literal") results.set(index, expressionValue(node[1]));
    else if (op === "path") {
      let value = context;
      for (const name of node[1]) {
        if (!dataObject(value)) reject("AISOP_E_EXPR_TYPE");
        const member = Object.getOwnPropertyDescriptor(value, name);
        if (!member) reject("AISOP_E_EXPR_UNDEFINED");
        if (!own(member, "value")) reject("AISOP_E_EXPR_TYPE");
        value = member.value;
      }
      results.set(index, expressionValue(value));
    } else if (phase === 0) pending.push([index, 1], [node[1], 0]);
    else if (phase === 1) {
      const [kind, left] = results.get(node[1]);
      if (op === "!") {
        if (kind !== "boolean") reject("AISOP_E_EXPR_TYPE");
        results.set(index, ["boolean", !left]);
      } else if ((op === "&&" || op === "||") && kind !== "boolean") reject("AISOP_E_EXPR_TYPE");
      else if ((op === "&&" && !left) || (op === "||" && left)) results.set(index, ["boolean", left]);
      else pending.push([index, 2], [node[2], 0]);
    } else {
      const [leftKind, left] = results.get(node[1]), [rightKind, right] = results.get(node[2]);
      let value;
      if (op === "&&" || op === "||") {
        if (rightKind !== "boolean") reject("AISOP_E_EXPR_TYPE");
        value = right;
      } else if (op === "==" || op === "!=") {
        if (leftKind !== rightKind) value = false;
        else if (leftKind === "array" || leftKind === "object") reject("AISOP_E_EXPR_TYPE");
        else value = left === right;
        if (op === "!=") value = !value;
      } else {
        if (leftKind !== "number" || rightKind !== "number") reject("AISOP_E_EXPR_TYPE");
        value = op === "<" ? left < right : op === ">" ? left > right : op === "<=" ? left <= right : left >= right;
      }
      results.set(index, ["boolean", value]);
    }
  }
  const [kind, value] = results.get(root);
  if (kind !== "boolean") reject("AISOP_E_EXPR_TYPE");
  return value;
}

// ── Prompt Builder ──────────────────────────────────────────

function buildPrompt(data, userInput, systemPrompt = "") {
  const result = JSON.parse(JSON.stringify(data));
  if (systemPrompt) result[0].content.system_prompt = systemPrompt;
  result[1].content.user_input = userInput;
  return JSON.stringify(result, null, 2);
}

// ── Exports ─────────────────────────────────────────────────

module.exports = {
  listGraphs,
  parseCall,
  check,
  parseMermaid,
  inferNodeType,
  load,
  validate,
  getMetadata,
  getTasks,
  getFunctions,
  listNodes,
  renderFlow,
  buildPrompt,
  classifyStep,
  parseSysCall,
  evalExpression,
  splitOutsideQuotes,
  findOperatorOutsideQuotes,
  VALID_SYS_CALLS,
  SYS_ERROR_TYPES,
  SYS_CALL_RE,
};

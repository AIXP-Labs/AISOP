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

function _extractNodeShape(text, nodeTypes, nodeLabels, delegateTargets) {
  text = text.trim();
  if (!text) return null;

  let m;

  // name((text)) → end
  m = text.match(/^(\w+)\(\((.+?)\)\)$/);
  if (m) {
    nodeTypes[m[1]] = "end";
    nodeLabels[m[1]] = m[2];
    return m[1];
  }

  // name{text} → decision
  m = text.match(/^(\w+)\{(.+?)\}$/);
  if (m) {
    nodeTypes[m[1]] = "decision";
    nodeLabels[m[1]] = m[2];
    return m[1];
  }

  // name[text] → process or delegate
  m = text.match(/^(\w+)\[(.+?)\]$/);
  if (m) {
    const name = m[1];
    const label = m[2];
    if (label.startsWith("aisop.")) {
      nodeTypes[name] = "delegate";
      delegateTargets[name] = label.slice("aisop.".length);
    } else {
      nodeTypes[name] = "process";
    }
    nodeLabels[name] = label;
    return name;
  }

  // plain name (no shape)
  m = text.match(/^(\w+)$/);
  if (m) return m[1];

  return null;
}

function parseMermaid(mermaidStr) {
  const nodes = {};
  const nodeTypes = {};
  const nodeLabels = {};
  const delegateTargets = {};

  const lines = mermaidStr.trim().split("\n");

  for (let line of lines) {
    line = line.trim();
    if (!line || line.startsWith("graph ") || line.startsWith("%%")) continue;

    const parts = line.split(/\s*(-->\|[^|]+\||-->|-\.->)\s*/);

    if (parts.length < 3) {
      _extractNodeShape(parts[0].trim(), nodeTypes, nodeLabels, delegateTargets);
      continue;
    }

    for (let i = 0; i < parts.length - 2; i += 2) {
      const srcRaw = parts[i].trim();
      const edgeRaw = parts[i + 1].trim();
      const dstRaw = parts[i + 2].trim();

      const src = _extractNodeShape(srcRaw, nodeTypes, nodeLabels, delegateTargets);
      const dst = _extractNodeShape(dstRaw, nodeTypes, nodeLabels, delegateTargets);

      if (!src || !dst) continue;

      if (!nodes[src]) nodes[src] = {};
      if (!nodes[dst]) nodes[dst] = {};

      if (edgeRaw.includes("-.->")) {
        nodes[src].error = dst;
      } else if (edgeRaw.includes("|")) {
        const labelMatch = edgeRaw.match(/\|(.+?)\|/);
        if (labelMatch) {
          if (!nodes[src].branches) nodes[src].branches = {};
          nodes[src].branches[labelMatch[1]] = dst;
        }
      } else {
        if (!nodes[src].next) nodes[src].next = [];
        if (!nodes[src].next.includes(dst)) nodes[src].next.push(dst);
      }
    }
  }

  for (const [name, target] of Object.entries(delegateTargets)) {
    if (nodes[name]) nodes[name].delegate_to = target;
  }

  return { nodes, node_types: nodeTypes, node_labels: nodeLabels };
}

function inferNodeType(node) {
  if (!node || Object.keys(node).length === 0) return "end";
  if (node.branches) return "decision";
  if (node.delegate_to) return "delegate";
  if (node.next) return node.next.length > 1 ? "fork" : "process";
  return "end";
}

function _inferJsonFlowType(node) {
  if (!node || Object.keys(node).length === 0) return "end";
  if (node.branches) return "decision";
  if (node.delegate_to) return "delegate";
  if (node.wait_for) return "join";
  if (node.next) return node.next.length > 1 ? "fork" : "process";
  return "end";
}

// ── Load & Validate ─────────────────────────────────────────

function load(filePath) {
  const raw = fs.readFileSync(filePath, "utf-8").replace(/^\uFEFF/, "");
  const data = JSON.parse(raw);
  validate(data);
  return data;
}

function validate(data) {
  if (!Array.isArray(data) || data.length !== 2) {
    throw new Error("AISOP file must be a JSON array with exactly 2 elements");
  }

  const [system, user] = data;
  if (!system || system.role !== "system") {
    throw new Error("First element must have role='system'");
  }
  if (!user || user.role !== "user") {
    throw new Error("Second element must have role='user'");
  }

  const sc = (system.content) || {};
  for (const field of ["protocol", "axiom_0", "id", "name", "version", "flow_format"]) {
    if (!(field in sc)) {
      throw new Error(`system.content missing required field: ${field}`);
    }
  }

  if (sc.axiom_0 !== "Human_Sovereignty_and_Wellbeing") {
    throw new Error('axiom_0 must be "Human_Sovereignty_and_Wellbeing"');
  }

  if (!["mermaid", "jsonflow", "hybrid"].includes(sc.flow_format)) {
    throw new Error('flow_format must be "mermaid", "jsonflow", or "hybrid"');
  }

  const uc = (user.content) || {};
  for (const field of ["instruction", "aisop", "functions"]) {
    if (!(field in uc)) {
      throw new Error(`user.content missing required field: ${field}`);
    }
  }
  if (!("main" in uc.aisop)) {
    throw new Error("aisop must contain a 'main' task");
  }

  for (const [taskName, taskBody] of Object.entries(uc.aisop)) {
    if (typeof taskBody === "string") {
      const parsed = parseMermaid(taskBody);
      if (Object.keys(parsed.nodes).length === 0) {
        throw new Error(`Task '${taskName}' has no parseable nodes`);
      }
    } else if (typeof taskBody === "object" && taskBody !== null) {
      if (Object.keys(taskBody).length === 0) {
        throw new Error(`Task '${taskName}' is empty`);
      }
    } else {
      throw new Error(`Task '${taskName}' must be Mermaid string or JSON flow object`);
    }
  }
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
function evalExpression(expr, context = {}) {
  expr = expr.trim();

  function resolveVar(name) {
    const parts = name.trim().split(".");
    let obj = context;
    for (const part of parts) {
      if (obj && typeof obj === "object" && part in obj) {
        obj = obj[part];
      } else {
        throw new Error(`Undefined variable: ${name}`);
      }
    }
    return obj;
  }

  function isLiteral(token) {
    if (token === "null" || token === "undefined") return true;
    if (token === "true" || token === "false") return true;
    if (!isNaN(Number(token)) && token !== "") return true;
    if ((token.startsWith("'") && token.endsWith("'")) ||
        (token.startsWith('"') && token.endsWith('"'))) return true;
    return false;
  }

  function parseLiteral(token) {
    if (token === "null" || token === "undefined") return null;
    if (token === "true") return true;
    if (token === "false") return false;
    if (!isNaN(Number(token)) && token !== "") return Number(token);
    if ((token.startsWith("'") && token.endsWith("'")) ||
        (token.startsWith('"') && token.endsWith('"'))) return token.slice(1, -1);
    return token;
  }

  function resolveToken(token) {
    token = token.trim();
    return isLiteral(token) ? parseLiteral(token) : resolveVar(token);
  }

  function evalComparison(subExpr) {
    subExpr = subExpr.trim();
    // Handle unary NOT: !var
    if (subExpr.startsWith("!")) {
      const inner = subExpr.slice(1).trim();
      return !evalComparison(inner);
    }
    const ops = ["!=", "==", ">=", "<=", ">", "<"];
    for (const op of ops) {
      const idx = findOperatorOutsideQuotes(subExpr, op);
      if (idx !== -1) {
        const left = subExpr.slice(0, idx).trim();
        const right = subExpr.slice(idx + op.length).trim();
        const leftVal = resolveToken(left);
        const rightVal = resolveToken(right);
        switch (op) {
          case "!=": return leftVal !== rightVal;
          case "==": return leftVal === rightVal;
          case ">=": return leftVal >= rightVal;
          case "<=": return leftVal <= rightVal;
          case ">":  return leftVal > rightVal;
          case "<":  return leftVal < rightVal;
        }
      }
    }
    // Single token — resolve as truthy/falsy
    return Boolean(resolveToken(subExpr));
  }

  // Handle || (lowest precedence) — split outside quotes only
  const orParts = splitOutsideQuotes(expr, "||");
  if (orParts !== null) {
    return orParts.some(p => evalExpression(p.trim(), context));
  }

  // Handle && (higher precedence than ||) — split outside quotes only
  const andParts = splitOutsideQuotes(expr, "&&");
  if (andParts !== null) {
    return andParts.every(p => evalExpression(p.trim(), context));
  }

  return evalComparison(expr);
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

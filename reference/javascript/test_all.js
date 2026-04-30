/**
 * AISOP V1.0.0 — Test suite for flow_runtime utilities.
 *
 * Offline, no AI needed.
 *
 * Usage: node test_all.js
 *
 * Covers:
 *   1. Mermaid parsing (node shapes, edge types, chained edges)
 *   2. Load & validate .aisop.json files
 *   3. Metadata extraction
 *   4. Task and function listing
 *   5. Flow rendering
 *   6. Prompt building
 *   7. Validation error detection
 *   8. Multiple tasks (main + sub-tasks)
 *   9. All node types (process, decision, end, delegate, fork)
 *  10. JSON flow format
 *  11. Mixed flow format (Mermaid + JSON)
 */

const assert = require("assert");
const path = require("path");
const {
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
  VALID_SYS_CALLS,
  SYS_ERROR_TYPES,
} = require("./flow_runtime");

// ── Test fixtures ───────────────────────────────────────────

const SIMPLE_FLOW = [
  {
    role: "system",
    content: {
      protocol: "AISOP V1.0.0",
      axiom_0: "Human_Sovereignty_and_Wellbeing",
      id: "test_simple",
      name: "Simple Test",
      version: "1.0.0",
      summary: "A simple test flow",
      flow_format: "mermaid",
      tools: [],
      params: { language: "en", tone: "friendly" },
      system_prompt: "{system_prompt}",
    },
  },
  {
    role: "user",
    content: {
      instruction: "RUN aisop.main",
      user_input: "{user_input}",
      aisop: {
        main: "graph TD\n    greet[Greet] --> classify{Classify}\n    classify -->|question| search[Search]\n    classify -->|chat| reply[Reply]\n    search --> end_node((End))\n    reply --> end_node",
      },
      functions: {
        greet: { step1: "Say hello" },
        classify: { step1: "Classify intent" },
        search: { step1: "Search info" },
        reply: { step1: "Chat reply" },
        end_node: { step1: "Final output" },
      },
    },
  },
];

const MULTI_TASK_FLOW = [
  {
    role: "system",
    content: {
      protocol: "AISOP V1.0.0",
      axiom_0: "Human_Sovereignty_and_Wellbeing",
      id: "test_multi",
      name: "Multi Task Test",
      version: "1.0.0",
      flow_format: "mermaid",
      system_prompt: "{system_prompt}",
    },
  },
  {
    role: "user",
    content: {
      instruction: "RUN aisop.main",
      user_input: "{user_input}",
      aisop: {
        main: "graph TD\n    start[Start] --> delegate_step[aisop.validation]\n    delegate_step --> finish[Finish]\n    finish --> end_node((End))",
        validation:
          "graph TD\n    check[Check] --> verify[Verify]\n    verify --> done((Done))",
      },
      functions: {
        start: { step1: "Begin" },
        delegate_step: { step1: "Call validation" },
        finish: { step1: "Wrap up" },
        check: { step1: "Check input" },
        verify: { step1: "Verify result" },
      },
    },
  },
];

const PARALLEL_FLOW = [
  {
    role: "system",
    content: {
      protocol: "AISOP V1.0.0",
      axiom_0: "Human_Sovereignty_and_Wellbeing",
      id: "test_parallel",
      name: "Parallel Test",
      version: "1.0.0",
      flow_format: "mermaid",
      system_prompt: "{system_prompt}",
    },
  },
  {
    role: "user",
    content: {
      instruction: "RUN aisop.main",
      user_input: "{user_input}",
      aisop: {
        main: "graph TD\n    prepare[Prepare] --> step_a[Step A]\n    prepare --> step_b[Step B]\n    step_a --> sync[Sync]\n    step_b --> sync\n    sync --> finish[Finish]\n    finish --> end_node((End))",
      },
      functions: {
        prepare: { step1: "Prepare data" },
        step_a: { step1: "Process A" },
        step_b: { step1: "Process B" },
        sync: { step1: "Merge results", join: { merge_strategy: "array" } },
        finish: { step1: "Finalize" },
      },
    },
  },
];

const ERROR_FLOW = [
  {
    role: "system",
    content: {
      protocol: "AISOP V1.0.0",
      axiom_0: "Human_Sovereignty_and_Wellbeing",
      id: "test_error",
      name: "Error Test",
      version: "1.0.0",
      flow_format: "mermaid",
      system_prompt: "{system_prompt}",
    },
  },
  {
    role: "user",
    content: {
      instruction: "RUN aisop.main",
      user_input: "{user_input}",
      aisop: {
        main: "graph TD\n    risky[Risky] --> ok[OK]\n    risky -.-> err[Error Handler]\n    ok --> end_node((End))\n    err --> end_node",
      },
      functions: {
        risky: { step1: "Try something", on_error: { timeout: "err", default: "err" } },
        ok: { step1: "Success" },
        err: { step1: "Handle error" },
      },
    },
  },
];

const JSON_FLOW = [
  {
    role: "system",
    content: {
      protocol: "AISOP V1.0.0",
      axiom_0: "Human_Sovereignty_and_Wellbeing",
      id: "test_jsonflow",
      name: "JSON Flow Test",
      version: "1.0.0",
      flow_format: "jsonflow",
    },
  },
  {
    role: "user",
    content: {
      instruction: "RUN aisop.main",
      user_input: "{user_input}",
      aisop: {
        main: {
          greet: { next: ["classify"] },
          classify: { branches: { question: "search", chat: "reply" } },
          search: { next: ["end"] },
          reply: { next: ["end"] },
          end: {},
        },
      },
      functions: {
        greet: { step1: "Say hello" },
        classify: { step1: "Classify intent" },
        search: { step1: "Search info" },
        reply: { step1: "Chat reply" },
        end: { step1: "Final output" },
      },
    },
  },
];

const MIXED_FLOW = [
  {
    role: "system",
    content: {
      protocol: "AISOP V1.0.0",
      axiom_0: "Human_Sovereignty_and_Wellbeing",
      id: "test_mixed",
      name: "Mixed Flow Test",
      version: "1.0.0",
      flow_format: "hybrid",
    },
  },
  {
    role: "user",
    content: {
      instruction: "RUN aisop.main",
      user_input: "{user_input}",
      aisop: {
        main: "graph TD\n    start[Start] --> delegate[aisop.sub]\n    delegate --> end_node((End))",
        sub: {
          check: { next: ["done"] },
          done: {},
        },
      },
      functions: {
        start: { step1: "Begin" },
        delegate: { step1: "Call sub" },
        check: { step1: "Check" },
        done: { step1: "Done" },
      },
    },
  },
];

// ── Tests ───────────────────────────────────────────────────

function test_parse_mermaid_basic() {
  const result = parseMermaid(
    "graph TD\n    greet[Greet] --> classify{Classify}\n    classify -->|question| search[Search]\n    classify -->|chat| reply[Reply]\n    search --> end_node((End))\n    reply --> end_node"
  );
  assert(result.nodes.greet);
  assert(result.nodes.classify);
  assert.deepStrictEqual(result.nodes.classify.branches, { question: "search", chat: "reply" });
  assert.strictEqual(result.node_types.greet, "process");
  assert.strictEqual(result.node_types.classify, "decision");
  assert.strictEqual(result.node_types.end_node, "end");
  console.log("  [PASS] parseMermaid: basic shapes and edges");
}

function test_parse_mermaid_error_edge() {
  const result = parseMermaid(
    "graph TD\n    risky[Risky] --> ok[OK]\n    risky -.-> err[Error]"
  );
  assert.strictEqual(result.nodes.risky.error, "err");
  console.log("  [PASS] parseMermaid: error edge (-.->)");
}

function test_parse_mermaid_delegate() {
  const result = parseMermaid(
    "graph TD\n    start[Start] --> call[aisop.validation]\n    call --> end_node((End))"
  );
  assert.strictEqual(result.node_types.call, "delegate");
  assert.strictEqual(result.nodes.call.delegate_to, "validation");
  console.log("  [PASS] parseMermaid: delegate node (aisop.sub)");
}

function test_parse_mermaid_chained() {
  const result = parseMermaid(
    "graph TD\n    A[Step A] --> B[Step B] --> C((End))"
  );
  assert(result.nodes.A);
  assert(result.nodes.B);
  assert(result.nodes.C);
  assert.deepStrictEqual(result.nodes.A.next, ["B"]);
  assert.deepStrictEqual(result.nodes.B.next, ["C"]);
  console.log("  [PASS] parseMermaid: chained edges");
}

function test_parse_mermaid_parallel() {
  const result = parseMermaid(
    "graph TD\n    prepare[Prepare] --> step_a[Step A]\n    prepare --> step_b[Step B]"
  );
  assert.deepStrictEqual(result.nodes.prepare.next, ["step_a", "step_b"]);
  console.log("  [PASS] parseMermaid: parallel fork");
}

function test_infer_node_type() {
  assert.strictEqual(inferNodeType({}), "end");
  assert.strictEqual(inferNodeType({ branches: { a: "b" } }), "decision");
  assert.strictEqual(inferNodeType({ delegate_to: "sub" }), "delegate");
  assert.strictEqual(inferNodeType({ next: ["a", "b"] }), "fork");
  assert.strictEqual(inferNodeType({ next: ["a"] }), "process");
  console.log("  [PASS] inferNodeType: all patterns correct");
}

function test_validate_valid() {
  validate(SIMPLE_FLOW);
  validate(MULTI_TASK_FLOW);
  validate(PARALLEL_FLOW);
  validate(ERROR_FLOW);
  validate(JSON_FLOW);
  validate(MIXED_FLOW);
  console.log("  [PASS] validate: all valid flows pass");
}

function test_validate_invalid() {
  let errors = 0;

  // Wrong length
  try { validate([{ role: "system", content: {} }]); } catch (e) { errors++; }

  // Missing role
  try {
    validate([
      { role: "wrong", content: { protocol: "AISOP V1.0.0", axiom_0: "Human_Sovereignty_and_Wellbeing", id: "x", name: "x", version: "1", flow_format: "mermaid" } },
      { role: "user", content: { instruction: "RUN aisop.main", aisop: { main: "graph TD\n    A[X] --> B((Y))" }, functions: {} } },
    ]);
  } catch (e) { errors++; }

  // Missing required metadata
  try {
    validate([
      { role: "system", content: { protocol: "AISOP V1.0.0", axiom_0: "Human_Sovereignty_and_Wellbeing", flow_format: "mermaid" } },
      { role: "user", content: { instruction: "RUN aisop.main", aisop: { main: "graph TD\n    A[X] --> B((Y))" }, functions: {} } },
    ]);
  } catch (e) { errors++; }

  // Missing main task
  try {
    validate([
      { role: "system", content: { protocol: "AISOP V1.0.0", axiom_0: "Human_Sovereignty_and_Wellbeing", id: "x", name: "x", version: "1", flow_format: "mermaid" } },
      { role: "user", content: { instruction: "RUN aisop.main", aisop: { other: "graph TD\n    A[X] --> B((Y))" }, functions: {} } },
    ]);
  } catch (e) { errors++; }

  // Task is not a string or object
  try {
    validate([
      { role: "system", content: { protocol: "AISOP V1.0.0", axiom_0: "Human_Sovereignty_and_Wellbeing", id: "x", name: "x", version: "1", flow_format: "mermaid" } },
      { role: "user", content: { instruction: "RUN aisop.main", aisop: { main: 123 }, functions: {} } },
    ]);
  } catch (e) { errors++; }

  // Wrong axiom_0
  try {
    validate([
      { role: "system", content: { protocol: "AISOP V1.0.0", axiom_0: "wrong", id: "x", name: "x", version: "1", flow_format: "mermaid" } },
      { role: "user", content: { instruction: "RUN aisop.main", aisop: { main: "graph TD\n    A[X] --> B((Y))" }, functions: {} } },
    ]);
  } catch (e) { errors++; }

  // Wrong flow_format
  try {
    validate([
      { role: "system", content: { protocol: "AISOP V1.0.0", axiom_0: "Human_Sovereignty_and_Wellbeing", id: "x", name: "x", version: "1", flow_format: "invalid" } },
      { role: "user", content: { instruction: "RUN aisop.main", aisop: { main: "graph TD\n    A[X] --> B((Y))" }, functions: {} } },
    ]);
  } catch (e) { errors++; }

  assert.strictEqual(errors, 7, `Expected 7 validation errors, got ${errors}`);
  console.log("  [PASS] validate: all invalid inputs rejected");
}

function test_get_metadata() {
  const meta = getMetadata(SIMPLE_FLOW);
  assert.strictEqual(meta.id, "test_simple");
  assert.strictEqual(meta.name, "Simple Test");
  assert.strictEqual(meta.version, "1.0.0");
  assert.strictEqual(meta.axiom_0, "Human_Sovereignty_and_Wellbeing");
  assert.strictEqual(meta.flow_format, "mermaid");
  console.log("  [PASS] getMetadata: correct extraction");
}

function test_params() {
  const meta = getMetadata(SIMPLE_FLOW);
  assert(meta.params);
  assert.strictEqual(meta.params.language, "en");
  assert.strictEqual(meta.params.tone, "friendly");

  const meta2 = getMetadata(MULTI_TASK_FLOW);
  assert.strictEqual(meta2.params, undefined);
  console.log("  [PASS] params: optional field correctly handled");
}

function test_get_tasks() {
  const tasks = getTasks(MULTI_TASK_FLOW);
  assert(tasks.main);
  assert(tasks.validation);
  console.log("  [PASS] getTasks: main and sub-tasks found");
}

function test_get_functions() {
  const funcs = getFunctions(SIMPLE_FLOW);
  assert(funcs.greet);
  assert(funcs.classify);
  assert.strictEqual(Object.keys(funcs).length, 5);
  console.log("  [PASS] getFunctions: correct extraction");
}

function test_list_nodes() {
  const nodes = listNodes(SIMPLE_FLOW);
  const names = nodes.map((n) => n.name);
  const types = {};
  nodes.forEach((n) => (types[n.name] = n.type));
  assert(names.includes("greet"));
  assert(names.includes("classify"));
  assert.strictEqual(types.classify, "decision");
  assert.strictEqual(types.end_node, "end");
  assert.strictEqual(types.greet, "process");
  console.log("  [PASS] listNodes: correct node listing");
}

function test_list_nodes_subtask() {
  const nodes = listNodes(MULTI_TASK_FLOW, "validation");
  const names = nodes.map((n) => n.name);
  assert(names.includes("check"));
  assert(names.includes("verify"));
  console.log("  [PASS] listNodes: sub-task listing works");
}

function test_parallel_nodes() {
  const nodes = listNodes(PARALLEL_FLOW);
  const prepare = nodes.find((n) => n.name === "prepare");
  assert(prepare);
  assert.strictEqual(prepare.type, "fork");
  assert.deepStrictEqual(prepare.next, ["step_a", "step_b"]);
  console.log("  [PASS] listNodes: parallel fork");
}

function test_error_routing_nodes() {
  const nodes = listNodes(ERROR_FLOW);
  const risky = nodes.find((n) => n.name === "risky");
  assert(risky);
  assert.strictEqual(risky.error, "err");
  console.log("  [PASS] listNodes: error routing");
}

function test_delegate_nodes() {
  const nodes = listNodes(MULTI_TASK_FLOW);
  const delegate = nodes.find((n) => n.name === "delegate_step");
  assert(delegate);
  assert.strictEqual(delegate.type, "delegate");
  assert.strictEqual(delegate.delegate_to, "validation");
  console.log("  [PASS] listNodes: delegate node");
}

function test_render_flow() {
  const output = renderFlow(SIMPLE_FLOW);
  assert(output.includes("greet"));
  assert(output.includes("classify"));
  console.log("  [PASS] renderFlow: returns Mermaid");
}

function test_build_prompt() {
  const prompt = buildPrompt(SIMPLE_FLOW, "hello world", "You are a bot");
  const parsed = JSON.parse(prompt);
  assert.strictEqual(parsed[0].content.system_prompt, "You are a bot");
  assert.strictEqual(parsed[1].content.user_input, "hello world");
  console.log("  [PASS] buildPrompt: variable substitution works");
}

function test_load_file() {
  const filePath = path.join(__dirname, "example.aisop.json");
  const data = load(filePath);
  assert(Array.isArray(data));
  assert.strictEqual(data.length, 2);
  console.log("  [PASS] load: file loading works");
}

function test_load_example() {
  const filePath = path.join(__dirname, "example.aisop.json");
  const data = load(filePath);
  const meta = getMetadata(data);
  assert.strictEqual(meta.protocol, "AISOP V1.0.0");
  assert.strictEqual(meta.axiom_0, "Human_Sovereignty_and_Wellbeing");
  assert.strictEqual(meta.flow_format, "mermaid");
  const nodes = listNodes(data);
  assert(nodes.length > 0);
  console.log("  [PASS] load: example.aisop.json valid");
}

function test_load_example_syscalls() {
  const filePath = path.join(__dirname, "example_syscalls.aisop.json");
  const data = load(filePath);
  const meta = getMetadata(data);
  assert.strictEqual(meta.protocol, "AISOP V1.0.0");
  const tasks = getTasks(data);
  assert("main" in tasks);
  const funcs = getFunctions(data);
  assert("validate" in funcs);
  assert("deploy" in funcs);
  // Verify syscall steps are classifiable
  assert.strictEqual(classifyStep(funcs.validate.step1), "sys_call");
  console.log("  [PASS] load: example_syscalls.aisop.json valid");
}

function test_json_flow_validate() {
  validate(JSON_FLOW);
  console.log("  [PASS] json_flow: validation passes");
}

function test_json_flow_list_nodes() {
  const nodes = listNodes(JSON_FLOW);
  const names = nodes.map((n) => n.name);
  const types = {};
  nodes.forEach((n) => (types[n.name] = n.type));
  assert(names.includes("greet"));
  assert(names.includes("classify"));
  assert.strictEqual(types.classify, "decision");
  assert.strictEqual(types.end, "end");
  assert.strictEqual(types.greet, "process");
  console.log("  [PASS] json_flow: list_nodes correct");
}

function test_json_flow_render() {
  const output = renderFlow(JSON_FLOW);
  assert(output.includes("greet"));
  assert(output.includes("classify"));
  console.log("  [PASS] json_flow: render_flow correct");
}

function test_mixed_flow_validate() {
  validate(MIXED_FLOW);
  console.log("  [PASS] mixed_flow: validation passes");
}

function test_mixed_flow_list_nodes() {
  const mainNodes = listNodes(MIXED_FLOW, "main");
  const subNodes = listNodes(MIXED_FLOW, "sub");
  const mainNames = mainNodes.map((n) => n.name);
  const subNames = subNodes.map((n) => n.name);
  assert(mainNames.includes("start"));
  assert(subNames.includes("check"));
  const subTypes = {};
  subNodes.forEach((n) => (subTypes[n.name] = n.type));
  assert.strictEqual(subTypes.done, "end");
  console.log("  [PASS] mixed_flow: list_nodes both formats");
}

// ── Run ─────────────────────────────────────────────────────

console.log("AISOP V1.0.0 — Testing all utilities (JavaScript):\n");
test_parse_mermaid_basic();
test_parse_mermaid_error_edge();
test_parse_mermaid_delegate();
test_parse_mermaid_chained();
test_parse_mermaid_parallel();
test_infer_node_type();
test_validate_valid();
test_validate_invalid();
test_get_metadata();
test_params();
test_get_tasks();
test_get_functions();
test_list_nodes();
test_list_nodes_subtask();
test_parallel_nodes();
test_error_routing_nodes();
test_delegate_nodes();
test_render_flow();
test_build_prompt();
test_load_file();
test_load_example();
test_load_example_syscalls();
test_json_flow_validate();
test_json_flow_list_nodes();
test_json_flow_render();
test_mixed_flow_validate();
test_mixed_flow_list_nodes();
console.log("\nAll tests passed!");

// ── sys.* System Call Tests ─────────────────────────────────

function test_classify_step_sys_call() {
  assert.strictEqual(classifyStep("sys.io.confirm('Delete?')"), "sys_call");
  assert.strictEqual(classifyStep("sys.assert('x != null', 'fail')"), "sys_call");
  assert.strictEqual(classifyStep("sys.run('ls')"), "sys_call");
  assert.strictEqual(classifyStep("sys.code.exec('python', 'print(1)')"), "sys_call");
  console.log("  [PASS] classifyStep: sys.* detected");
}

function test_classify_step_sub_task() {
  assert.strictEqual(classifyStep("RUN aisop.extract_keywords"), "sub_task");
  assert.strictEqual(classifyStep("RUN aisop.main"), "sub_task");
  console.log("  [PASS] classifyStep: RUN aisop.* detected");
}

function test_classify_step_natural_language() {
  assert.strictEqual(classifyStep("Say hello to the user"), "natural_language");
  assert.strictEqual(classifyStep("Classify user intent"), "natural_language");
  console.log("  [PASS] classifyStep: natural language detected");
}

function test_parse_sys_call_confirm() {
  const result = parseSysCall("sys.io.confirm('Delete all data?')");
  assert(result !== null);
  assert.strictEqual(result.name, "sys.io.confirm");
  assert(result.args.includes("Delete all data?"));
  assert.strictEqual(result.store, null);
  console.log("  [PASS] parseSysCall: sys.io.confirm parsed");
}

function test_parse_sys_call_with_store() {
  const result = parseSysCall("sys.io.input('Enter path') -> target_path");
  assert(result !== null);
  assert.strictEqual(result.name, "sys.io.input");
  assert.strictEqual(result.store, "target_path");
  console.log("  [PASS] parseSysCall: -> store_var parsed");
}

function test_parse_sys_call_nested() {
  const result = parseSysCall("sys.code.exec('python', 'data.sort()')");
  assert(result !== null);
  assert.strictEqual(result.name, "sys.code.exec");
  assert(result.args.includes("python"));
  console.log("  [PASS] parseSysCall: three-level name parsed");
}

function test_parse_sys_call_invalid() {
  assert.strictEqual(parseSysCall("Say hello"), null);
  assert.strictEqual(parseSysCall("RUN aisop.main"), null);
  console.log("  [PASS] parseSysCall: non-sys returns null");
}

function test_eval_expression_comparison() {
  const ctx = { count: 5, threshold: 3 };
  assert.strictEqual(evalExpression("count > 0", ctx), true);
  assert.strictEqual(evalExpression("count == 5", ctx), true);
  assert.strictEqual(evalExpression("count < threshold", ctx), false);
  assert.strictEqual(evalExpression("threshold >= 3", ctx), true);
  console.log("  [PASS] evalExpression: comparisons work");
}

function test_eval_expression_null_check() {
  const ctx = { account_id: "abc123" };
  assert.strictEqual(evalExpression("account_id != null", ctx), true);
  const ctx2 = { account_id: null };
  assert.strictEqual(evalExpression("account_id != null", ctx2), false);
  assert.strictEqual(evalExpression("account_id == null", ctx2), true);
  console.log("  [PASS] evalExpression: null checks work");
}

function test_eval_expression_logical_and() {
  const ctx = { a: 5, b: 10, c: 3 };
  assert.strictEqual(evalExpression("a > 0 && b > 0", ctx), true);
  assert.strictEqual(evalExpression("a > 0 && b < 0", ctx), false);
  assert.strictEqual(evalExpression("a > 0 && b > 0 && c == 3", ctx), true);
  console.log("  [PASS] evalExpression: && operator works");
}

function test_eval_expression_logical_or() {
  const ctx = { status: 0, fallback: 1 };
  assert.strictEqual(evalExpression("status > 0 || fallback > 0", ctx), true);
  assert.strictEqual(evalExpression("status > 0 || fallback < 0", ctx), false);
  assert.strictEqual(evalExpression("status == 0 || fallback == 0", ctx), true);
  console.log("  [PASS] evalExpression: || operator works");
}

function test_eval_expression_logical_not() {
  const ctx = { done: false, active: true };
  assert.strictEqual(evalExpression("!done", ctx), true);
  assert.strictEqual(evalExpression("!active", ctx), false);
  console.log("  [PASS] evalExpression: ! operator works");
}

function test_eval_expression_combined_logic() {
  const ctx = { x: 5, y: 0, z: 10 };
  assert.strictEqual(evalExpression("x > 0 && y > 0 || z > 0", ctx), true);
  assert.strictEqual(evalExpression("x > 0 && y == 0 || z < 0", ctx), true);
  console.log("  [PASS] evalExpression: combined && || works");
}

function test_parse_sys_call_validation() {
  const r1 = parseSysCall("sys.io.confirm('ok?')");
  assert(r1 !== null);
  assert.strictEqual(r1.valid, true);

  const r2 = parseSysCall("sys.io.destroy('all')");
  assert(r2 !== null);
  assert.strictEqual(r2.valid, false);

  const r3 = parseSysCall("sys.run.bg('npm start') -> handle");
  assert(r3 !== null);
  assert.strictEqual(r3.valid, true);
  console.log("  [PASS] parseSysCall: valid field checks VALID_SYS_CALLS");
}

function test_eval_expression_string_with_operators() {
  const ctx = { msg: "ok || error" };
  assert.strictEqual(evalExpression("msg == 'ok || error'", ctx), true);
  assert.strictEqual(evalExpression("msg != 'ok || error'", ctx), false);
  const ctx2 = { status: "a && b" };
  assert.strictEqual(evalExpression("status == 'a && b'", ctx2), true);
  console.log("  [PASS] evalExpression: strings with || && handled correctly");
}

function test_eval_expression_string_comparison() {
  const ctx = { env: "production" };
  assert.strictEqual(evalExpression("env == 'production'", ctx), true);
  assert.strictEqual(evalExpression("env != 'staging'", ctx), true);
  assert.strictEqual(evalExpression("env == 'staging'", ctx), false);
  console.log("  [PASS] evalExpression: string comparison works");
}

function test_valid_sys_calls_count() {
  assert.strictEqual(VALID_SYS_CALLS.size, 24, `Expected 24, got ${VALID_SYS_CALLS.size}`);
  assert(VALID_SYS_CALLS.has("sys.run.bg"));
  assert(VALID_SYS_CALLS.has("sys.io.confirm"));
  assert(VALID_SYS_CALLS.has("sys.security.redact"));
  console.log("  [PASS] VALID_SYS_CALLS: contains all 24 entries");
}

console.log("\nsys.* System Call Tests:\n");
test_classify_step_sys_call();
test_classify_step_sub_task();
test_classify_step_natural_language();
test_parse_sys_call_confirm();
test_parse_sys_call_with_store();
test_parse_sys_call_nested();
test_parse_sys_call_invalid();
test_eval_expression_comparison();
test_eval_expression_null_check();
test_eval_expression_logical_and();
test_eval_expression_logical_or();
test_eval_expression_logical_not();
test_eval_expression_combined_logic();
test_parse_sys_call_validation();
test_eval_expression_string_with_operators();
test_eval_expression_string_comparison();
test_valid_sys_calls_count();
console.log("\nAll sys.* tests passed!");

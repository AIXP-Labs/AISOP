# AISOP V1.0.0 — JavaScript Reference Implementation

Zero dependencies. Node.js stdlib only.

## Files

| File | Description |
|------|-------------|
| `flow_runtime.js` | Core library — Mermaid + JSON Flow parser, loader, validator, flow analyzer, prompt builder |
| `run.js` | CLI tool — inspect and run `.aisop.json` files |
| `test_all.js` | Test suite — 44 tests covering Mermaid parsing, JSON flow, mixed flow, all node types, flow patterns, and sys.* system calls |
| `example.aisop.json` | Example flow file — greeting assistant |
| `example_syscalls.aisop.json` | Advanced example — deployment pipeline with sys.* calls |
| `package.json` | npm package metadata |

## Usage

```bash
# Inspect a flow file
node run.js example.aisop.json

# Build a prompt
node run.js example.aisop.json --prompt "hello"

# Run tests
node test_all.js
```

## API

```javascript
const { load, validate, getMetadata, getTasks, getFunctions, listNodes, renderFlow, buildPrompt, parseMermaid } = require("./flow_runtime");

const data = load("example.aisop.json");
const meta = getMetadata(data);
const nodes = listNodes(data, "main");
const prompt = buildPrompt(data, "hello world");
```

## sys.* System Call API

```javascript
const { classifyStep, parseSysCall, evalExpression } = require("./flow_runtime");

// Step classification (§5.3)
classifyStep("sys.io.confirm('ok?')");      // → "sys_call"
classifyStep("RUN aisop.sub");              // → "sub_task"
classifyStep("Analyze data");              // → "natural_language"

// Parse sys.* calls (§6.10)
const result = parseSysCall("sys.io.input('Enter path') -> target_path");
// → { name: "sys.io.input", args: "'Enter path'", store: "target_path", valid: true }

// Deterministic expression engine (§6.11)
evalExpression("count > 0 && status != null", { count: 5, status: "ok" });  // → true
```

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev

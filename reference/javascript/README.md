# AISOP V1.0.0 — JavaScript Reference Implementation

No third-party runtime dependencies; Node.js built-in modules only. These are inspection/checking utilities, not a business-flow executor.

## Files

| File | Description |
|------|-------------|
| `flow_runtime.js` | Core library — Mermaid + JSON Flow parser, loader, validator, flow analyzer, prompt builder |
| `run.js` | CLI tool — inspect definitions and build prompts; does not execute the flow |
| `test_all.js` | Test suite — 57 test functions (44 existing + 8 subgraph tests + 1 deployment-example check + 1 function-contract check + 3 expression, JSON-input and API-boundary checks, including 279 shared diagnostic, 114 expression and 54 raw-JSON cases) covering Mermaid parsing, JSON flow, mixed flow, all node types, flow patterns, and sys.* system calls |
| `example.aisop.json` | Example flow file — greeting assistant |
| `example_syscalls.aisop.json` | Advanced example — deployment pipeline with sys.* calls |
| `example_subgraphs.aisop.json` | Complete hybrid subgraph/delegation/store example, identical in both directories |
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

### Output Privacy

Inspection prints program metadata and steps, and `--prompt` prints the constructed prompt. Command arguments may remain in shell history or process listings. Use synthetic input and redact credentials, personal information and unrelated business data before sharing output. Static checks, local hashes and resolver claims do not establish trust or perform automatic redaction; `.gitignore` does not remove already-tracked secrets.

## Requirements

- The repository CI configuration covers Python 3.10-3.15 and Node.js 24 on ubuntu-24.04 and windows-2022. A configured matrix is not evidence of a successful workflow run. The library uses `Array.prototype.at`; no minimum earlier Node.js version is certified here, and `package.json` has no engines constraint.
- Running the library and tests requires no npm installation and no third-party runtime packages.
- The optional repository documentation site needs compatible MkDocs, Material theme and Pymdown Extensions tooling; these are separate from Node.js runtime requirements. A skipped site build is not a passing build.

## API

```javascript
const { load, validate, getMetadata, getTasks, getFunctions, listNodes, renderFlow, buildPrompt, parseMermaid } = require("./flow_runtime");

const data = load("example.aisop.json");
const meta = getMetadata(data);
const nodes = listNodes(data, "main");
const prompt = buildPrompt(data, "hello world");
```

## Subgraph Check API

```javascript
const {check, parseCall, listGraphs} = require("./flow_runtime");
const issues = check(data, null, true);   // Complete standalone example
const call = parseCall("RUN aisop.extract_keywords -> keywords");
const graphs = listGraphs(data);          // Ordered {name, format} items
```

parse_call / parseCall returns {target, store}, or null for a non-matching whole call. list_graphs / listGraphs expects a structurally valid definition and preserves graph member order. check defaults to component mode (standalone=False/false): absent local targets warn without a resolver; standalone mode rejects them without calling a resolver. An injected resolver(target) must return a strict boolean; false, exception or another type is an error. Local targets always win, and invalid local graphs cannot use an external fallback. Each actual static call position queries at most once; matching labels do not add calls, while repeated explicit steps remain separate.

validate keeps its original return value and exception type (Python ValueError / JS Error), and raises only for ERROR, not WARNING. parse_mermaid / parseMermaid retains nodes, node_types and node_labels, supports five documented arrows, grouped endpoints and quoted labels, and keeps standalone nodes. Delegate priority preserves return-time branches. check is read-only; it does not execute program steps.

The example's keywords result is its explicitly described ordered business list. Optional -> values remain local to the calling node; neither the reference checker nor output_mapping invents a universal subgraph return type.

### Label and Call Boundaries

Ordinary apostrophes and internal quotes are label data. Quote protection starts at the first non-W quote and requires a matching close followed only by W. Protection is not trimming: node labels retain data padding, while branch-label outer W is trimmed before removing one exact outer quote pair. Backslashes remain in labels after the single JSON decoding; do not unescape twice.

W is the fixed set in specification §4.2.2: U+0009-U+000D, U+0020, U+00A0, U+1680, U+2000-U+200A, U+2028/U+2029, U+202F, U+205F and U+3000. B (U+001C-U+001F, U+0085, U+FEFF) is not syntax whitespace. W boundary padding is accepted; fixed RUN/store/arrow separators are not widened. Graph rows split only on CRLF/LF/CR, not label U+2028/U+2029.

Clearly B-wrapped, indexed or malformed calls remain CALL_SYNTAX. Other unquoted RUN aisop. candidates at the start or after a character outside [A-Za-z0-9_] must be valid whole calls, including inside sys.-prefixed steps; no punctuation list is used. Matched unescaped boundary quotes protect literals, with backslash parity; word apostrophes do not open protection and unmatched quotes do not hide later calls. fooRUN and foo_RUN are not new candidates. This is finite linting, not a full sys parser or trust proof.

For fully parsed rectangular labels, inspect the original label region by trimming W/B, removing at most one complete outer quote pair and trimming that layer's W/B. A reserved aisop. intent that is not a valid original delegate is CALL_SYNTAX, never a repaired call. Public labels are unchanged and a["'aisop.helper'"] remains ordinary data. Incomplete lines remain PARSE_PARTIAL with necessary SHAPE errors; validate still ignores warnings. classify_step/classifyStep is only a prefix hint.

## Function and Parameter Checks

Only step[1-9][0-9]* keys and the eight existing reserved keys are allowed. Steps must be nonempty strings after fixed-W checking. Calls are analyzed in numeric step order using digit lengths and digits, without bounded numeric conversion; graph entry order and input data are unchanged. Unknown keys and invalid step values do not query the resolver or count as references; independent valid steps and UNUSED diagnostics remain.

An absent execute_mode means inline; explicit values must be exact inline/agent strings. Zero-step, configuration-only and unreferenced functions are checked too. A valid agent declaration does not prove executor support; runtimes must not silently downgrade it.

Optional params declares simple string/number/boolean/array/object/null type names, not defaults. Names are ASCII identifiers other than null/true/false; null declarations and old en/friendly/production defaults are invalid. Optional input absence differs from supplied null/false/0/empty strings. Actual input type admission, filtering, local shadowing and agent execution are executor obligations, not performed by check. Existing input channels are unchanged.

## Shared Expressions and Strict JSON Input

eval_expression / evalExpression accepts the boolean subset in specification §6.11: ASCII member paths, JSON-number and string literals, !, one comparison, && and ||. Precedence follows that order; no source parentheses, arithmetic, function calls, indexing or assignment. Parse the entire syntax and source literals before short-circuit evaluation. Unreached variables are not read.

Only boolean is valid for logical operations and the final condition. Different JSON types compare unequal; same-type non-null arrays/objects cannot be equality-compared. Ordering is numeric only. Object paths read own data, not prototype members, array length or getters. Missing values fail; an omitted/null overall context means an empty object, not missing parameter data. This is a JSON-data view, not a proxy sandbox or certification of unread host payloads.

Success returns boolean. ValueError/Error keeps a stable code attribute: AISOP_E_EXPR_SYNTAX for malformed source/escapes, AISOP_E_EXPR_UNDEFINED for missing data, AISOP_E_EXPR_TYPE for operand/read-data types or invalid read Unicode, and AISOP_E_EXPR_RANGE for non-finite/out-of-bound numbers. Errors are never replaced with false.

JSON-number literals and actually read numbers must be finite with absolute value at most 9007199254740991. Python bool is not number, and huge ints are range-checked before conversion. 1e3 and 0.1 are accepted; 1e300/1e309 and M+1 are rejected; binary64 underflow may round 1e-400 to 0. This is not exact decimal/financial arithmetic or an extra raw-number scanner.

Strings support JSON escapes and escaped single quotes in single-quoted literals. Reject source raw controls and lone surrogate halves; legal paired/non-BMP/Chinese values are preserved. Legal decoded control data is comparable. Do not normalize case or Unicode or unescape either JSON/expression layer twice.

load reads bytes as strict UTF-8, tolerates only one leading BOM and preserves internal string BOMs. Standard JSON decoding remains authoritative; decoded duplicate object keys, nonstandard constants, out-of-range/non-finite numbers and lone key/value surrogates fail with code AISOP_E_JSON_INPUT. The private iterative Unicode/number traversal applies only to the freshly parsed tree. JavaScript scans raw text only for duplicate keys, not numeric spellings.

Native IO failures retain their identity; valid JSON with invalid AISOP structure retains its SUBGRAPH rejection instead of becoming JSON_INPUT. check(data) checks visited structure only and cannot recover source duplicate keys. Invalid visited diagnostic keys return SHAPE at a safe ancestor/root, not an encoding crash. This adds no cyclic-host-object conformance rule or general host-object deep scan.

Valid JSON may still be rejected at host parser depth or resource limits. The Python reference maps a parser RecursionError to AISOP_E_JSON_INPUT; thresholds depend on the host and version, and JavaScript may accept the same input. Such rejection alone does not prove invalid JSON syntax. AISOP does not define a uniform acceptance depth.

The reference library does not execute sys.assert: mapping its false result or evaluation error to assertion_error with a reason is an executor obligation. sys.code.eval returns boolean on success or fails with the evaluator reason, not assertion_error. Load/static/IO/confirmation failures are not silently recategorized. Static tests do not prove runtime gates, input binding or side effects.

Migration: review numeric step order and confirmation/value dependencies; do not blindly rename keys or invent defaults. Replace permissive expression coercions, truthiness and missing-as-null assumptions with explicit valid boolean conditions; fix actual strings such as config_status == "valid". Escaped quotes and 1e3 now parse correctly. Review duplicate JSON keys, extensions, numeric range and encoding rather than treating a matching 1.0.0 version as compatibility proof.

## Diagnostic Codes

Each issue has severity (ERROR or WARNING), code, location and message. Locations are input-relative JSON-pointer-style paths; Mermaid line numbers start at 1 in the decoded graph string, including leading blank and declaration lines. Ordering is deterministic by UTF-8 location, code, severity. PARSE_PARTIAL is not full conformance; incomplete topology suppresses only conclusions that depend on missing information.

| Code | Meaning |
|---|---|
| `AISOP_E_SUBGRAPH_SHAPE` | Malformed required object, graph, function or edge/configuration type |
| `AISOP_E_SUBGRAPH_NAME` | Invalid ASCII graph, node or function identifier |
| `AISOP_E_SUBGRAPH_FORMAT` | Missing/invalid flow format or declaration/body mismatch |
| `AISOP_E_SUBGRAPH_FUNCTION_KEY` | Unknown non-reserved function key; not analyzed as a step |
| `AISOP_E_SUBGRAPH_STEP_VALUE` | Non-string or empty/W-only step value |
| `AISOP_E_SUBGRAPH_EXECUTE_MODE` | Invalid explicit dispatch value, including in zero-step/unreferenced functions |
| `AISOP_E_SUBGRAPH_PARAMS` | Invalid simple parameter declaration or name |
| `AISOP_E_SUBGRAPH_CALL_SYNTAX` | Malformed whole RUN, RUN node label or prefixed/invalid delegate |
| `AISOP_E_SUBGRAPH_CALL_MAIN` | Nested call to main |
| `AISOP_E_SUBGRAPH_LOCAL_EDGE` | Missing current-graph next/branch/error/wait_for/on_error target |
| `AISOP_E_SUBGRAPH_TARGET` | Missing standalone/consumer target or invalid local target |
| `AISOP_E_SUBGRAPH_CYCLE` | Local subgraph call cycle; not an ordinary control-flow loop |
| `AISOP_E_SUBGRAPH_CONFLICT` | Delegate, active join and map conflict |
| `AISOP_E_SUBGRAPH_RESOLVER` | Callback exception or non-boolean result |
| `AISOP_W_SUBGRAPH_RESOLVER` | No consumer resolver; absent component target is unverified |
| `AISOP_W_SUBGRAPH_PARSE_PARTIAL` | Unsupported Mermaid line, uncertain shared role or unexpanded indirect map call |
| `AISOP_W_SUBGRAPH_NODE_REUSE` | Shared node is not uniformly entry or uniformly terminal |
| `AISOP_W_SUBGRAPH_UNUSED` | No valid local incoming call; not a main reachability proof |

These static codes are distinct from the runtime error subgraph_not_found. SYS_ERROR_TYPES still contains only six sys errors, not every possible on_error key. The library does not execute calls, return/store results, propagate errors, present human confirmation or implement retries. It does not load external files or run map.iterator helpers; a resolver true is a consumer location claim, not trust or target-conformance proof.

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

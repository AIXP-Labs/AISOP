# Changelog

## V1.0.0 — 2026-11-16 revision

### Changes

- Accept only step[1-9][0-9]* and the eight existing function configuration keys. Analyze nonempty string steps by numeric index; reject unknown keys and invalid step values without querying their apparent calls.
- Remove the undefined category-matching layer: exact type, default, current-graph Mermaid/JSON error edge, parent caller, then unhandled outermost termination. Custom timeout/tool_error remain exact names, not wildcard categories.
- Reject invalid explicit execute_mode values in every declared function. Missing still means inline; valid agent mode does not certify executor capability or permit silent downgrade.
- Define params as optional simple type declarations, not defaults; migrate language/tone/environment examples and preserve former defaults as negative cases. Document own-key input presence, input admission and node-local scope without adding a binding engine or interpolation.
- Reject reserved-but-malformed rectangular delegate intent without changing public label data. Recognize unquoted mixed RUN candidates at ASCII identifier boundaries, including sys-prefixed text, instead of enumerating punctuation.
- Complete the shared boolean expression subset with strict types, own data-member access, defined precedence, whole-source validation and lazy value reads. Return boolean or ValueError/Error with fixed SYNTAX/UNDEFINED/TYPE/RANGE reason codes; never hide failures as false.
- Define actual sys.assert false/evaluator-error mapping to assertion_error with the reason retained, while sys.code.eval fails with its evaluator reason. Reference utilities do not execute those system calls or runtime human gates.
- Make load strict about UTF-8, one-only leading BOM, decoded duplicate keys, nonstandard constants, finite parsed numbers within abs(value) <= 9007199254740991 and lone Unicode surrogates. Keep legal paired/non-BMP/Chinese text and internal string BOMs. Standard JSON decoding, not a second numeric grammar scanner, owns file syntax.
- Preserve native IO and AISOP structural error identities; input rejection uses AISOP_E_JSON_INPUT. Limit the private iterative Unicode/number walk to newly parsed JSON trees, not arbitrary caller objects. Invalid visited diagnostic keys fail safely with SHAPE.
- Partially supersede ADR-004's category-matching statement by an appended note, preserving its history.
- Preserve the original 25 expression assertions and all 180 original shared diagnostic inputs with two prescribed diagnostic migrations. The diagnostic set now contains 279 cases, with two additional join counterfactuals; add 114 shared expression cases and 54 shared raw-JSON/byte cases. Current total: 57 test functions per language (44 existing + 8 subgraph tests + 1 deployment-example check + 1 function-contract check + 3 expression, JSON-input and API-boundary checks).
- Protocol and reference package versions remain 1.0.0; content and validation behavior have changed.

### Migration

- Audit unknown function keys and non-string/empty steps. Move genuine instructions to reviewed stepN positions, not by blind renaming or deleting confirmation. Review existing stepN member orders against numeric order and value/call dependencies; static checking does not prove unchanged business order.
- Use exact inline/agent values or omit execute_mode. Do not trim/coerce an invalid value or use on_error to downgrade a static error. Check runtime capability separately.
- Replace default-value-style params with type-name strings; preserve any intended defaults through explicit reviewed business behavior, not by silently filling production or other values. Missing optional inputs are not supplied null.
- Correct whitespace-padded reserved delegate labels and split mixed prose/RUN into separate steps. Ordinary quoted literal mentions and nested quote data remain data; a passing prefix classifier is not whole-call validation.
- Replace intended standard timeouts with command_timeout or confirm_timeout. An exact custom timeout key does not handle either automatically; review error paths rather than globally replacing timeout data.
- Use explicit boolean conditions, declared operand types and present own-key values; missing is an error, not null. Same-type non-null containers are not comparable for equality, and string ordering is unsupported. Split unsupported expression syntax rather than evaluating it as host code.
- Review JSON duplicate keys, NaN/Infinity extensions, unsafe ranges, malformed UTF-8, double BOMs and lone surrogates. These previously permissive or inconsistent inputs are rejected; 1e3 and correctly escaped string quotes are parsing fixes, not new coercions.
- Do not rewrite confirmation or business dependencies automatically; version 1.0.0 alone does not prove revised behavior support.

### Known Limitations

- The libraries check and evaluate utilities, not business-flow execution, actual assertion routing, confirmation, retries, input binding or agent dispatch. Their passing checks are not runtime proof or independent trust evidence.
- Already parsed objects cannot prove their original duplicate keys or numeric spelling. Unread context payloads and arbitrary cyclic/proxy objects are not certified by these utilities. Decimal exactness, new expression operators and CLI exit-status work remain out of scope.
- Valid JSON may still be rejected at host parser depth or resource limits. The Python reference maps a parser RecursionError to AISOP_E_JSON_INPUT; thresholds depend on the host and version, and JavaScript may accept the same input. Such rejection alone does not prove invalid JSON syntax. AISOP does not define a uniform acceptance depth.
- Earlier dated revisions record historical states, not current test totals or active expression-engine limitations. No known limitation waives a required failing check.

## V1.0.0 — 2026-11-15 revision

### Changes

- Distinguish approval choices from independent rejection and timeout outcomes. Route confirmation and false-assertion errors through the existing error chain without granting approval to a refusal path.
- Run a join/map node's own steps after its configured phase completes; analyze their potential calls without weakening mode-conflict errors. Join completion, merge_strategy and timeout definitions remain unchanged.
- Preserve confirmation-step and decision facts while allowing sensitive prompt/option payload minimization; clarify that this does not require approver identity. Correct the deployment example's shared cancellation audit message.

- Clarify peer subgraphs in §4.4: functional identifiers, three call forms, optional node-local results, preparation/return order, actual-arrival call counts, local routing, local call cycles and shared-node/unused warnings.
- Define runtime subgraph_not_found and the existing exact/category/default/Mermaid-or-JSON error chain, with unhandled child errors returning to the caller. Preserve human confirmation; the reference libraries do not execute this behavior.
- Keep flow_format required with no implicit hybrid default; delegate priority preserves return-time branches. Mixed prose/RUN steps are non-conformant.
- Add list_graphs/listGraphs, parse_call/parseCall and read-only check APIs with strict consumer resolver handling, deterministic diagnostics and finite Mermaid parsing. Protect identifier-keyed JavaScript dictionaries without banning legal names.
- Add byte-identical complete hybrid subgraph examples, 8 test functions per language with 63 independent diagnostic cases, ADR-003 for one-step-one-mode and ADR-004 for subgraph calls; align current documentation and AIXP project tables.
- Fix ordinary apostrophes dropping Mermaid lines; distinguish quote protection from output unquoting, preserve label data, unify fixed W/B boundaries, and reject explicit mixed calls and malformed rectangular aisop. labels.
- Preserve the original 63 diagnostic cases and extend to 180 (117 additions), using 53 test functions per language; add concrete label/topology and validate-boundary assertions.
- Separate zero-runtime-dependency claims from Python build and optional documentation requirements; require setuptools>=77 for SPDX license metadata without changing runtime dependencies or versions.
- Strengthen local ignore rules while retaining public environment templates; document synthetic inputs, prompt-output privacy and minimal private vulnerability reports.
- Qualify unmeasured performance claims, clarify non-exclusive ecosystem roles and reference-library limits, synchronize bilingual guidance and ADR mirrors, and correct ADR topic paths. These documentation/configuration changes do not alter protocol rules or program execution.
- Protocol, Python package and npm package versions remain 1.0.0; content and validation behavior have changed.

### Migration

- Review steps previously skipped beside join/map: they can now execute and produce side effects after that phase. Per-attempt execution does not guarantee exactly-once effects across retries. Version 1.0.0 alone does not establish support for these revised semantics.
- Treat options as approval choices, not rejection tokens; always provide independent rejection. Handling rejection/timeout does not authorize the protected operation; fresh approval must cover that same operation and relevant parameters.
- The existing parser also treats unquoted labels that use internal quotes to shield closing delimiters (for example, `a[He said "x]y"]`) and nested round-node delimiters (`a((p)(p))`) as partial parses. An otherwise empty supported graph can additionally fail its shape check; this is not uniformly CALL_SYNTAX.

- Keep main as the top-level entry and give peer graphs functional ASCII identifiers; do not add sub_mermaids/sub_jsonflows containers.
- Use bare delegate_to targets and whole RUN steps, optionally with -> variable. Split mixed prose/calls; old indexed calls and RUN node labels are rejected.
- Preserve preparation steps and explicit call positions; a matching label does not add another call. Do not merge repeated explicit steps or reuse confirmations. Older §5.3 described delegate steps as replaced; preparation now runs before the call or at the explicit call position. Review previously skipped steps and their side effects.
- Declare flow_format explicitly. Inspect warnings through check; use standalone mode for complete independent programs. Resolve external components through an explicitly supplied consumer callback, not an invented local success fallback.
- validate()/load() are stricter about identifiers, local targets, call syntax, local call cycles, conflicting modes and format mismatches; some previously accepted files are rejected. W boundary padding remains valid, but host-specific B whitespace is no longer trimmed. Invalid quote suffixes are not full parses; warnings still do not raise by default.

### Known Limitations

- The reference libraries load, check, analyze and build prompts; they do not execute business flows, return/store results, error propagation, retries or confirmation gates. These runtime semantics were not exercised by this static revision.
- Unsupported Mermaid lines and uncertain/indirect call analysis produce PARSE_PARTIAL. That is not full conformance; the local cycle check is not cross-file acyclicity or reachability proof.
- The category-matching statement in the earlier Changes is superseded by the 2026-11-16 revision above; it does not define a current matching layer. Shared expression-engine and strict JSON changes are included in that revision; CLI exit-status work remains separate. Known issues do not waive a failing required gate.

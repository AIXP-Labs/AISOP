/**
 * AISOP V1.0.0 — Load and inspect .aisop.json files.
 *
 * Usage:
 *     node run.js                              # default: example.aisop.json
 *     node run.js my_flow.aisop.json           # custom flow
 *     node run.js my_flow.aisop.json --prompt "hello"  # build prompt
 *     node run.js --test                       # run test suite
 */

const path = require("path");
const { load, getMetadata, getTasks, getFunctions, listNodes, renderFlow, buildPrompt } = require("./flow_runtime");

function inspectFlow(filePath) {
  const data = load(filePath);
  const meta = getMetadata(data);

  console.log("=".repeat(50));
  console.log(`  ${meta.name} v${meta.version}`);
  console.log(`  Protocol: ${meta.protocol}`);
  console.log(`  ID: ${meta.id}`);
  if (meta.summary) console.log(`  Summary: ${meta.summary}`);
  console.log("=".repeat(50) + "\n");

  const tasks = getTasks(data);
  for (const taskName of Object.keys(tasks)) {
    console.log(`Task: ${taskName}`);
    console.log(renderFlow(data, taskName));
    console.log();
  }

  const funcs = getFunctions(data);
  console.log(`Functions (${Object.keys(funcs).length}):`);
  for (const [name, body] of Object.entries(funcs)) {
    const steps = Object.entries(body).map(([k, v]) => `${k}: ${v}`).join(", ");
    console.log(`  ${name}: ${steps}`);
  }
}

function showPrompt(filePath, userInput) {
  const data = load(filePath);
  console.log(buildPrompt(data, userInput));
}

// ── Entry point ──────────────────────────────────────────────

const args = process.argv.slice(2);

if (args.includes("--test")) {
  const { execFileSync } = require("child_process");
  execFileSync(process.execPath, [path.join(__dirname, "test_all.js")], { stdio: "inherit" });
} else if (args.includes("--prompt")) {
  const idx = args.indexOf("--prompt");
  const flowPath = idx > 0 ? args[0] : path.join(__dirname, "example.aisop.json");
  const userInput = idx + 1 < args.length ? args[idx + 1] : "hello";
  showPrompt(flowPath, userInput);
} else {
  const flowPath = args[0] || path.join(__dirname, "example.aisop.json");
  inspectFlow(flowPath);
}

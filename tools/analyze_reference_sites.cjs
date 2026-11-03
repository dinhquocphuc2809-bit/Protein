// Static AST inspection only: never execute the reference extension.
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const acorn = require("../.private/multisite-research/node_modules/acorn");
const sourcePath = path.resolve(
  __dirname,
  "../../Youtube Dubbing/injectScript.js",
);
const source = fs.readFileSync(sourcePath, "utf8");
const ast = acorn.parse(source, { ecmaVersion: "latest", locations: true });
const nodes = [],
  functions = new Map(),
  variables = new Map();
function walk(node) {
  if (!node || typeof node !== "object") return;
  if (node.type) nodes.push(node);
  if (node.type === "FunctionDeclaration" && node.id)
    functions.set(node.id.name, node);
  if (
    node.type === "VariableDeclarator" &&
    node.id.type === "Identifier" &&
    node.init
  )
    variables.set(node.id.name, node.init);
  for (const [key, value] of Object.entries(node)) {
    if (key === "loc") continue;
    if (Array.isArray(value)) value.forEach(walk);
    else if (value && typeof value === "object") walk(value);
  }
}
walk(ast);
function literal(node, depth = 0, env = {}) {
  if (!node || depth > 20) return null;
  if (node.type === "Literal")
    return node.regex
      ? { pattern: node.regex.pattern, flags: node.regex.flags }
      : node.value;
  if (node.type === "Identifier" && Object.hasOwn(env, node.name))
    return env[node.name];
  if (node.type === "Identifier" && variables.has(node.name))
    return literal(variables.get(node.name), depth + 1, env);
  if (node.type === "MemberExpression" && !node.computed) {
    const obj = literal(node.object, depth + 1, env);
    if (obj && Object.hasOwn(obj, node.property.name))
      return obj[node.property.name];
  }
  if (node.type === "UnaryExpression" && node.operator === "!")
    return !literal(node.argument, depth + 1, env);
  if (node.type === "ArrayExpression")
    return node.elements.flatMap((n) =>
      n.type === "SpreadElement"
        ? literal(n.argument, depth + 1, env)
        : [literal(n, depth + 1, env)],
    );
  if (node.type === "ObjectExpression")
    return Object.fromEntries(
      node.properties
        .filter((p) => p.type === "Property")
        .map((p) => [
          p.key.name || p.key.value,
          literal(p.value, depth + 1, env),
        ]),
    );
  if (
    node.type === "CallExpression" &&
    node.callee.type === "MemberExpression" &&
    node.callee.property.name === "map" &&
    functions.has(node.arguments[0]?.name)
  ) {
    const input = literal(node.callee.object, depth + 1, env),
      fn = functions.get(node.arguments[0].name);
    const returned = fn.body.body.find((n) => n.type === "ReturnStatement");
    if (Array.isArray(input) && returned)
      return input.map((value) =>
        literal(returned.argument, depth + 1, {
          ...env,
          [fn.params[0].name]: value,
        }),
      );
  }
  if (
    node.type === "CallExpression" &&
    node.callee.type === "Identifier" &&
    functions.has(node.callee.name)
  ) {
    const returned = functions
      .get(node.callee.name)
      .body.body.find((n) => n.type === "ReturnStatement");
    if (returned) return literal(returned.argument, depth + 1, env);
  }
  return { $dynamic: source.slice(node.start, node.end).slice(0, 180) };
}
const catalog = nodes.find(
  (n) =>
    n.type === "CallExpression" &&
    n.arguments[1]?.value === "rules" &&
    n.arguments[2]?.type === "ArrayExpression",
);
if (!catalog) throw new Error("Reference rule catalog not found");
const expanded = literal(catalog.arguments[2]);
const unresolved = expanded.filter((n) => !n?.domain);
const rules = expanded.filter(
  (n) => n?.className === "SiteDubbingRules" && typeof n.domain === "string",
);
const seen = new Set(),
  unique = rules.filter((r) => {
    const key = r.domain + "|" + r.site + "|" + JSON.stringify(r.dubbingPages);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
const inventory = {
  source: "Youtube Dubbing 4.3.19 / injectScript.js",
  sha256: crypto.createHash("sha256").update(source).digest("hex"),
  rules: unique,
};
fs.writeFileSync(
  path.resolve(
    __dirname,
    "../.private/multisite-research/reference-rules.json",
  ),
  JSON.stringify(inventory, null, 2),
);
const methods = {};
for (const rule of unique)
  (methods[rule.subtitleFetchMethod] ??= []).push(rule.site);
console.log(
  JSON.stringify({ count: unique.length, unresolved, methods }, null, 2),
);
// Only factual routing/schema data is exported; never copy executable handlers.
const minimal = unique.map((r) => {
  const row = {
    site: r.site,
    domain: r.domain,
    pages: r.dubbingPages.filter((p) => typeof p === "string"),
    selector: typeof r.mediaSelector === "string" ? r.mediaSelector : "video",
    family: r.subtitleFetchMethod,
  };
  const config = r.apiInterceptConfig,
    schema = config?.parseConfig?.subtitleExtract;
  if (
    config &&
    schema &&
    typeof schema.subtitleListJsonPath === "string" &&
    r.site !== "youtube"
  )
    row.api = {
      url: config.url,
      match: config.urlMatchType,
      exclude: config.urlExclude,
      path: schema.subtitleListJsonPath,
      urlField: schema.subtitleUrlName,
      language: schema.subtitleLanguageName,
      label: schema.subtitleLabelName,
    };
  return row;
});
const publicInventory = {
  source: inventory.source,
  sha256: inventory.sha256,
  rules: minimal,
};
fs.writeFileSync(
  path.resolve(__dirname, "../research/multisite-inventory.json"),
  JSON.stringify(publicInventory, null, 2) + "\n",
);
fs.writeFileSync(
  path.resolve(__dirname, "../extension/lib/sites.js"),
  "// Factual site routes, generated by tools/analyze_reference_sites.cjs.\n// Registry membership is not a live-site support certification.\n(function(root){const rules=" +
    JSON.stringify(minimal) +
    ';root.VeloaSites=rules;if(typeof module!=="undefined")module.exports=rules;})(globalThis);\n',
);
const coverage = minimal.map((r) => {
  let implementation =
    "Shared native tracks/HLS only; bespoke API not implemented";
  if (r.family === "youtube")
    implementation = "Dedicated YouTube player/timedtext/transcript";
  else if (r.api)
    implementation = "Configured metadata schema + shared subtitle readers";
  else if (r.family === "kinescope")
    implementation = "Captured playlist player + VTT tracks";
  else if (["wistia", "kajabi", "pendo"].includes(r.family))
    implementation = "Wistia player identity + inline captions";
  else if (r.family.includes("jwplayer"))
    implementation = "JWPlayer owned playlist tracks + HLS sources";
  else if (
    ["domTrack", "commonVtt", "commonM3u8", "mux", "videojs"].includes(r.family)
  )
    implementation = "Shared DOM/open-shadow/SDK/HLS reader";
  const live =
    r.site === "apple_developer"
      ? "360 cues acquired on one live sample"
      : r.site === "ahrefs_wistia"
        ? "Live page uses YouTube embed; captions unknown"
        : "Not individually live verified";
  return `| ${r.site} | ${r.domain} | ${r.family} | ${implementation} | ${live} |`;
});
fs.writeFileSync(
  path.resolve(__dirname, "../docs/MULTISITE_COVERAGE.md"),
  "# Multisite routing and coverage\n\nGenerated from the statically inspected local reference. The 159 rows include repeated\nbrands and embedded players. Shared readers work only when the page exposes a supported\ncaption representation. Registry membership does not mean a bespoke API was ported or\nthat the live site passed testing. See MULTISITE_ANALYSIS.md for evidence and limits.\nFull lesson patterns and selectors: research/multisite-inventory.json.\n\n| Site | Domain pattern | Reference method | Veloa implementation | Live evidence |\n| --- | --- | --- | --- | --- |\n" +
    coverage.join("\n") +
    "\n",
);

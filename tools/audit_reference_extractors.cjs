// Static reference inspection only. Private excerpts are never executed or redistributed.
const fs = require("node:fs"),
  path = require("node:path"),
  crypto = require("node:crypto");
const acorn = require("../.private/multisite-research/node_modules/acorn");
const base = path.resolve(__dirname, "..");
const source = fs.readFileSync(
  path.resolve(base, "../Youtube Dubbing/injectScript.js"),
  "utf8",
);
const tree = acorn.parse(source, { ecmaVersion: "latest" });
const classes = new Map(),
  mappings = new Map(),
  aliases = new Map(),
  declarations = new Map();
function walk(node, visit) {
  if (!node || typeof node !== "object") return;
  if (node.type) visit(node);
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) for (const item of value) walk(item, visit);
    else if (value && typeof value === "object") walk(value, visit);
  }
}
walk(tree, (node) => {
  if (node.type === "FunctionDeclaration" && node.id)
    declarations.set(node.id.name, node);
  if (
    node.type === "VariableDeclarator" &&
    node.id.type === "Identifier" &&
    node.init
  )
    declarations.set(node.id.name, node);
  if (node.type === "ClassDeclaration" && node.id)
    classes.set(node.id.name, node);
  if (
    node.type === "VariableDeclarator" &&
    node.init?.type === "ClassExpression"
  )
    classes.set(node.id.name, node.init);
  if (
    node.type === "AssignmentExpression" &&
    node.left?.type === "Identifier" &&
    node.right?.type === "ClassExpression"
  )
    classes.set(node.left.name, node.right);
  if (node.type === "VariableDeclarator" && node.init?.type === "Identifier")
    aliases.set(node.id.name, node.init.name);
  if (
    node.type === "CallExpression" &&
    node.callee.property?.name === "with" &&
    node.arguments[0]?.type === "Literal" &&
    node.arguments[1]?.body?.type === "NewExpression"
  )
    mappings.set(node.arguments[0].value, node.arguments[1].body.callee.name);
});
for (let pass = 0; pass < 5; pass++)
  for (const [name, target] of aliases)
    if (classes.has(target)) classes.set(name, classes.get(target));
const rules = JSON.parse(
  fs.readFileSync(
    path.join(base, ".private/multisite-research/reference-rules.json"),
  ),
).rules;
const directory = path.join(base, ".private/multisite-research/extractors");
fs.mkdirSync(directory, { recursive: true });
const audit = [];
for (const family of [...new Set(rules.map((r) => r.subtitleFetchMethod))]) {
  const name = mappings.get(family),
    node = classes.get(name),
    chain = [];
  let current = node;
  while (current && !chain.includes(current)) {
    chain.push(current);
    current = classes.get(current.superClass?.name);
  }
  const strings = [],
    methods = [];
  if (node) {
    for (const member of node.body.body)
      methods.push(member.key?.name || member.key?.value);
    walk(node, (n) => {
      if (n.type === "Literal" && typeof n.value === "string")
        strings.push(n.value);
    });
    fs.writeFileSync(
      path.join(directory, family + ".js"),
      chain
        .map(
          (n, i) =>
            (n.type === "ClassExpression" ? `const Extractor${i} = ` : "") +
            source.slice(n.start, n.end) +
            ";",
        )
        .join("\n\n"),
    );
    const helpers = new Map();
    function collect(n, depth) {
      if (depth > 2) return;
      walk(n, (x) => {
        if (
          x.type !== "Identifier" ||
          helpers.has(x.name) ||
          classes.has(x.name)
        )
          return;
        const d = declarations.get(x.name);
        if (
          !d ||
          d.end - d.start > 16000 ||
          (d.start >= node.start && d.end <= node.end)
        )
          return;
        helpers.set(x.name, d);
        collect(d, depth + 1);
      });
    }
    collect(node, 0);
    const helperSource = [...helpers.values()]
      .map(
        (n) =>
          (n.type === "VariableDeclarator" ? "const " : "") +
          source.slice(n.start, n.end) +
          ";",
      )
      .join("\n\n");
    fs.writeFileSync(
      path.join(directory, family + ".helpers.js"),
      helperSource,
    );
  }
  audit.push({
    family,
    className: name || null,
    parent: node?.superClass?.name || null,
    bytes: node ? node.end - node.start : 0,
    sites: rules
      .filter((r) => r.subtitleFetchMethod === family)
      .map((r) => r.site),
    methods,
    hints: [...new Set(strings)].filter(
      (s) =>
        s.length < 350 &&
        /https?:|subtitle|caption|\.vtt|\.srt|\.m3u8|\/api|__NEXT|playerConfig/i.test(
          s,
        ),
    ),
  });
}
fs.writeFileSync(
  path.join(base, "research/extractor-audit.json"),
  JSON.stringify(
    {
      sourceSha256: crypto.createHash("sha256").update(source).digest("hex"),
      reviewLedger: "docs/FULL_SITE_PARITY.md",
      families: audit,
    },
    null,
    2,
  ) + "\n",
);
console.log(
  JSON.stringify(
    audit.map(({ family, className, parent, bytes, sites }) => ({
      family,
      className,
      parent,
      bytes,
      routes: sites.length,
    })),
    null,
    2,
  ),
);

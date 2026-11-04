// Static inspection: parse the supplied extension, never execute its runtime.
const fs = require("node:fs"),
  path = require("node:path"),
  crypto = require("node:crypto");
const acorn = require("../.private/multisite-research/node_modules/acorn");
const root = path.resolve(__dirname, "..");
const source = fs.readFileSync(
  path.resolve(root, "../Youtube Dubbing/content-scripts/content.js"),
  "utf8",
);
const tree = acorn.parse(source, { ecmaVersion: "latest" });
const families = {
  twitter: [
    "getSubtitleContentFromBackground",
    "tryBuildMetadataFromNativeTextTrack",
  ],
  facebook: ["getFacebookMapping", "loadPreferredFacebookCaption"],
  domestika: ["resolveMetadataForMedia", "domestikaMetadataService"],
  mindvalley: ["resolveMetadataForMedia", "mindvalleyMetadataService"],
};
const found = new Map();
function walk(node) {
  if (!node || typeof node !== "object") return;
  if (["ClassDeclaration", "ClassExpression"].includes(node.type)) {
    const text = source.slice(node.start, node.end);
    for (const [family, markers] of Object.entries(families)) {
      if (!markers.every((marker) => text.includes(marker))) continue;
      const methods = node.body.body
        .map((member) => member.key?.name || member.key?.value)
        .filter(Boolean);
      found.set(family, {
        family,
        className: node.id?.name || null,
        methods,
        sourceStart: node.start,
        sourceEnd: node.end,
        mechanism:
          family === "twitter"
            ? "Current tweet/media ID -> background observed HLS map; complete native TextTrack fallback; unified cards"
            : family === "facebook"
              ? "Selected video React metadata/FBID -> observed GraphQL mapping -> caption locales/sideLoadCaptionsUrl"
              : family === "mindvalley"
                ? "Owned HLS sources or MP4+VTT source siblings; per-player activation"
                : "Per-lesson control selection -> background manifest associated with current video-item ID",
      });
      const output = path.join(root, ".private/multisite-research/runtime");
      fs.mkdirSync(output, { recursive: true });
      fs.writeFileSync(path.join(output, family + ".js"), text);
    }
  }
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach(walk);
    else if (value && typeof value === "object") walk(value);
  }
}
walk(tree);
if (found.size !== Object.keys(families).length)
  throw Error("Runtime handler changed; manual review required");
const report = {
  source: "Youtube Dubbing/content-scripts/content.js",
  sha256: crypto.createHash("sha256").update(source).digest("hex"),
  scope:
    "Companion content-runtime audit. Absence from injectScript factory does not mean absence of caption support.",
  families: [...found.values()],
};
fs.writeFileSync(
  path.join(root, "research/runtime-extractor-audit.json"),
  JSON.stringify(report, null, 2) + "\n",
);
console.log(
  JSON.stringify({ families: [...found.keys()], sourceSha256: report.sha256 }),
);

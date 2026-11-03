(function (root) {
  "use strict";
  const enc = new TextEncoder();
  const hex = (value) =>
    Array.from(new Uint8Array(value), (n) =>
      n.toString(16).padStart(2, "0"),
    ).join("");
  const random = (bytes = 16) =>
    hex(crypto.getRandomValues(new Uint8Array(bytes)));
  const sha256 = async (value) =>
    hex(
      await crypto.subtle.digest(
        "SHA-256",
        typeof value === "string" ? enc.encode(value) : value,
      ),
    );
  async function signedHeaders(session, method, path, body = "") {
    const timestamp = String(
      Math.floor((Date.now() + (session.clockOffset || 0)) / 1000),
    );
    const nonce = random();
    const key = await crypto.subtle.importKey(
      "raw",
      Uint8Array.from(session.request_key.match(/../g), (c) => parseInt(c, 16)),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"],
    );
    const signature = hex(
      await crypto.subtle.sign(
        "HMAC",
        key,
        enc.encode(
          [method, path, await sha256(body), timestamp, nonce].join("\n"),
        ),
      ),
    );
    return {
      Authorization: `Bearer ${session.token}`,
      "X-Auvirel-Time": timestamp,
      "X-Auvirel-Nonce": nonce,
      "X-Auvirel-Signature": signature,
      "Content-Type": "application/json",
    };
  }
  function endpoint(value, modal = false) {
    const url = new URL(value);
    if (
      url.protocol !== "https:" ||
      url.username ||
      url.password ||
      url.port ||
      url.search ||
      url.hash ||
      url.pathname !== "/"
    )
      throw new Error("Use an HTTPS origin without path or credentials.");
    if (modal && !url.hostname.endsWith(".modal.run"))
      throw new Error("Voice endpoint must use modal.run.");
    return url.origin;
  }
  function parseModal(command) {
    if (
      typeof command !== "string" ||
      command.length > 4096 ||
      !/^\s*modal\s+token\s+set\s/.test(command)
    )
      throw new Error("Expected modal token set command.");
    const id = command.match(/--token-id(?:=|\s+)(ak-[A-Za-z0-9_-]+)/);
    const secret = command.match(/--token-secret(?:=|\s+)(as-[A-Za-z0-9_-]+)/);
    if (!id || !secret) throw new Error("Modal token ID or secret is missing.");
    return { token_id: id[1], token_secret: secret[1] };
  }
  function cues(items) {
    if (!Array.isArray(items) || !items.length || items.length > 20000)
      throw new Error("No usable subtitles found.");
    let previous = -1;
    return items.map((item, id) => {
      const start = Number(item.start),
        end = Number(item.end);
      const text = String(item.text || "")
        .replace(/<[^>]*>/g, "")
        .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, "")
        .trim();
      if (
        !Number.isFinite(start) ||
        !Number.isFinite(end) ||
        start < previous ||
        start < 0 ||
        end <= start ||
        end - start > 120 ||
        end > 14400 ||
        !text ||
        text.length > 4000
      )
        throw new Error(`Invalid subtitle timing or text at cue ${id + 1}.`);
      previous = start;
      return {
        id,
        start,
        end,
        text,
        ...(item.translated ? { translated: String(item.translated) } : {}),
      };
    });
  }
  function parseSrt(text) {
    if (enc.encode(text).length > 2 * 1024 ** 2)
      throw new Error("SRT exceeds 2 MiB.");
    return cues(
      text
        .replace(/^\uFEFF/, "")
        .replace(/\r\n?/g, "\n")
        .trim()
        .split(/\n\s*\n/)
        .map((block) => {
          const lines = block.trim().split("\n");
          if (/^\d+$/.test(lines[0])) lines.shift();
          const m = lines
            .shift()
            ?.match(
              /^(\d{1,3}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{1,3}):(\d{2}):(\d{2})[,.](\d{3})(?:\s+.*)?$/,
            );
          if (!m || lines.length === 0 || [2, 3, 6, 7].some((i) => +m[i] >= 60))
            throw new Error("Invalid UTF-8 SRT.");
          const stamp = (i) =>
            +m[i] * 3600 + +m[i + 1] * 60 + +m[i + 2] + +m[i + 3] / 1000;
          return { start: stamp(1), end: stamp(5), text: lines.join(" ") };
        }),
    );
  }
  function atTime(items, time) {
    let lo = 0,
      hi = items.length;
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      if (items[mid].start <= time) lo = mid + 1;
      else hi = mid;
    }
    return lo - 1;
  }
  const stamp = (seconds) => {
    const value = Math.max(0, Math.floor(seconds));
    return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
  };
  const api = {
    hex,
    random,
    sha256,
    signedHeaders,
    endpoint,
    parseModal,
    cues,
    parseSrt,
    atTime,
    stamp,
  };
  root.Auvirel = Object.assign(root.Auvirel || {}, api);
  if (typeof module !== "undefined") module.exports = api;
})(globalThis);

(function (root) {
  "use strict";
  function glob(pattern, value) {
    return (
      typeof pattern === "string" &&
      new RegExp(
        "^" +
          pattern
            .split("*")
            .map((s) => s.replace(/[.+?^${}()|[\]\\]/g, "\\$&"))
            .join(".*") +
          "$",
      ).test(value)
    );
  }
  function matches(pattern, value) {
    try {
      const url = new URL(value),
        parts = pattern.match(/^(\*|https?):\/\/([^/]+)(\/.*)$/);
      if (
        !parts ||
        !["http:", "https:"].includes(url.protocol) ||
        url.username ||
        url.password
      )
        return false;
      const host = parts[2];
      const hosts = host.startsWith("*.") ? [host, host.slice(2)] : [host];
      return (
        (parts[1] === "*" || url.protocol === parts[1] + ":") &&
        hosts.some((h) => glob(h, url.hostname)) &&
        glob(parts[3], url.pathname + url.search + url.hash)
      );
    } catch {
      return false;
    }
  }
  let cachedUrl, cachedRegistry, cachedRules;
  function rules(url) {
    if (cachedUrl !== url || cachedRegistry !== root.VeloaSites) {
      cachedUrl = url;
      cachedRegistry = root.VeloaSites;
      cachedRules = (root.VeloaSites || []).filter(
        (r) =>
          r.site !== "common" &&
          matches(r.domain, url) &&
          r.pages.some((p) => matches(p, url)),
      );
    }
    return cachedRules;
  }
  function query(selector, scope = document) {
    const found = [],
      stack = [scope];
    let count = 0;
    while (stack.length && count++ < 256) {
      const current = stack.shift();
      found.push(...current.querySelectorAll(selector));
      for (const node of current.querySelectorAll("*"))
        if (node.shadowRoot) stack.push(node.shadowRoot);
    }
    return [...new Set(found)];
  }
  function videos(scope = document) {
    const selectors = rules(location.href)
      .map((r) => r.selector)
      .filter((s) => s !== "video" && s !== "video, audio");
    const preferred = (v) => {
      let node = v;
      while (node) {
        if (
          selectors.some((s) => {
            try {
              return node.matches?.(s);
            } catch {
              return false;
            }
          })
        )
          return 1;
        node = node.parentElement || node.getRootNode()?.host;
      }
      return 0;
    };
    return query("video", scope)
      .filter((v) => {
        const rect = v.getBoundingClientRect();
        return rect.width > 100 && rect.height > 60;
      })
      .sort((a, b) => {
        const priority = preferred(b) - preferred(a);
        if (priority) return priority;
        const x = a.getBoundingClientRect(),
          y = b.getBoundingClientRect();
        return y.width * y.height - x.width * x.height;
      });
  }
  function source(video) {
    // Stable lesson IDs survive a player's initial URL -> MediaSource blob swap.
    const stable =
      video?.getAttribute("data-video-id") || video?.getAttribute("data-id");
    if (stable) return "media-id:" + stable;
    return (
      video?.currentSrc ||
      video?.src ||
      video?.querySelector("source")?.src ||
      ""
    );
  }
  function youtubeId(value) {
    try {
      const url = new URL(value);
      if (!/(^|\.)(youtube\.com|youtube-nocookie\.com)$/.test(url.hostname))
        return null;
      const id =
        url.searchParams.get("v") ||
        url.pathname.match(/^\/(?:embed|shorts|live)\/([\w-]+)/)?.[1];
      return /^[\w-]{11}$/.test(id || "") ? id : null;
    } catch {
      return null;
    }
  }
  function language(value) {
    const parts = String(value || "")
      .replace(/_/g, "-")
      .split("-");
    if (!/^[a-z]{2,3}$/i.test(parts[0]) || parts[0] === "und") return "auto";
    const region = parts.slice(1).find((p) => /^[A-Z]{2}$/i.test(p));
    return parts[0].toLowerCase() + (region ? "-" + region.toUpperCase() : "");
  }
  const api = {
    glob,
    matches,
    rules,
    query,
    videos,
    source,
    youtubeId,
    language,
  };
  root.VeloaMedia = api;
  if (typeof module !== "undefined") module.exports = api;
})(globalThis);

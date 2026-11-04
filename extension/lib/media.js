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
  function siteUrl(value) {
    let url;
    try {
      url = new URL(value);
    } catch {
      return String(value || "");
    }
    if (/(^|\.)bilibili\.com$/.test(url.hostname))
      url.pathname = url.pathname.replace(
        /^\/[a-z]{2}(?:-[a-z]{2,4})?\/(?=(?:video|bangumi|cheese|list|medialist|festival)\/)/i,
        "/",
      );
    return url.href;
  }
  function rules(url) {
    if (cachedUrl !== url || cachedRegistry !== root.VeloaSites) {
      cachedUrl = url;
      cachedRegistry = root.VeloaSites;
      const matchedUrl = siteUrl(url);
      cachedRules = (root.VeloaSites || []).filter(
        (r) =>
          r.site !== "common" &&
          matches(r.domain, matchedUrl) &&
          r.pages.some((p) => matches(p, matchedUrl)),
      );
    }
    return cachedRules;
  }
  function query(selector, scope = document) {
    const found = [],
      stack = scope.shadowRoot ? [scope, scope.shadowRoot] : [scope];
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
    const ted = rules(location.href).some((r) => r.family === "ted");
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
        if (ted && v.closest("#ad-container")) return false;
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
    if (!video) return "";
    const bili = biliRoute(location.href);
    if (bili) return "bili:" + bili.key;
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
  function biliRoute(value) {
    try {
      const url = new URL(siteUrl(value));
      if (!/(^|\.)bilibili\.com$/.test(url.hostname)) return null;
      const path = url.pathname.match(/^\/video\/(BV[\w]+|av\d+)/i);
      const bvid = path?.[1]?.startsWith("BV")
        ? path[1]
        : url.searchParams.get("bvid");
      const aid =
        path?.[1]?.match(/^av(\d+)$/i)?.[1] || url.searchParams.get("aid");
      const episode = url.pathname.match(
        /^\/(?:bangumi|cheese)\/play\/ep(\d+)/,
      )?.[1];
      const page = Number(
        url.searchParams.get("p") || url.searchParams.get("page") || 1,
      );
      if (!Number.isSafeInteger(page) || page < 1 || page > 10000) return null;
      if (
        !/^BV\w{3,}$/.test(bvid || "") &&
        !/^[1-9]\d*$/.test(aid || "") &&
        !episode
      )
        return null;
      const cid = url.searchParams.get("cid");
      return {
        bvid: /^BV\w{3,}$/.test(bvid || "") ? bvid : null,
        aid: /^[1-9]\d*$/.test(aid || "") ? aid : null,
        episode,
        page,
        cid: /^[1-9]\d*$/.test(cid || "") ? cid : null,
        key: `${episode ? "ep" + episode : bvid || "av" + aid}:${page}:${cid || ""}`,
      };
    } catch {
      return null;
    }
  }
  function controls(video) {
    if (!video) return null;
    const selectors = rules(location.href)
      .map((r) => r.controls)
      .filter(Boolean);
    selectors.push(
      "media-control-bar",
      ".vjs-control-bar",
      ".jw-button-container",
      ".shaka-controls-button-panel",
    );
    if (youtubeId(location.href))
      selectors.unshift("#movie_player .ytp-right-controls");
    // Walk outward from the selected video, never attach to another player's controls.
    let scope = video.parentElement || video.getRootNode();
    while (scope && scope !== document) {
      for (const selector of selectors) {
        try {
          const matches = [...scope.querySelectorAll(selector)];
          if (
            matches.length === 1 &&
            query("video", matches[0]).length === 0 &&
            query("video", scope).filter(
              (v) =>
                !rules(location.href).some((r) => r.family === "ted") ||
                !v.closest("#ad-container"),
            ).length === 1
          )
            return matches[0];
        } catch {
          /* A changed site selector leaves the floating launcher available. */
        }
      }
      scope = scope.parentElement || scope.host || null;
    }
    return null;
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
    biliRoute,
    controls,
    youtubeId,
    language,
  };
  root.VeloaMedia = api;
  if (typeof module !== "undefined") module.exports = api;
})(globalThis);

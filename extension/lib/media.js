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
    // CoinDesk now links individual clips under /video/; the catalog uses /videos/.
    if (/(^|\.)coindesk\.com$/.test(url.hostname))
      url.pathname = url.pathname.replace(/^\/video\//, "/videos/");
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
      // International Bilibili is a separate player/API, absent from the reference registry.
      if (biliInternationalRoute(url))
        cachedRules.push({
          site: "biliintl",
          family: "biliintl",
          selector: "video",
          controls:
            ".player-mobile-control-bar-right, .squirtle-controller-right",
        });
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
  function auxiliary(video) {
    const families = rules(location.href).map((r) => r.family);
    return (
      (families.includes("ted") && !!video.closest("#ad-container")) ||
      (families.includes("loom") &&
        (String(video.className).includes("animatedPreviewVideo") ||
          /cdn\.loom\.com\/sessions\/thumbnails\//.test(
            video.currentSrc || video.src,
          )))
    );
  }
  const watchedPlayers = new WeakSet(),
    activatedPlayers = new WeakMap();
  let activationSequence = 0;
  function videos(scope = document) {
    const douyin = rules(location.href).some((r) => r.site === "douyin");
    const lessonPlayers = rules(location.href).some((r) =>
      ["domestika", "mindvalley"].includes(r.family),
    );
    const aljazeera = rules(location.href).some(
      (r) => r.family === "aljazeera_brightcove",
    );
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
        if (auxiliary(v)) return false;
        if (douyin) {
          const feed = v.closest(
            '[data-e2e="feed-video"], [data-e2e="feed-active-video"]',
          );
          if (feed && feed.getAttribute("data-e2e") !== "feed-active-video")
            return false;
          const style = getComputedStyle(v);
          if (
            style.visibility === "hidden" ||
            style.display === "none" ||
            style.opacity === "0"
          )
            return false;
        }
        if (lessonPlayers && !watchedPlayers.has(v)) {
          watchedPlayers.add(v);
          v.addEventListener("play", () =>
            activatedPlayers.set(v, ++activationSequence),
          );
          if (!v.paused && !v.ended)
            activatedPlayers.set(v, ++activationSequence);
        }
        const carousel =
          aljazeera && v.closest(".vertical-video-player-container");
        if (carousel && !carousel.classList.contains("vve-is-active"))
          return false;
        const rect = v.getBoundingClientRect();
        return rect.width > 100 && rect.height > 60;
      })
      .sort((a, b) => {
        if (douyin) {
          const active =
            Number(!!b.closest('[data-e2e="feed-active-video"]')) -
            Number(!!a.closest('[data-e2e="feed-active-video"]'));
          if (active) return active;
        }
        const priority = preferred(b) - preferred(a);
        if (priority) return priority;
        const x = a.getBoundingClientRect(),
          y = b.getBoundingClientRect();
        if (lessonPlayers) {
          const playing =
            Number(!b.paused && !b.ended) - Number(!a.paused && !a.ended);
          if (playing) return playing;
          // Buffering/prepare pauses must not switch the session to a neighboring lesson.
          const active =
            (activatedPlayers.get(b) || 0) - (activatedPlayers.get(a) || 0);
          if (active) return active;
          const visible = (rect) =>
            Math.max(
              0,
              Math.min(rect.right, innerWidth) - Math.max(rect.left, 0),
            ) *
            Math.max(
              0,
              Math.min(rect.bottom, innerHeight) - Math.max(rect.top, 0),
            );
          const area = visible(y) - visible(x);
          if (area) return area;
        }
        return y.width * y.height - x.width * x.height;
      });
  }
  function source(video) {
    if (!video) return "";
    const intl = biliInternationalRoute(location.href, root.document);
    if (intl?.id) return `biliintl:${intl.kind}:${intl.id}`;
    const aweme = douyinId(location.href, video);
    if (aweme) return "douyin:" + aweme;
    if (rules(location.href).some((r) => r.family === "twitter")) {
      try {
        const poster = new URL(video.poster);
        const id =
          poster.hostname === "pbs.twimg.com" &&
          poster.pathname.match(
            /^\/(?:ext_tw_video_thumb|amplify_video_thumb)\/(\d+)\//,
          )?.[1];
        if (id) return "twitter-media:" + id;
      } catch {}
    }
    const bili = biliRoute(location.href);
    if (bili) return "bili:" + bili.key;
    const brightcove =
      rules(location.href).some((r) => r.family.endsWith("_brightcove")) &&
      video
        ?.closest("video-js[data-video-id], .video-js[data-video-id]")
        ?.getAttribute("data-video-id");
    if (brightcove) return "brightcove:" + brightcove;
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
  function biliInternationalRoute(value, doc) {
    try {
      const url = new URL(value);
      if (
        url.protocol !== "https:" ||
        url.username ||
        url.password ||
        !/(^|\.)bilibili\.tv$/.test(url.hostname)
      )
        return null;
      const path = url.pathname.match(
        /^\/(?:[a-z]{2}(?:-[a-z]{2})?\/)?(video|play)\/(\d{1,24})(?:\/(\d{1,24}))?\/?$/i,
      );
      if (!path) return null;
      if (path[1] === "video" && path[3]) return null;
      if (path[1] === "video") return { kind: "aid", id: path[2] };
      let episode = path[3];
      // The season landing URL does not include the currently selected episode.
      if (!episode && doc) {
        const selected = [...doc.querySelectorAll("a.ep-item--active[href]")];
        if (selected.length === 1) {
          const current = new URL(selected[0].getAttribute("href"), url);
          const match = current.pathname.match(/\/play\/(\d+)\/(\d+)\/?$/);
          if (current.origin === url.origin && match?.[1] === path[2])
            episode = match[2];
        }
      }
      return { kind: "episode_id", id: episode || null, season: path[2] };
    } catch {
      return null;
    }
  }
  function douyinId(value, video) {
    try {
      const url = new URL(value);
      if (
        url.protocol !== "https:" ||
        url.username ||
        url.password ||
        !/(^|\.)douyin\.com$/.test(url.hostname)
      )
        return null;
      const route =
        url.searchParams.get("modal_id") ||
        url.pathname.match(/^\/(?:video|note|lvdetail)\/(\d+)\/?$/)?.[1];
      const owner = video?.closest("[data-aweme-id], [data-e2e-vid]");
      const dom =
        owner?.getAttribute("data-aweme-id") ||
        owner?.getAttribute("data-e2e-vid");
      const valid = (x) => /^\d{10,24}$/.test(x || "");
      if (valid(route) && valid(dom) && route !== dom) return null;
      return valid(dom) ? dom : valid(route) ? route : null;
    } catch {
      return null;
    }
  }
  function controls(video) {
    if (!video) return null;
    const selectors = rules(location.href)
      .map((r) =>
        r.family === "loom"
          ? '.transportSection div:has(> div[data-hide-if-fullscreen] > div[role="presentation"] > button[data-name="FullScreenBtn"])'
          : r.controls,
      )
      .filter(Boolean);
    selectors.push(
      "media-control-bar",
      ".vjs-control-bar",
      ".jw-button-container",
      ".shaka-controls-button-panel",
    );
    if (youtubeId(location.href))
      selectors.unshift("#movie_player .ytp-right-controls");
    if (rules(location.href).some((r) => r.site === "douyin"))
      selectors.unshift(
        "xg-right-grid.xg-right-grid",
        ".douyin-player-controls-right",
      );
    // Walk outward from the selected video, never attach to another player's controls.
    let scope = video.parentElement || video.getRootNode();
    while (scope && scope !== document) {
      for (const selector of selectors) {
        try {
          const matches = [...scope.querySelectorAll(selector)];
          if (
            matches.length === 1 &&
            !matches[0].matches("video, audio, iframe, object, embed") &&
            query("video", matches[0]).length === 0 &&
            query("video", scope).filter((v) => !auxiliary(v)).length === 1
          )
            return matches[0];
        } catch {
          /* A changed site selector leaves the floating launcher available. */
        }
      }
      scope =
        scope.parentElement ||
        scope.host ||
        scope.getRootNode?.()?.host ||
        null;
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
    biliInternationalRoute,
    douyinId,
    controls,
    youtubeId,
    language,
  };
  root.VeloaMedia = api;
  if (typeof module !== "undefined") module.exports = api;
})(globalThis);

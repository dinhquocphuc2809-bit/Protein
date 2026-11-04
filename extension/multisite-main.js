(() => {
  "use strict";
  if (globalThis.__veloaSiteCaptions) return;
  const M = globalThis.VeloaMedia,
    F = globalThis.VeloaSubtitleFormats;
  if (
    !M ||
    !F ||
    /(^|\.)(youtube\.com|youtube-nocookie\.com)$/.test(location.hostname)
  )
    return;
  const nativeFetch = window.fetch,
    resources = new Map(),
    metadata = new Map();
  const ids = new WeakMap(),
    players = new Set();
  let nextId = 0,
    href = location.href,
    media = null,
    mediaSource = "",
    revision = 0,
    capturing = 0,
    busy = false;
  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  function identity() {
    const selected = M.videos()[0] || null,
      src = M.source(selected);
    if (
      location.href !== href ||
      (media && selected !== media) ||
      (mediaSource && src !== mediaSource)
    ) {
      resources.clear();
      metadata.clear();
      revision++;
    }
    href = location.href;
    media = selected;
    mediaSource = src;
    if (selected && !ids.has(selected)) ids.set(selected, ++nextId);
    return { href, revision, node: ids.get(selected) || 0, src };
  }
  function same(a, b, early = false) {
    return (
      a.href === b.href &&
      a.revision === b.revision &&
      ((early && !a.node) || (a.node === b.node && (!a.src || a.src === b.src)))
    );
  }
  function path(data, value) {
    if (!/^\$(?:\.[A-Za-z_][\w]*)*$/.test(value)) return undefined;
    return value
      .slice(2)
      .split(".")
      .reduce(
        (obj, key) => (obj && Object.hasOwn(obj, key) ? obj[key] : undefined),
        data,
      );
  }
  function classify(value) {
    let url;
    try {
      url = new URL(value, location.href);
    } catch {
      return null;
    }
    if (url.protocol !== "https:") return null;
    if (VocalmReaders.observedKind(url.href, location.href))
      return { kind: "reader" };
    if (
      M.rules(location.href).some((r) => r.site === "bili") &&
      url.hostname === "api.bilibili.com" &&
      /^\/x\/player\/(?:wbi\/)?v2$/.test(url.pathname)
    )
      return {
        kind: "metadata",
        bili: true,
        api: {
          path: "$.data.subtitle.subtitles",
          urlField: "subtitle_url",
          language: "lan",
          label: "lan_doc",
        },
      };
    for (const rule of M.rules(location.href)) {
      const api = rule.api;
      if (
        rule.site === "bili" ||
        !api ||
        (api.exclude && M.matches(api.exclude, url.href))
      )
        continue;
      if (
        api.match === "pattern"
          ? M.matches(api.url, url.href)
          : url.pathname.concat(url.search).includes(api.url)
      )
        return { kind: "metadata", api };
    }
    if (/\.(vtt|webvtt|srt|ttml|dfxp)(?:$|\/)/i.test(url.pathname))
      return { kind: "caption" };
    if (/\.m3u8$/i.test(url.pathname)) return { kind: "hls" };
    if (/\.mpd$/i.test(url.pathname)) return { kind: "dash" };
    if (
      /(^|\.)wistia\.(com|net)$/.test(url.hostname) &&
      /^\/embed\/captions\/[\w-]+\.json$/.test(url.pathname)
    )
      return { kind: "wistia" };
    if (
      /(^|\.)hdslb\.com$/.test(url.hostname) &&
      /\/bfs\/subtitle\//.test(url.pathname)
    )
      return { kind: "caption" };
    return null;
  }
  function prune() {
    let size = 0;
    for (const [key, row] of [...resources].reverse()) {
      size += row.text.length * 2;
      if (size > 8 * 1024 ** 2) resources.delete(key);
    }
    while (resources.size > 24) resources.delete(resources.keys().next().value);
    while (metadata.size > 16) metadata.delete(metadata.keys().next().value);
  }
  function tracks(data, api, base) {
    const list = path(data, api.path);
    if (!Array.isArray(list) || list.length > 100)
      throw new Error("Caption metadata not ready");
    return list
      .filter((t) => !t.kind || ["captions", "subtitles"].includes(t.kind))
      .map((t) => ({
        url: F.safeUrl(t[api.urlField], base),
        language: M.language(t[api.language]),
        label: String(t[api.label] || ""),
        default: Boolean(t.default),
      }));
  }
  function remember(url, text, type, token) {
    if (!same(token, identity(), true) || text.length > F.MAX_BYTES) return;
    try {
      if (type.kind === "metadata") {
        const data = JSON.parse(text);
        if (!globalThis.VocalmPlatforms?.metadataMatches(url, data)) return;
        if (type.bili && data.code !== undefined && data.code !== 0) return;
        metadata.set(url, {
          tracks: type.bili
            ? VocalmBilibili.tracks(data.data?.subtitle?.subtitles, url)
            : tracks(data, type.api, url),
          owner: type.bili ? VocalmBilibili.owner(data, url) : null,
          token,
          at: Date.now(),
        });
      } else {
        // Video playlists are not subtitle bodies. Keep only masters with subtitle renditions.
        if (type.kind === "hls" && !text.includes("TYPE=SUBTITLES")) return;
        resources.delete(url);
        resources.set(url, {
          url,
          text,
          kind: type.kind,
          token,
          at: Date.now(),
        });
      }
      prune();
    } catch {
      /* A failed metadata response never proves caption absence. */
    }
  }
  window.fetch = async function (...args) {
    const value =
      typeof args[0] === "string" || args[0] instanceof URL
        ? String(args[0])
        : args[0]?.url;
    const type = classify(value),
      token = type ? identity() : null;
    const response = await Reflect.apply(nativeFetch, this, args);
    if (type && response.ok && capturing < 3) {
      capturing++;
      F.bounded(response.clone())
        .then((text) => remember(response.url || value, text, type, token))
        .catch(() => {})
        .finally(() => capturing--);
    }
    return response;
  };
  const open = XMLHttpRequest.prototype.open,
    send = XMLHttpRequest.prototype.send,
    pending = new WeakMap();
  XMLHttpRequest.prototype.open = function (method, url, ...args) {
    const type = classify(String(url));
    pending.set(this, {
      url: String(url),
      type,
      token: type ? identity() : null,
    });
    return Reflect.apply(open, this, [method, url, ...args]);
  };
  XMLHttpRequest.prototype.send = function (...args) {
    const request = pending.get(this);
    if (request?.type)
      this.addEventListener(
        "load",
        () => {
          if (this.status < 200 || this.status >= 300) return;
          try {
            const value =
              this.responseType === "json"
                ? JSON.stringify(this.response)
                : !this.responseType || this.responseType === "text"
                  ? this.responseText
                  : "";
            if (value)
              remember(
                this.responseURL || request.url,
                value,
                request.type,
                request.token,
              );
          } catch {}
        },
        { once: true },
      );
    return Reflect.apply(send, this, args);
  };
  if (M.rules(location.href).some((r) => r.family === "kinescope")) {
    const capture = (p) => {
      if (p && typeof p.getPlaylistItem === "function" && players.size < 8)
        players.add(p);
    };
    const handlers = window.KinescopePlayerCreatedHandlers;
    if (Array.isArray(handlers)) handlers.push(capture);
    else window.KinescopePlayerCreatedHandlers = [capture];
    const previous = window.onKinescopePlayerCreated;
    window.onKinescopePlayerCreated = function (player, ...args) {
      try {
        return previous?.call(this, player, ...args);
      } finally {
        capture(player);
      }
    };
  }
  async function load(
    url,
    token,
    budget,
    session = false,
    policyKey = null,
    rpc = null,
  ) {
    if (!same(token, identity()))
      throw new Error("Video changed while reading subtitles");
    const cached = resources.get(url);
    if (!policyKey && !rpc && cached && same(cached.token, token, true))
      return cached.text;
    if (++budget.requests > 1204 || Date.now() > budget.deadline)
      throw new Error("Subtitle acquisition deadline exceeded");
    const address = VocalmReaders.captionUrl(
      F.safeUrl(url, location.href),
      location.href,
    );
    const headers = VocalmReaders.playbackHeaders(address, policyKey);
    const request = VocalmReaders.motionRequest(address, rpc, location.href);
    const sameOrigin = new URL(address).origin === location.origin;
    let response;
    try {
      response = await nativeFetch(address, {
        credentials: sameOrigin || session ? "include" : "omit",
        headers,
        ...request,
        signal: AbortSignal.timeout(
          Math.min(8000, Math.max(1, budget.deadline - Date.now())),
        ),
      });
      if (!sameOrigin && !session && [401, 403].includes(response.status))
        throw new Error("Subtitle requires browser session");
    } catch (reason) {
      if (request || sameOrigin || session || Date.now() > budget.deadline)
        throw reason;
      response = await nativeFetch(address, {
        credentials: "include",
        headers,
        signal: AbortSignal.timeout(5000),
      });
    }
    const text = await F.bounded(response);
    budget.bytes += text.length * 2;
    if (budget.bytes > 24 * 1024 ** 2)
      throw new Error("Subtitle acquisition memory limit exceeded");
    if (!same(token, identity()))
      throw new Error("Video changed while reading subtitles");
    return text;
  }
  function trackCandidates(video) {
    return [
      ...video.querySelectorAll(
        'track[kind="subtitles"],track[kind="captions"],track:not([kind])',
      ),
    ]
      .filter((t) => t.src)
      .map((t) => ({
        url: t.src,
        language: t.srclang || "auto",
        default: t.default || t.track?.mode === "showing",
      }));
  }
  async function nativeTracks(video) {
    const list = [...video.textTracks].filter((t) =>
      ["subtitles", "captions"].includes(t.kind),
    );
    list.sort(
      (a, b) => Number(b.mode === "showing") - Number(a.mode === "showing"),
    );
    for (const track of list) {
      const previous = track.mode;
      try {
        track.mode = "hidden";
        for (let attempt = 0; attempt < 6 && !track.cues?.length; attempt++)
          await delay(100);
        if (track.cues?.length) {
          if (track.cues.length > 20000)
            throw new Error("Subtitle cue limit exceeded");
          const cues = F.normalize(
            [...track.cues].map((c) => ({
              start: c.startTime,
              end: c.endTime,
              text: c.text,
            })),
          );
          // Segmented players often expose only a sliding cue window. Prefer their full manifest.
          const remote = [...video.querySelectorAll("track")].some(
            (t) =>
              t.track === track && /\.(vtt|srt|ttml)(?:[?#]|$)/i.test(t.src),
          );
          if (
            remote ||
            (Number.isFinite(video.duration) &&
              cues.at(-1).end >= video.duration - 2)
          )
            return { cues, language: track.language || "auto" };
        }
      } finally {
        track.mode = previous;
      }
    }
    return null;
  }
  function sdkTracks(video) {
    const result = [
      ...VocalmPlatforms.videojsTracks(video),
      ...VocalmReaders.sourceCaptions(video, location.href),
    ];
    const append = (list) => {
      if (!Array.isArray(list)) return;
      for (const t of list.slice(0, 100))
        if (
          (!t.kind || ["captions", "subtitles"].includes(t.kind)) &&
          (t.file || t.src || t.url)
        ) {
          const candidate = VocalmPlatforms.track(
            t.file || t.src || t.url,
            t.srclang || t.srcLang || t.language || t.lang,
            location.href,
            { default: Boolean(t.default) },
          );
          if (candidate) result.push(candidate);
        }
    };
    const manifest = (value) => {
      if (typeof value === "string" && /\.(?:m3u8|mpd)(?:[?#]|$)/i.test(value))
        append([{ src: value }]);
    };
    for (const value of [
      video.currentSrc,
      video.src,
      ...[...video.querySelectorAll("source")].map((s) => s.src),
      ...VocalmReaders.mediaUrls(video),
    ])
      manifest(value);
    let parent = video.getRootNode()?.host;
    while (parent) {
      manifest(parent.src);
      parent = parent.getRootNode()?.host;
    }
    try {
      const container = video.closest(".jwplayer");
      if (container && typeof window.jwplayer === "function") {
        const player = window.jwplayer(container.id);
        if (
          typeof player.getContainer === "function" &&
          !player.getContainer()?.contains(video)
        )
          throw new Error("Different JW player");
        const item = player.getPlaylistItem();
        const captions = player.getCaptionsList?.();
        if (Array.isArray(captions)) {
          const selected = player.getCurrentCaptions?.();
          for (const [index, caption] of captions.slice(0, 100).entries()) {
            if (!caption || caption.id === "off") continue;
            const matching = (item?.tracks || []).filter(
              (t) =>
                ["captions", "subtitles"].includes(t.kind) &&
                (t.file === caption.id ||
                  (caption.label && t.label === caption.label)),
            );
            const own = matching.length === 1 ? matching[0] : {};
            const url = /^(?:https:)?\/\//.test(caption.id || "")
              ? caption.id
              : own.file;
            if (url)
              append([{ ...own, file: url, default: index === selected }]);
          }
        }
        append(item?.tracks);
        for (const source of item?.sources || []) manifest(source.file);
      }
    } catch {}
    try {
      const list = window.videojs?.getPlayers?.();
      if (list)
        for (const player of Object.values(list))
          if (player?.el?.()?.contains(video)) {
            manifest(player.currentSource?.()?.src);
            append(player.mediainfo?.text_tracks);
            append(player.options?.()?.tracks);
            const remote = player.remoteTextTrackEls?.();
            if (remote)
              append(
                Array.from(
                  { length: Math.min(remote.length, 100) },
                  (_, i) => remote[i],
                ),
              );
          }
    } catch {}
    return result;
  }
  async function special(video, token, budget) {
    const result = [],
      rules = M.rules(location.href);
    const shadowHost = video.getRootNode()?.host;
    const embed = video.closest(".wistia_embed"),
      wistiaId =
        (shadowHost?.localName === "wistia-player" &&
          shadowHost.getAttribute("media-id")?.match(/^[a-zA-Z0-9]+$/)?.[0]) ||
        embed?.className?.match(/\bwistia_async_([a-zA-Z0-9]+)/)?.[1] ||
        (/^fast\.wistia\.(net|com)$/.test(location.hostname) &&
          location.pathname.match(/^\/embed\/iframe\/([a-zA-Z0-9]+)/)?.[1]);
    if (wistiaId) {
      const data = JSON.parse(
        await load(
          `https://fast.wistia.com/embed/captions/${wistiaId}.json`,
          token,
          budget,
        ),
      );
      if (!Array.isArray(data.captions))
        throw new Error("Wistia captions are not ready");
      for (const caption of data.captions.slice(0, 100))
        if (caption.hasCaptions !== false && caption.hash?.lines?.length)
          result.push({
            cues: F.json(caption),
            language: caption.bcp47LanguageTag || caption.language || "auto",
          });
    }
    if (
      rules.some((r) => r.family === "kinescope") &&
      M.videos().length === 1
    ) {
      let item;
      if (players.size === 1)
        item = await Promise.race([
          [...players][0].getPlaylistItem(),
          delay(2000).then(() => {
            throw new Error("Kinescope metadata timeout");
          }),
        ]);
      else if (window.playerOptions?.playlist?.length === 1)
        item = window.playerOptions.playlist[0];
      for (const t of (item?.vtt || []).slice(0, 100))
        result.push({
          url: F.safeUrl(t.src || t.url, location.href),
          language: t.srcLang || t.srclang || t.language || "auto",
          default: Boolean(t.default),
        });
    }
    return result;
  }
  async function recoverMetadata(token, budget) {
    // Resource timings survive SPA navigation. Only recover schemas whose URL
    // can be tied to the currently displayed lesson, not generic API matches.
    if (
      !M.rules(location.href).some((r) =>
        ["udemy", "chartacademy"].includes(r.family),
      )
    )
      return;
    const seen = new Set();
    for (const entry of performance
      .getEntriesByType("resource")
      .slice(-500)
      .reverse()) {
      const type = classify(entry.name);
      if (
        type?.kind !== "metadata" ||
        type.bili ||
        metadata.has(entry.name) ||
        seen.has(entry.name)
      )
        continue;
      // Lecture APIs can fire before the hook is installed. Re-read only current,
      // allowlisted metadata URLs; never replay requests with writes or bodies.
      if (!VocalmPlatforms.metadataMatches(entry.name, null)) continue;
      seen.add(entry.name);
      if (seen.size > 3) break;
      try {
        remember(
          entry.name,
          await load(entry.name, token, budget),
          type,
          token,
        );
      } catch {
        /* Normal candidate failure reporting remains available. */
      }
    }
  }
  async function acquire(expected) {
    if (busy)
      return {
        state: "unknown",
        reason: "Caption acquisition already running",
      };
    busy = true;
    try {
      const token = identity(),
        video = media;
      if (
        !video ||
        expected?.href !== href ||
        expected?.src !== M.source(video)
      )
        return { state: "unknown", reason: "Video changed" };
      const budget = { requests: 0, bytes: 0, deadline: Date.now() + 45000 };
      const check = () => {
        if (!same(token, identity()))
          throw new Error("Video changed while reading subtitles");
      };
      const bili =
        M.rules(location.href).some((r) => r.site === "bili") &&
        M.videos().length === 1;
      let diagnostic = "";
      const finish = (result) => {
        if (!same(token, identity()))
          return { state: "unknown", reason: "Video changed" };
        const cues = F.normalize(result.cues);
        return {
          state: "ready",
          cues: M.rules(location.href).some((r) => r.family === "vkvideo")
            ? VocalmReaders.incrementalCues(cues)
            : cues,
          language: result.language || "auto",
          href: token.href,
          src: token.src,
        };
      };
      const platformFirst = M.rules(location.href).some((r) =>
        ["udemy", "updraft", "loom"].includes(r.family),
      );
      let native = null,
        failure = "";
      try {
        if (!platformFirst) native = await nativeTracks(video);
      } catch (e) {
        failure = e.message;
      }
      if (native) return finish(native);
      const udemy = M.rules(location.href).some((r) => r.family === "udemy");
      let candidates = [...trackCandidates(video), ...sdkTracks(video)];
      if (bili) {
        try {
          const discovered = await VocalmBilibili.discover({
            read: (url, session) => load(url, token, budget, session),
            check,
            observed: () =>
              [...metadata.values()].filter((r) => same(r.token, token, true)),
          });
          candidates.push(...discovered.tracks);
          diagnostic = discovered.diagnostic || "";
        } catch (e) {
          failure = e.message;
          diagnostic = "bili_metadata";
        }
      }
      try {
        candidates.push(...(await special(video, token, budget)));
      } catch (e) {
        failure = e.message;
      }
      const twitter = M.rules(location.href).some(
        (r) => r.family === "twitter",
      );
      const facebook = M.rules(location.href).some(
        (r) => r.family === "facebook",
      );
      if (twitter && M.videos().length > 1) {
        for (const row of resources.values()) {
          if (row.kind !== "reader" || !same(row.token, token, true)) continue;
          try {
            candidates.push(
              ...VocalmReaders.observedTracks(row, video, location.href),
            );
          } catch (e) {
            failure = e.message;
          }
        }
      }
      // API/network resources have no DOM owner. Only accept them in an unambiguous frame.
      if (M.videos().length === 1) {
        await recoverMetadata(token, budget);
        for (const row of metadata.values())
          if (
            !row.owner &&
            same(row.token, token, true) &&
            (!udemy || row.tracks.length === 1)
          )
            candidates.push(...row.tracks);
        prune();
        const rows = [...resources.values()].filter((r) =>
          same(r.token, token, true),
        );
        for (const row of rows.filter((r) => r.kind === "reader")) {
          try {
            candidates.push(
              ...VocalmReaders.observedTracks(row, video, location.href),
            );
          } catch (e) {
            failure = e.message;
          }
        }
        for (const row of rows.filter((r) => !udemy && r.kind === "wistia"))
          try {
            const data = JSON.parse(row.text);
            for (const c of data.captions || [])
              if (c.hash?.lines?.length)
                candidates.push({
                  cues: F.json(c),
                  language: c.bcp47LanguageTag || c.language || "auto",
                });
          } catch (e) {
            failure = e.message;
          }
        candidates.push(
          ...rows
            .filter(
              (r) => !udemy && !facebook && ["hls", "dash"].includes(r.kind),
            )
            .map((r) => ({ url: r.url, language: "auto" })),
        );
        // Individual WebVTT network responses may be HLS fragments. Do not use them as a complete transcript.
        if (
          !udemy &&
          !twitter &&
          !facebook &&
          !rows.some((r) => ["hls", "dash"].includes(r.kind))
        )
          candidates.push(
            ...rows
              .filter(
                (r) =>
                  r.kind === "caption" && !r.text.includes("X-TIMESTAMP-MAP"),
              )
              .map((r) => ({ url: r.url, language: "auto", observed: true })),
          );
      }
      candidates.sort((a, b) => Number(b.default) - Number(a.default));
      const tried = new Set();
      const attempt = async (candidate) => {
        if (!candidate) return null;
        if (candidate.cues) return finish(candidate);
        if (tried.has(candidate.url)) return null;
        tried.add(candidate.url);
        if (
          /\.m3u8(?:[?#]|$)/i.test(candidate.url) &&
          !VocalmReaders.manifestAllowed(candidate.url, video, location.href)
        )
          throw new Error("Manifest does not belong to the active lesson");
        const value = await load(candidate.url, token, budget);
        if (/<(?:\w+:)?MPD\b/.test(value)) {
          for (const track of F.mpd(value, candidate.url)) {
            try {
              const result = await attempt(track);
              if (result) return result;
            } catch (e) {
              failure = e.message;
            }
          }
          throw new Error("No supported complete DASH subtitle track");
        }
        const result = value.trimStart().startsWith("#EXTM3U")
          ? await F.hls(
              value,
              candidate.url,
              (url) => load(url, token, budget),
              candidate.language,
              M.rules(location.href).some(
                (r) => r.family === "medbridge_course",
              )
                ? { timing: "media", duration: video.duration }
                : {},
            )
          : {
              cues: VocalmPlatforms.parse(value, candidate.format),
              language: candidate.language,
            };
        if (
          candidate.observed &&
          (!Number.isFinite(video.duration) ||
            result.cues.at(-1).end < video.duration - 2)
        )
          throw new Error(
            "Only a partial subtitle response was observed; enable CC and retry",
          );
        if (
          candidate.ownerKey &&
          !VocalmReaders.sourceCaptions(video, location.href).some(
            (current) =>
              current.ownerKey === candidate.ownerKey &&
              current.url === candidate.url,
          )
        )
          throw new Error("Caption owner changed while loading");
        return finish(result);
      };
      const discoverPlatforms = async () => {
        if (M.videos().length !== 1) return null;
        try {
          for await (const candidate of VocalmPlatforms.discover({
            video,
            check,
            read: (url, session, policyKey, rpc) =>
              load(url, token, budget, session, policyKey, rpc),
          })) {
            check();
            try {
              const result = await attempt(candidate);
              if (result) return result;
            } catch (e) {
              failure = e.message;
            }
          }
        } catch (e) {
          failure = e.message;
        }
        return null;
      };
      // Udemy exposes dozens of translated tracks; resolve the original course
      // locale before accepting an arbitrary observed or intercepted caption.
      if (platformFirst) {
        const result = await discoverPlatforms();
        if (result) return result;
      }
      for (const candidate of candidates.slice(0, 100)) {
        try {
          const result = await attempt(candidate);
          if (result) return result;
        } catch (e) {
          failure = e.message;
        }
      }
      if (!platformFirst) {
        const result = await discoverPlatforms();
        if (result) return result;
      }
      if (bili) {
        try {
          check();
          const candidate = await VocalmBilibili.menuTrack(video, {
            check,
            resources: () =>
              [...resources.values()].filter((r) => same(r.token, token, true)),
          });
          if (candidate)
            return finish({
              cues: F.parse(await load(candidate.url, token, budget)),
              language: candidate.language,
            });
        } catch (e) {
          failure = e.message;
        }
      }
      return {
        state:
          candidates.length || video.textTracks.length ? "failed" : "unknown",
        reason: failure || "No complete subtitle track discovered",
        diagnostic,
        href: token.href,
        src: token.src,
      };
    } finally {
      busy = false;
    }
  }
  // Called only through extension scripting; this object contains no extension credentials.
  Object.defineProperty(globalThis, "__veloaSiteCaptions", {
    value: { acquire },
    configurable: false,
  });
  addEventListener("pagehide", () => {
    resources.clear();
    metadata.clear();
    players.clear();
  });
})();

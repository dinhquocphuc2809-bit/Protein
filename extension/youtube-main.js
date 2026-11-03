(() => {
  "use strict";
  if (globalThis.__veloaYoutubeCaptions || !globalThis.VeloaCaptions) return;
  const MAX_BYTES = 4 * 1024 ** 2,
    cache = new Map();
  let transcriptCache = null;
  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const currentId = () => globalThis.VeloaMedia?.youtubeId(location.href) || new URL(location.href).searchParams.get("v");
  function timedtext(value) {
    try {
      const url = new URL(value, location.href);
      return url.protocol === "https:" &&
        /(^|\.)youtube\.com$/.test(url.hostname) &&
        url.pathname === "/api/timedtext" &&
        url.searchParams.get("v") === currentId()
        ? url
        : null;
    } catch {
      return null;
    }
  }
  function isTranscript(value) {
    try {
      const url = new URL(value, location.href);
      return (
        url.origin === location.origin &&
        url.pathname === "/youtubei/v1/get_transcript"
      );
    } catch {
      return false;
    }
  }
  function rememberTranscript(id, text) {
    if (id !== currentId() || !text || text.length > MAX_BYTES) return;
    try {
      const cues = transcriptRows(JSON.parse(text));
      if (cues.length && cues.length <= 20000)
        transcriptCache = { id, cues, at: Date.now() };
    } catch {}
  }
  async function bounded(response) {
    if (
      !response.ok ||
      Number(response.headers.get("content-length")) > MAX_BYTES
    )
      return "";
    const reader = response.body.getReader(),
      chunks = [];
    let size = 0;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.length;
        if (size > MAX_BYTES) {
          await reader.cancel();
          return "";
        }
        chunks.push(value);
      }
    } finally {
      reader.releaseLock();
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.length;
    }
    return new TextDecoder().decode(bytes);
  }
  function parse(text) {
    if (!text.trim() || text.length > MAX_BYTES) return [];
    if (text.trim().startsWith("{"))
      return VeloaCaptions.json3(JSON.parse(text));
    const xml = new DOMParser().parseFromString(text, "text/xml");
    if (xml.querySelector("parsererror")) return [];
    if (!["timedtext", "transcript"].includes(xml.documentElement.nodeName))
      return [];
    return [...xml.querySelectorAll("text, p")]
      .map((node) => {
        const classic = node.nodeName === "text",
          unit = classic ? 1 : 1000;
        const start = Number(node.getAttribute(classic ? "start" : "t")) / unit;
        return {
          start,
          end: start + Number(node.getAttribute(classic ? "dur" : "d")) / unit,
          text: node.textContent.trim(),
        };
      })
      .filter((cue) => cue.text);
  }
  function remember(value, text) {
    const url = timedtext(value);
    if (!url || url.searchParams.has("tlang")) return;
    try {
      const cues = parse(text);
      if (!cues.length || cues.length > 20000) return;
      const key = [
        url.searchParams.get("v"),
        url.searchParams.get("lang"),
        url.searchParams.get("kind") || "",
      ].join(":");
      // Only retain a few bounded responses for the current page, never tokens or URLs.
      cache.set(key, { cues, at: Date.now() });
      while (cache.size > 3) cache.delete(cache.keys().next().value);
    } catch {
      /* Malformed responses cannot authorize an ASR fallback. */
    }
  }
  const nativeFetch = window.fetch;
  window.fetch = function (...args) {
    const url =
      typeof args[0] === "string" || args[0] instanceof URL
        ? String(args[0])
        : args[0]?.url;
    const promise = nativeFetch.apply(this, args);
    const id = currentId();
    if (isTranscript(url))
      promise
        .then((response) =>
          bounded(response.clone()).then((text) =>
            rememberTranscript(id, text),
          ),
        )
        .catch(() => {});
    if (timedtext(url))
      promise
        .then((response) =>
          bounded(response.clone()).then((text) => remember(url, text)),
        )
        .catch(() => {});
    return promise;
  };
  const urls = new WeakMap(),
    videos = new WeakMap(),
    open = XMLHttpRequest.prototype.open,
    send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url, ...args) {
    urls.set(this, String(url));
    videos.set(this, currentId());
    return open.call(this, method, url, ...args);
  };
  XMLHttpRequest.prototype.send = function (...args) {
    const url = urls.get(this);
    if (timedtext(url) || isTranscript(url))
      this.addEventListener(
        "load",
        () => {
          try {
            if (this.status >= 200 && this.status < 300) {
              const text =
                this.responseType === "json"
                  ? JSON.stringify(this.response)
                  : this.responseText;
              if (isTranscript(url)) rememberTranscript(videos.get(this), text);
              else remember(url, text);
            }
          } catch {}
        },
        { once: true },
      );
    return send.apply(this, args);
  };
  function responseFor(id) {
    const player = document.querySelector("#movie_player");
    let active;
    try {
      active = player?.getPlayerResponse?.();
    } catch {}
    const matches = [active, globalThis.ytInitialPlayerResponse].filter(
      (response) => response?.videoDetails?.videoId === id,
    );
    return (
      matches.find(
        (response) =>
          response.captions?.playerCaptionsTracklistRenderer?.captionTracks
            ?.length,
      ) ||
      matches[0] ||
      null
    );
  }
  function transcriptRows(data) {
    const cues = [],
      stack = [data];
    let visited = 0;
    while (stack.length && visited++ < 150000) {
      const node = stack.pop();
      if (!node || typeof node !== "object") continue;
      const segment = node.transcriptSegmentRenderer;
      if (segment)
        cues.push({
          start: Number(segment.startMs) / 1000,
          end: Number(segment.endMs) / 1000,
          text:
            segment.snippet?.simpleText ||
            segment.snippet?.runs?.map((run) => run.text || "").join("") ||
            "",
        });
      for (const value of Object.values(node))
        if (value && typeof value === "object") stack.push(value);
    }
    return cues.sort((a, b) => a.start - b.start);
  }
  async function transcript(id) {
    if (
      transcriptCache?.id === id &&
      Date.now() - transcriptCache.at < 30 * 60 * 1000
    )
      return transcriptCache.cues;
    // Reuse only this page's own transcript command/context, with its existing session.
    const roots = [
      document.querySelector("ytd-watch-flexy")?.data,
      globalThis.ytInitialData,
    ];
    let params;
    const stack = roots.filter(Boolean),
      seen = new WeakSet();
    let visited = 0;
    while (stack.length && visited++ < 50000) {
      const node = stack.pop();
      if (!node || typeof node !== "object" || seen.has(node)) continue;
      seen.add(node);
      if (node.getTranscriptEndpoint?.params) {
        params = node.getTranscriptEndpoint.params;
        break;
      }
      for (const value of Object.values(node))
        if (value && typeof value === "object") stack.push(value);
    }
    const context = globalThis.ytcfg?.get?.("INNERTUBE_CONTEXT");
    if (!params || !context || currentId() !== id) return [];
    try {
      const result = await nativeFetch(
        "/youtubei/v1/get_transcript?prettyPrint=false",
        {
          method: "POST",
          credentials: "same-origin",
          redirect: "error",
          signal: AbortSignal.timeout(7000),
          headers: {
            "Content-Type": "application/json",
            "X-Youtube-Client-Name": String(
              globalThis.ytcfg.get("INNERTUBE_CONTEXT_CLIENT_NAME") || 1,
            ),
            "X-Youtube-Client-Version": String(
              context.client?.clientVersion || "",
            ),
          },
          body: JSON.stringify({ context, params }),
        },
      );
      const text = await bounded(result);
      return text ? transcriptRows(JSON.parse(text)) : [];
    } catch {
      return [];
    }
  }
  let pending;
  async function acquire(id) {
    let response,
      stableEmpty = 0;
    for (let attempt = 0; attempt < 12; attempt++) {
      if (currentId() !== id) return { state: "changed", videoId: currentId() };
      response = responseFor(id);
      const tracks =
        response?.captions?.playerCaptionsTracklistRenderer?.captionTracks;
      if (tracks?.length) break;
      if (
        response?.playabilityStatus?.status === "OK" &&
        document.querySelector("#movie_player")?.getVideoData?.()?.video_id ===
          id
      )
        stableEmpty++;
      else stableEmpty = 0;
      if (stableEmpty >= 6)
        return { state: "absent", videoId: id, confirmed: true, trackCount: 0 };
      await delay(500);
    }
    const renderer = response?.captions?.playerCaptionsTracklistRenderer;
    const tracks = renderer?.captionTracks;
    if (!tracks?.length) return { state: "unknown", videoId: id };
    const player = document.querySelector("#movie_player");
    let previous;
    try {
      previous = player.getOption("captions", "track");
    } catch {}
    const language =
      response.videoDetails?.defaultAudioLanguage ||
      response.microformat?.playerMicroformatRenderer?.defaultAudioLanguage;
    const index =
      renderer.audioTracks?.[renderer.defaultAudioTrackIndex || 0]
        ?.defaultCaptionTrackIndex;
    const track = VeloaCaptions.selectTrack(tracks, previous, language, index);
    const key = [id, track.languageCode, track.kind || ""].join(":");
    const cached = () => {
      const row = cache.get(key);
      return row && Date.now() - row.at < 30 * 60 * 1000 ? row.cues : null;
    };
    const ready = (cues, language = track.languageCode) => ({
      state: "ready",
      videoId: id,
      language,
      trackCount: tracks.length,
      cues,
    });
    if (cached()) return ready(cached());
    if (
      transcriptCache?.id === id &&
      Date.now() - transcriptCache.at < 30 * 60 * 1000
    )
      return ready(transcriptCache.cues, "auto");
    const url = timedtext(track.baseUrl);
    if (url) {
      url.searchParams.set("fmt", "json3");
      try {
        const result = await nativeFetch(url.href, {
          credentials: "same-origin",
          redirect: "error",
          signal: AbortSignal.timeout(5000),
        });
        remember(url.href, await bounded(result));
      } catch {}
      if (cached()) return ready(cached());
    }
    const enabled =
      document
        .querySelector("#movie_player .ytp-subtitles-button")
        ?.getAttribute("aria-pressed") === "true";
    try {
      player.loadModule?.("captions");
      player.setOption?.("captions", "track", {});
      await delay(300);
      if (currentId() !== id) return { state: "changed", videoId: currentId() };
      player.setOption?.("captions", "track", {
        languageCode: track.languageCode,
        ...(track.kind ? { kind: track.kind } : {}),
      });
      for (let attempt = 0; attempt < 24; attempt++) {
        if (currentId() !== id)
          return { state: "changed", videoId: currentId() };
        if (cached()) return ready(cached());
        await delay(250);
      }
    } finally {
      if (currentId() === id) {
        try {
          player.setOption?.(
            "captions",
            "track",
            enabled ? previous || {} : {},
          );
        } catch {}
      }
    }
    const rows = await transcript(id);
    if (currentId() !== id) return { state: "changed", videoId: currentId() };
    if (rows.length) return ready(rows, "auto");
    return { state: "unavailable", videoId: id, trackCount: tracks.length };
  }
  globalThis.__veloaYoutubeCaptions = {
    acquire(id) {
      if (!/^[A-Za-z0-9_-]{11}$/.test(id || ""))
        return Promise.resolve({ state: "unknown" });
      if (!pending || pending.id !== id) {
        const task = { id };
        task.promise = acquire(id).finally(() => {
          if (pending === task) pending = null;
        });
        pending = task;
      }
      return pending.promise;
    },
  };
})();

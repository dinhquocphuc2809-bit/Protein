(function (root) {
  "use strict";
  const F = root.VeloaSubtitleFormats,
    M = root.VeloaMedia;
  const list = (v, limit = 100) => (Array.isArray(v) ? v.slice(0, limit) : []);
  function twitterMedia(video) {
    try {
      const url = new URL(video.poster || video.getAttribute("poster"));
      return url.protocol === "https:" && url.hostname === "pbs.twimg.com"
        ? url.pathname.match(
            /^\/(?:ext_tw_video_thumb|amplify_video_thumb)\/(\d+)\//,
          )?.[1]
        : null;
    } catch {
      return null;
    }
  }
  function twitterManifest(address, video) {
    try {
      const url = new URL(address);
      const id = twitterMedia(video);
      return (
        !!id &&
        url.protocol === "https:" &&
        !url.username &&
        !url.password &&
        url.hostname === "video.twimg.com" &&
        url.pathname.match(
          /^\/(?:ext_tw_video|amplify_video)\/(\d+)\//,
        )?.[1] === id &&
        /\.m3u8$/i.test(url.pathname)
      );
    } catch {
      return false;
    }
  }
  function manifestAllowed(address, video, href, doc = root.document) {
    const families = M.rules(href).map((r) => r.family);
    const url = new URL(address, href);
    if (families.includes("twitter")) return twitterManifest(address, video);
    if (families.includes("mindvalley") || families.includes("domestika")) {
      const owned = mediaUrls(video).filter((value) =>
        /\.m3u8(?:[?#]|$)/i.test(value),
      );
      return owned.some((value) => {
        try {
          const current = new URL(value, href);
          return (
            current.origin === url.origin && current.pathname === url.pathname
          );
        } catch {
          return false;
        }
      });
    }
    if (!families.includes("pluralsight")) return true;
    const token = url.pathname.match(
      /^\/video\/delivery\/api\/v1\/manifests\/([\w.-]+)\.m3u8$/i,
    )?.[1];
    if (
      url.origin !== "https://app.pluralsight.com" ||
      !token ||
      token.length > 16384
    )
      return false;
    try {
      // The payload is only an ownership hint, never an authentication decision.
      const raw = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
      const path = JSON.parse(
        atob(raw + "=".repeat((4 - (raw.length % 4)) % 4)),
      ).path;
      if (typeof path !== "string" || !/\/hls\/master\.m3u8$/i.test(path))
        return false;
      const guid =
        "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
      const asset = path.match(
        new RegExp(`(?:^|/)clips2/(${guid})/`, "i"),
      )?.[1];
      const route = new RegExp(
        `^/ilx/video-courses/${guid}/${guid}/(${guid})/?$`,
        "i",
      );
      const clip = (value) => {
        try {
          const u = new URL(value, href);
          return u.origin === new URL(href).origin
            ? u.pathname.match(route)?.[1]
            : null;
        } catch {
          return null;
        }
      };
      let active = clip(href);
      if (!active) {
        const label = (video?.getAttribute("aria-label") || "")
          .replace(/^video:\s*/i, "")
          .trim();
        const links = [
          ...(doc?.querySelectorAll('a[href*="/ilx/video-courses/"]') || []),
        ];
        const ids = new Set(
          links
            .filter((a) => {
              const name = a.getAttribute("aria-label") || "";
              return (
                (label && (name === label || name.startsWith(label + ","))) ||
                ["page", "true"].includes(a.getAttribute("aria-current"))
              );
            })
            .map((a) => clip(a.href))
            .filter(Boolean)
            .map((id) => id.toLowerCase()),
        );
        if (ids.size === 1) active = [...ids][0];
      }
      return (
        !!asset && !!active && asset.toLowerCase() === active.toLowerCase()
      );
    } catch {
      return false;
    }
  }
  function incrementalCues(cues) {
    const result = [];
    let previous;
    for (const cue of cues) {
      const text = cue.text.replace(/\s+/g, " ").trim();
      let value = text;
      if (previous && cue.start < previous.end) {
        const before = previous.text.replace(/\s+/g, " ").trim();
        if (before === text) {
          if (result.length)
            result[result.length - 1].end = Math.max(
              result[result.length - 1].end,
              cue.end,
            );
          value = "";
        } else {
          for (
            let count = Math.min(before.length, text.length);
            count >= 3;
            count--
          ) {
            if (
              before.endsWith(text.slice(0, count)) &&
              (count === text.length || /[\s.,!?;:]/.test(text[count]))
            ) {
              value = text.slice(count).trim();
              break;
            }
          }
        }
      }
      if (value) result.push({ ...cue, text: value });
      previous = cue;
    }
    return result;
  }
  function playbackHeaders(address, policyKey) {
    if (policyKey === null || policyKey === undefined) return undefined;
    const url = new URL(address);
    if (
      url.protocol !== "https:" ||
      url.hostname !== "edge.api.brightcove.com" ||
      !/^\/playback\/v1\/accounts\/\d+\/videos\/[\w%:.-]+$/.test(
        url.pathname,
      ) ||
      typeof policyKey !== "string" ||
      !/^[\w.-]{1,4096}$/.test(policyKey)
    )
      throw new Error("Invalid public Brightcove playback policy");
    return { Accept: `application/json;pk=${policyKey}` };
  }
  function motionRequest(address, rpc, href) {
    if (!rpc) return null;
    if (
      address !== "https://backend.codedamn.com/api" ||
      !M.rules(href).some((r) => r.family === "motionmagic")
    )
      throw new Error("Unapproved metadata RPC destination");
    const item = new URL(href).searchParams.get("item-id");
    let data;
    if (
      rpc.method === "get-course-item-information" &&
      item &&
      rpc.item === item &&
      /^[\w-]{1,200}$/.test(item)
    )
      data = { requestType: { type: "for-user" }, fermionCourseItemId: item };
    else if (
      rpc.method === "get-details-to-play-fermion-saas-recorded-video" &&
      /^[\w-]{1,200}$/.test(rpc.video || "") &&
      typeof rpc.token === "string" &&
      rpc.token.length > 0 &&
      rpc.token.length < 16384
    )
      data = {
        authorizationJwt: rpc.token,
        supportedDrmSystem: null,
        videoId: rpc.video,
        playbackOrigin: new URL(href).origin,
      };
    else throw new Error("Unapproved metadata RPC operation");
    return {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fermionSchoolId: "692c0f3fb450fc68827a4ede",
        authToken: null,
        fermionAuthTokenForCodedamn: null,
        data: [
          {
            context: { namespace: "fermion-user", functionName: rpc.method },
            data,
          },
        ],
      }),
    };
  }
  function captionUrl(address, href) {
    const url = new URL(address);
    if (
      M.rules(href).some((r) => r.family === "plex") &&
      url.searchParams.has("url")
    ) {
      try {
        const direct = new URL(url.searchParams.get("url"));
        if (
          direct.protocol === "https:" &&
          direct.hostname === "vod-static.plex.tv" &&
          /\.vtt$/i.test(direct.pathname) &&
          !direct.username &&
          !direct.password
        )
          return direct.href;
      } catch {
        /* Keep the original URL when the wrapper is not an approved subtitle. */
      }
    }
    return address;
  }
  function observedKind(address, href) {
    const url = new URL(address, href),
      page = new URL(href);
    if (url.protocol !== "https:") return null;
    const families = new Set(M.rules(href).map((r) => r.family));
    if (
      families.has("twitter") &&
      url.origin === page.origin &&
      /^\/i\/api\/(?:graphql\/[^/]+\/[^/]+|2\/timeline\/[^/]+\.json)$/.test(
        url.pathname,
      )
    )
      return "twitter";
    if (
      families.has("dropbox") &&
      /(^|\.)dropbox(?:usercontent)?\.com$/.test(url.hostname) &&
      /^\/p\/transcript\//.test(url.pathname)
    )
      return "dropbox";
    if (
      families.has("circle_academy") &&
      url.origin === page.origin &&
      /^\/internal_api\/(?:spaces\/[^/]+\/posts|courses\/[^/]+\/sections\/[^/]+\/lessons)(?:\/|$)/.test(
        url.pathname,
      )
    )
      return "circle_academy";
    if (
      families.has("movebox") &&
      (/(^|\.)aoneroom\.com$/.test(url.hostname) ||
        url.hostname === "movebox.run") &&
      url.pathname === "/wefeed-h5api-bff/subject/caption"
    )
      return "movebox";
    return null;
  }
  function observedTracks(row, video, href) {
    const kind = observedKind(row.url, href);
    if (!kind || row.text.length > F.MAX_BYTES) return [];
    const data = JSON.parse(row.text),
      P = root.VocalmPlatforms;
    const page = new URL(href),
      request = new URL(row.url);
    if (kind === "twitter") {
      const result = [];
      const owners = objects(data);
      // Unified cards contain an additional serialized metadata object.
      for (const owner of owners.slice()) {
        if (
          owner.key !== "unified_card" ||
          typeof owner.value?.string_value !== "string" ||
          owner.value.string_value.length > 512 * 1024
        )
          continue;
        try {
          owners.push(...objects(JSON.parse(owner.value.string_value), 500));
        } catch {}
        if (owners.length > 4500) break;
      }
      for (const owner of owners) {
        for (const variant of list(owner.video_info?.variants)) {
          if (
            variant.content_type === "application/x-mpegURL" &&
            twitterManifest(variant.url, video)
          )
            result.push({ url: variant.url, language: "auto" });
        }
      }
      return [...new Map(result.map((t) => [t.url, t])).values()].slice(0, 10);
    }
    if (kind === "dropbox") {
      if (
        !row.token?.node ||
        !Array.isArray(data.segments) ||
        data.segments.length > 20000
      )
        return [];
      return [
        {
          cues: F.normalize(
            data.segments.map((c) => ({
              start: c.startTime,
              end: c.endTime,
              text: c.text,
            })),
          ),
          language: M.language(data.transcriptLocale),
        },
      ];
    }
    if (kind === "movebox") {
      const detail = request.searchParams.get("detailPath");
      if (!detail || !/^\d+$/.test(request.searchParams.get("id") || ""))
        return [];
      const owner = new URL(
        detail.startsWith("/") ? detail : "/" + detail,
        page,
      );
      if (
        owner.origin !== page.origin ||
        owner.pathname.replace(/\/$/, "") !== page.pathname.replace(/\/$/, "")
      )
        return [];
      return list(data.data?.captions)
        .map((c) => P.track(c.url, c.lan, href))
        .filter(Boolean);
    }
    const selected = new Set(
      mediaUrls(video).map((address) => {
        try {
          const url = new URL(address, href);
          return url.origin + url.pathname;
        } catch {
          return "";
        }
      }),
    );
    const lessonId = page.pathname.match(/\/lessons\/([^/]+)/)?.[1];
    const requestId = request.pathname.match(/\/lessons\/([^/]+)/)?.[1];
    const tracks = [];
    for (const item of objects(data)) {
      const meta = item.metadata || {};
      const hls =
        item.video_variants?.hls ||
        meta.video_variants?.hls ||
        item.hls ||
        meta.hls ||
        item.hls_url ||
        meta.hls_url ||
        item.hlsUrl ||
        meta.hlsUrl ||
        item.playback_url ||
        meta.playback_url;
      let matchesMedia = false;
      try {
        const url = new URL(hls, href);
        matchesMedia = Boolean(hls) && selected.has(url.origin + url.pathname);
      } catch {}
      const matchesLesson =
        lessonId &&
        requestId === lessonId &&
        String(item.id || "") === lessonId;
      if (!matchesMedia && !matchesLesson) continue;
      const id =
        item.media_transcript_id ||
        meta.media_transcript_id ||
        item.transcript_id ||
        meta.transcript_id;
      const url = id
        ? `/media_transcripts/${encodeURIComponent(id)}.vtt`
        : item.webvtt_file_url || meta.webvtt_file_url;
      if (typeof url !== "string" || /(?:^|\/)mosaic\.vtt(?:[?#]|$)/i.test(url))
        continue;
      const candidate = P.track(
        url,
        item.language || meta.language || "auto",
        href,
      );
      if (candidate) tracks.push(candidate);
    }
    return [...new Map(tracks.map((t) => [t.url, t])).values()];
  }
  function objects(value, limit = 4000) {
    const queue = [value],
      seen = new Set(),
      result = [];
    for (let i = 0; i < queue.length && i < limit; i++) {
      const row = queue[i];
      if (!row || typeof row !== "object" || seen.has(row)) continue;
      seen.add(row);
      if (!Array.isArray(row)) result.push(row);
      for (const item of Object.values(row)) {
        if (queue.length >= limit) break;
        if (item && typeof item === "object") queue.push(item);
      }
    }
    return result;
  }
  function scriptJson(doc, selector) {
    let bytes = 0;
    return [...doc.querySelectorAll(selector)].slice(0, 32).flatMap((el) => {
      const text = el.textContent || "";
      bytes += text.length;
      if (!text || bytes > F.MAX_BYTES) return [];
      try {
        return [JSON.parse(text)];
      } catch {
        return [];
      }
    });
  }
  function mediaUrls(video) {
    const urls = [
      video.currentSrc,
      video.src,
      video.getAttribute("poster"),
      video.poster,
      ...[...(video.querySelectorAll?.("source[src]") || [])]
        .slice(0, 32)
        .map((s) => s.src),
      video.querySelector?.("source")?.src,
      video.getRootNode?.()?.host?.getAttribute("src"),
    ];
    let player = video.player || video.player_;
    const container = video.closest(".video-js, video-js");
    player ||= container?.player || container?.player_;
    try {
      urls.push(player?.currentSrc?.(), player?.currentSource?.()?.src);
    } catch {}
    return urls.filter((v) => typeof v === "string" && v.length < 32768);
  }
  function sourceCaptions(video, href) {
    if (M.rules(href).some((r) => r.family === "facebook"))
      return facebookCaptions(video, href);
    if (!M.rules(href).some((r) => r.family === "mindvalley")) return [];
    const sources = mediaUrls(video).flatMap((value) => {
      try {
        const url = new URL(value, href);
        return url.protocol === "https:" &&
          !url.username &&
          !url.password &&
          url.hostname === "assets.mindvalley.com" &&
          /^\/api\/v1\/assets\/[a-z0-9-]{8,}\.(?:mp4|vtt)$/i.test(url.pathname)
          ? [url.href]
          : [];
      } catch {
        return [];
      }
    });
    if (!sources.some((s) => new URL(s).pathname.endsWith(".mp4"))) return [];
    const captions = [
      ...new Set(sources.filter((s) => new URL(s).pathname.endsWith(".vtt"))),
    ];
    return captions.length === 1
      ? [{ url: captions[0], language: "auto" }]
      : [];
  }
  function dataObjects(value, limit = 500) {
    const queue = [value],
      seen = new Set(),
      result = [];
    for (let i = 0; i < queue.length && i < limit; i++) {
      const node = queue[i];
      if (!node || typeof node !== "object" || seen.has(node)) continue;
      seen.add(node);
      let descriptors;
      try {
        const proto = Object.getPrototypeOf(node);
        if (
          proto !== Object.prototype &&
          proto !== Array.prototype &&
          proto !== null
        )
          continue;
        descriptors = Object.getOwnPropertyDescriptors(node);
      } catch {
        continue;
      }
      const copy = Object.create(null);
      for (const [key, descriptor] of Object.entries(descriptors).slice(
        0,
        200,
      )) {
        if (!("value" in descriptor)) continue;
        copy[key] = descriptor.value;
        if (
          queue.length < limit &&
          descriptor.value &&
          typeof descriptor.value === "object"
        )
          queue.push(descriptor.value);
      }
      if (!Array.isArray(node)) result.push(copy);
    }
    return result;
  }
  function facebookCaptions(video, href) {
    const P = root.VocalmPlatforms;
    const idOf = (item) => {
      const id =
        item.videoFBID || (item.__typename === "Video" ? item.id : null);
      return typeof id === "string" && /^\d{10,20}$/.test(id) ? id : null;
    };
    let scope = video;
    for (
      let depth = 0;
      scope && depth < 8;
      depth++, scope = scope.parentElement
    ) {
      if (scope.querySelectorAll?.("video").length > 1) break;
      const records = [];
      try {
        for (const key of Object.keys(scope)
          .filter((k) => /^__react(?:Props|Fiber)\$/.test(k))
          .slice(0, 4)) {
          const descriptor = Object.getOwnPropertyDescriptor(scope, key);
          const state = descriptor?.value;
          const props = key.startsWith("__reactFiber$")
            ? Object.getOwnPropertyDescriptor(state || {}, "memoizedProps")
                ?.value
            : state;
          records.push(...dataObjects(props));
        }
      } catch {
        continue;
      }
      const owners = records.filter((item) => idOf(item));
      const ids = new Set(owners.map(idOf));
      if (ids.size > 1) return [];
      if (ids.size !== 1) continue;
      const result = [];
      const append = (address, lang) => {
        const track = P.track(address, lang, href);
        if (!track) return;
        if (
          /(^|\.)(?:fbcdn\.net|facebook\.com)$/.test(
            new URL(track.url).hostname,
          )
        )
          result.push({ ...track, ownerKey: "facebook:" + [...ids][0] });
      };
      for (const owner of owners) {
        append(
          owner.sideLoadCaptionsUrl || owner.captions_url || owner.captionsUrl,
          "auto",
        );
        // Reading descriptors avoids invoking page-defined getters in React state.
        const locales = dataObjects(
          owner.video_available_captions_locales,
          100,
        );
        for (const row of locales)
          append(
            row.captions_url || row.captionsUrl || row.caption_url,
            row.locale || row.locale_code || row.language,
          );
      }
      return [...new Map(result.map((t) => [t.url, t])).values()];
    }
    return [];
  }
  async function* discover({
    video,
    read,
    check,
    win = window,
    doc = document,
    href = location.href,
  }) {
    const P = root.VocalmPlatforms,
      page = new URL(href);
    const families = new Set(M.rules(href).map((r) => r.family));
    const json = async (address, session = false, policyKey = null) => {
      check();
      const data = JSON.parse(
        await read(F.safeUrl(address, href), session, policyKey),
      );
      check();
      return data;
    };
    if ([...families].some((family) => family.endsWith("_brightcove"))) {
      const container = video.closest("video-js, .video-js");
      const account = container?.getAttribute("data-account");
      const player = container?.getAttribute("data-player") || "default";
      const id = container?.getAttribute("data-video-id");
      if (
        /^\d+$/.test(account || "") &&
        /^[\w-]+$/.test(player) &&
        /^[\w:.-]+$/.test(id || "")
      ) {
        const config = await json(
          `https://players.brightcove.net/${account}/${player}_default/config.json`,
        );
        const policy = config.video_cloud?.policy_key;
        if (policy) {
          const address = `https://edge.api.brightcove.com/playback/v1/accounts/${account}/videos/${encodeURIComponent(id)}`;
          playbackHeaders(address, policy);
          const info = await json(address, false, policy);
          if (
            container.getAttribute("data-video-id") !== id ||
            (id.startsWith("ref:")
              ? info.reference_id !== id.slice(4)
              : String(info.id) !== id)
          )
            throw new Error("Brightcove video changed");
          for (const row of list(info.text_tracks))
            if (["captions", "subtitles"].includes(row.kind))
              yield P.track(row.src, row.srclang, href, {
                default: row.default === true,
              });
        }
      }
    }
    if (families.has("artstation")) {
      const match = page.pathname.match(
        /^\/learning\/courses\/([^/]+)\/[^/]+\/chapters\/([^/]+)(?:\/|$)/,
      );
      if (match) {
        const course = decodeURIComponent(match[1]),
          chapter = decodeURIComponent(match[2]);
        const data = await json(
          `/api/v2/learning/courses/${encodeURIComponent(course)}.json`,
          true,
        );
        if (data.hash_id && String(data.hash_id) !== course)
          throw new Error("ArtStation course changed");
        const selected = list(data.chapters, 2000).find(
          (row) => String(row.hash_id) === chapter,
        );
        for (const row of list(selected?.subtitles))
          if (
            row.format === "vtt" ||
            /\.vtt(?:[?#]|$)/i.test(row.file_url || "")
          )
            yield P.track(
              row.file_url,
              row.locale || row.language || row.lang,
              href,
            );
      }
    }
    if (families.has("platzi")) {
      for (const address of mediaUrls(video)) {
        let encoded;
        try {
          encoded = new URL(address, href).searchParams.get("subtitles");
        } catch {
          continue;
        }
        if (!encoded || encoded.length > 131072 || !/^[\w+/=-]+$/.test(encoded))
          continue;
        try {
          const normalized = encoded.replace(/-/g, "+").replace(/_/g, "/");
          const rows = JSON.parse(
            win.atob(
              normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "="),
            ),
          );
          for (const row of list(rows))
            yield P.track(row.uri, row.language, href);
        } catch {
          /* A malformed media descriptor does not invalidate SDK tracks. */
        }
      }
    }
    if (families.has("pandavideo")) {
      const id = page.searchParams.get("v");
      const library = (page.searchParams.get("l") || page.hostname).match(
        /(?:^|[^a-z0-9])(vz-[a-z0-9]{8}-[a-z0-9]{3})(?:[^a-z0-9]|$)/i,
      )?.[1];
      if (
        /^[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12}$/i.test(id || "") &&
        library &&
        win.pandaLoad?.configVideoLoaded === true &&
        win.pandaLoad?.playerLoaded === true
      ) {
        for (const row of list(win.player_configs?.subtitles)) {
          if (!/^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/i.test(row.srclang || ""))
            continue;
          const lang =
            row.srclang.toLowerCase() === "pt" ? "pt-BR" : row.srclang;
          yield P.track(
            `https://subtitles.tv.pandavideo.com.br/${library.toLowerCase()}/${id}/${lang}.vtt`,
            lang,
            href,
          );
        }
      }
    }
    if (families.has("tella")) {
      let story;
      for (const address of mediaUrls(video)) {
        const url = new URL(address, href);
        if (url.origin === page.origin)
          story ||= url.pathname.match(
            /^\/api\/stories\/([\w-]+)(?:\/|$)/,
          )?.[1];
      }
      story ||= page.pathname.match(/^\/video\/([\w-]+)\/embed\/?$/)?.[1];
      if (story) {
        const data = await json(`/api/stories/${story}/manifest-refresh`, true);
        const candidate = P.track(data.signedManifestUrl, "auto", href);
        if (candidate) {
          const url = new URL(candidate.url);
          if (
            url.hostname === "prod-stream.tella.tv" &&
            url.pathname === "/media/manifest.m3u8" &&
            url.searchParams.get("story_id") === story
          )
            yield candidate;
        }
      }
    }
    if (families.has("skillshare")) {
      const data = win.SS?.serverBootstrap?.pageData?.videoPlayerData;
      const sessions = list(data?.units, 1000).flatMap((unit) =>
        list(unit?.sessions, 1000),
      );
      const active = doc.querySelector(
        ".session-item.active .session-item-rank [data-rank], .session-item.active [data-rank]",
      );
      const rank = Number(active?.getAttribute("data-rank"));
      // The bootstrap startingSession is stale after SPA changes: require current DOM selection.
      const selected =
        Number.isInteger(rank) && rank > 0
          ? sessions[rank - 1]
          : sessions.length === 1
            ? sessions[0]
            : null;
      if (/^[\w-]+$/.test(String(selected?.id || ""))) {
        const data = await json(`/sessions/${selected.id}/stream`, true);
        for (const stream of list(data.streams)) {
          if (String(stream.type).toLowerCase() !== "hls") continue;
          const candidate = P.track(stream.url, "auto", href);
          if (candidate) {
            const url = new URL(candidate.url);
            if (
              url.hostname.endsWith(".cloudflarestream.com") &&
              /\.m3u8$/i.test(url.pathname)
            )
              yield candidate;
          }
        }
      }
    }
    if (families.has("updraft")) {
      const candidates = objects(
        scriptJson(doc, 'script[type="application/ld+json"]'),
      ).filter(
        (row) =>
          [row["@type"]].flat().includes("VideoObject") &&
          typeof row.contentUrl === "string",
      );
      const associated = candidates.filter((row) => {
        const owner =
          row.url ||
          row.embedUrl ||
          row.mainEntityOfPage?.["@id"] ||
          row.mainEntityOfPage;
        if (!owner) return candidates.length === 1;
        try {
          return new URL(owner, href).pathname === page.pathname;
        } catch {
          return false;
        }
      });
      if (associated.length === 1) {
        const candidate = P.track(
          associated[0].contentUrl,
          associated[0].inLanguage || "en",
          href,
        );
        if (
          candidate &&
          new URL(candidate.url).hostname === "stream.mux.com" &&
          /^\/[\w-]+\.m3u8$/.test(new URL(candidate.url).pathname)
        )
          yield candidate;
      }
    }
    if (families.has("bbc")) {
      const id = page.pathname.match(
        /\/(?:news\/videos|reel\/video)\/([\w-]+)/,
      )?.[1];
      if (id) {
        const data = await json(
          `https://web-cdn.api.bbci.co.uk/xd/page/content?path=${encodeURIComponent(page.pathname)}`,
        );
        const models = objects(data)
          .map((row) => row.model)
          .filter(
            (row) =>
              row &&
              (row.id || row.pid || row.vpid) &&
              ((!row.type && !row.format) ||
                /video|audio_video/i.test(row.type || row.format)),
          );
        const matches = models.filter((row) =>
          [row.id, row.pid, row.vpid].includes(id),
        );
        const unique = [
          ...new Map(
            (matches.length ? matches : models).map((row) => [
              row.id || row.pid || row.vpid,
              row,
            ]),
          ).values(),
        ];
        if (unique.length === 1) {
          const model = unique[0],
            version =
              model.versionId ||
              model.versions?.[0]?.versionId ||
              model.versions?.[0]?.id;
          if (/^[a-z0-9]+$/i.test(version || "")) {
            let selector;
            try {
              selector = await json(
                `https://open.live.bbc.co.uk/mediaselector/6/select/version/3.0/mediaset/pc/cvid/urn:bbc:pips:pid:${version}/format/json/cors/1`,
              );
            } catch {
              check();
              selector = await json(
                `https://open.live.bbc.co.uk/mediaselector/6/select/version/2.0/mediaset/pc/vpid/${version}/format/json`,
              );
            }
            for (const media of list(selector.media))
              if (media.kind === "captions") {
                for (const connection of list(media.connection)) {
                  if (!connection.href) continue;
                  const url = new URL(connection.href, href);
                  if (
                    url.protocol === "http:" &&
                    /\.(?:bbci\.co\.uk|bbc\.co\.uk|akamaized\.net)$/.test(
                      url.hostname,
                    )
                  )
                    url.protocol = "https:";
                  yield P.track(url.href, media.language || "en", href);
                }
              }
          }
        }
      }
    }
    if (families.has("loom")) {
      const id = page.pathname.match(
        /^\/(?:embed|share)\/([a-f0-9]{32})\/?$/i,
      )?.[1];
      if (id) {
        const body = await read(F.safeUrl(`/share/${id}`, href), true);
        check();
        const decoded = body
          .replace(/\\u002f/gi, "/")
          .replace(/\\\//g, "/")
          .replace(/\\u0026/gi, "&")
          .replace(/&amp;/g, "&");
        const addresses = [
          ...new Set(
            decoded.match(
              /https:\/\/cdn\.loom\.com\/mediametadata\/captions\/[^"'<>\\\s]+\.vtt(?:\?[^"'<>\\\s]+)?/gi,
            ) || [],
          ),
        ];
        // Page-specific VTT avoids guessing units or inventing missing JSON cue ends.
        if (addresses.length === 1) yield P.track(addresses[0], "en", href);
      }
    }
    if (families.has("osmosis")) {
      const parts = page.pathname.split("/").filter(Boolean);
      if (parts[0] === "learn") {
        const localized =
          /^[a-z]{2}(?:-[a-z]{2})?$/i.test(parts[1] || "") && parts[2];
        const slug = decodeURIComponent(parts[localized ? 2 : 1] || "");
        const language = localized
          ? parts[1]
          : page.searchParams.get("language") || "en";
        if (slug && /^[a-z]{2,3}(?:[-_][a-z]{2,4})?$/i.test(language)) {
          const url = new URL("/learnData", page);
          url.searchParams.set("query", slug);
          url.searchParams.set("language", language.split(/[-_]/)[0]);
          if (page.searchParams.has("from"))
            url.searchParams.set("from", page.searchParams.get("from"));
          const data = await json(url.href, true);
          const owners = objects(data).filter(
            (row) => Array.isArray(row.captions) && row.captions.length,
          );
          // A lesson endpoint can contain related videos; never select its first caption array blindly.
          const matched = owners.filter((row) => row.slug === slug);
          const selected =
            matched.length === 1
              ? matched[0]
              : owners.length === 1 && !owners[0].slug
                ? owners[0]
                : null;
          for (const row of list(selected?.captions)) {
            if (typeof row?.src !== "string") continue;
            const address = /^https?:\/\/|^\/\//i.test(row.src.trim())
              ? row.src.trim()
              : new URL(
                  row.src.replace(/^\/+/, ""),
                  "https://d16qt3wv6xm098.cloudfront.net/",
                ).href;
            yield P.track(
              address,
              row.srcLang || row.srclang || row.language || row.lang || "en",
              href,
            );
          }
        }
      }
    }
    if (families.has("gaia")) {
      const container = video.closest("video-js, .video-js");
      let player =
        video.player ||
        video.player_ ||
        container?.player ||
        container?.player_;
      if (!player && container?.id)
        player = win.videojs?.getPlayer?.(container.id);
      const id = String(player?.mediainfo?.id || "");
      if (/^\d+$/.test(id)) {
        const audio = player.audioTracks?.();
        const active = Array.from(
          { length: Math.min(Number(audio?.length) || 0, 100) },
          (_, i) => audio.item?.(i) || audio[i],
        ).find((row) => row?.enabled);
        const language = M.language(active?.language || "en").split("-")[0];
        const address = (path) => {
          const url = new URL(path, "https://brooklyn.gaia.com");
          url.searchParams.set("language[]", language);
          return url;
        };
        const data = await json(address(`/node/${id}`).href, true);
        if (data.nid && String(data.nid) !== id)
          throw new Error("Gaia page node changed");
        const preview = page.searchParams.get("fullplayer") === "preview";
        // Preview and full media have different timing and entitlements.
        const node = preview ? data.preview : data.feature;
        if (/^\d+$/.test(String(node?.nid || ""))) {
          const url = address(`/v1/media-info/${node.nid}`);
          url.searchParams.set("hls", "7");
          const info = await json(url.href, true);
          if (String(player.mediainfo?.id || "") !== id)
            throw new Error("Gaia player changed");
          for (const group of [
            info.textTracks?.captions,
            info.textTracks?.subtitles,
          ]) {
            for (const [lang, value] of Object.entries(group || {}).slice(
              0,
              100,
            )) {
              const candidate = P.track(
                value,
                lang,
                "https://brooklyn.gaia.com/",
              );
              if (
                candidate &&
                new URL(candidate.url).hostname === "brooklyn.gaia.com" &&
                /\.vtt$/i.test(new URL(candidate.url).pathname)
              )
                yield candidate;
            }
          }
        }
      }
    }
    if (families.has("kollus")) {
      let key =
        page.searchParams.get("media_content_key") ||
        page.searchParams.get("mckey");
      if (!key) {
        for (const value of [...page.searchParams.values()].slice(0, 30)) {
          const payload = value.split(".")[1];
          if (!payload || payload.length > 16384) continue;
          try {
            const encoded = payload.replace(/-/g, "+").replace(/_/g, "/");
            const data = JSON.parse(
              win.atob(encoded.padEnd(Math.ceil(encoded.length / 4) * 4, "=")),
            );
            const keys = [
              ...new Set(
                objects(data, 100)
                  .flatMap((row) => [
                    row.mckey,
                    row.media_content_key,
                    row.mediaContentKey,
                  ])
                  .filter((v) => typeof v === "string" && v.length < 512),
              ),
            ];
            if (keys.length === 1) key = keys[0];
          } catch {
            /* Only decode player metadata; this does not authenticate or modify the token. */
          }
        }
      }
      if (key) {
        const owners = list(win.KollusPlayers).filter((row) => {
          try {
            return row.player?.el?.()?.contains(video);
          } catch {
            return false;
          }
        });
        if (owners.length === 1) {
          const item = list(owners[0].media_info?.items).find(
            (row) => row.attr?.media_content_key === key,
          );
          for (const row of list(item?.subtitles)) {
            const candidate = P.track(
              row.subtitle_url,
              row.subtitle_language_code,
              href,
              { default: row.default === true },
            );
            if (
              candidate &&
              /\.(srt|vtt)$/i.test(new URL(candidate.url).pathname)
            )
              yield candidate;
          }
        }
      }
    }
    if (families.has("skool")) {
      const router = win.next?.router;
      const current =
        router?.components?.[router.route || router.pathname]?.props?.pageProps;
      const data = current || P.nextData(doc)?.props?.pageProps;
      const moduleId = page.searchParams.get("md");
      const selected = data?.selectedModule;
      const selectedId = String(selected?.id || "");
      const player = data?.video;
      // Bootstrap data may still describe the previous classroom module after SPA navigation.
      if (
        moduleId &&
        selectedId === moduleId &&
        /^[\w-]+$/.test(player?.playbackId || "") &&
        typeof player?.playbackToken === "string" &&
        player.playbackToken.length > 0 &&
        player.playbackToken.length < 16384
      ) {
        const url = new URL(
          `https://stream.video.skool.com/${player.playbackId}.m3u8`,
        );
        url.searchParams.set("token", player.playbackToken);
        yield P.track(url.href, player.language || "en", href);
      }
    }
    if (families.has("okru")) {
      const id = page.pathname.match(/^\/video\/([^/]+)/)?.[1];
      const parse = (value) => {
        if (typeof value === "string") {
          if (value.length > F.MAX_BYTES) return null;
          try {
            value = JSON.parse(value);
          } catch {
            return null;
          }
        }
        return value && typeof value === "object" && !Array.isArray(value)
          ? value
          : null;
      };
      if (id)
        for (const node of [...doc.querySelectorAll("[data-options]")].slice(
          0,
          32,
        )) {
          const options = parse(node.getAttribute("data-options"));
          const flash = parse(options?.flashvars),
            data = parse(flash?.metadata),
            movie = parse(data?.movie);
          if (String(movie?.id || "") !== id) continue;
          const tracks = list(movie.subtitleTracks || data.subtitleTracks);
          const truth = (v) =>
            v === true || v === 1 || v === "true" || v === "1";
          tracks.sort(
            (a, b) =>
              Number(truth(b.default || b.isDefault || b.defaultTrack)) -
              Number(truth(a.default || a.isDefault || a.defaultTrack)),
          );
          for (const row of tracks)
            yield P.track(
              row.url || row.src || row.href,
              row.lang || row.language || row.locale || row.srclang,
              href,
            );
        }
    }
    if (families.has("sketchy_cloudflare")) {
      const id = page.pathname.match(/^\/([a-f0-9]{32})\/iframe\/?$/i)?.[1];
      if (
        id &&
        page.hostname === "customer-uvgt1jgt7nqod9np.cloudflarestream.com"
      ) {
        const url = new URL(`/${id}/manifest/video.m3u8`, page);
        // Signed embeds can carry authorization in the query. Preserve it only on the same host.
        url.search = page.search;
        yield P.track(url.href, "auto", href);
      }
    }
    if (families.has("motionmagic")) {
      const item = page.searchParams.get("item-id");
      if (item && /^[\w-]{1,200}$/.test(item)) {
        const call = async (rpc) => {
          check();
          const address = "https://backend.codedamn.com/api";
          motionRequest(address, rpc, href);
          const result = JSON.parse(await read(address, false, null, rpc));
          check();
          const output = result?.[0]?.output;
          if (output?.status !== "ok")
            throw new Error(
              "MotionMagic metadata request denied or unavailable",
            );
          return output.data?.response;
        };
        const course = await call({
          method: "get-course-item-information",
          item,
        });
        const data = course?.data?.courseItemData;
        if (data?.id && String(data.id) !== item)
          throw new Error("MotionMagic course item changed");
        const videoData = data?.videoData;
        if (
          videoData?.availabilityState === "ready-for-playback" &&
          videoData.playbackToken
        ) {
          const result = await call({
            method: "get-details-to-play-fermion-saas-recorded-video",
            video: videoData.videoId,
            token: videoData.playbackToken,
          });
          if (result?.availabilityState === "ready-for-playback")
            for (const row of list(result.data?.signedCaptions))
              yield P.track(row.src, row.language || "en", href);
        }
      }
    }
    if (families.has("vidlove")) {
      const id = page.pathname.match(/^\/embed\/movie\/(\d+)\/?$/)?.[1];
      if (id) {
        const data = await json(
          `https://api.shows.st/movie?id=${id}&mode=json&sources=moviebox2&hevc=1`,
        );
        for (const row of list(data.subtitles))
          yield P.track(row.file, row.language || row.lang || row.label, href);
      }
    }
    if (families.has("patreon")) {
      const post = page.pathname.match(/\/posts\/(?:[^/]+-)?(\d+)\/?$/)?.[1];
      if (post) {
        const roots = [
          win.patreon?.bootstrap,
          ...scriptJson(doc, 'script[type="application/json"]'),
        ];
        for (const owner of objects(roots).filter(
          (row) => String(row.id || row.post_id || "") === post,
        )) {
          const data =
            owner.attributes?.viewer_playback_data ||
            owner.viewer_playback_data;
          const urls = objects(data, 200)
            .flatMap((row) => Object.values(row))
            .filter((value) => typeof value === "string");
          if (typeof data === "string") urls.push(data);
          for (const value of [...new Set(urls)]) {
            const candidate = P.track(
              value,
              owner.attributes?.language || owner.language || "en",
              href,
            );
            if (
              candidate &&
              new URL(candidate.url).hostname === "stream.mux.com" &&
              /\.m3u8$/.test(new URL(candidate.url).pathname)
            )
              yield candidate;
          }
        }
      }
    }
    if (families.has("google_drive_youtube")) {
      const player = video.closest(
        "#movie_player, #video-player, .html5-video-player",
      );
      const id = player?.getVideoData?.()?.video_id;
      const routeId =
        page.searchParams.get("docid") ||
        page.searchParams.get("v") ||
        page.pathname.match(/^\/embed\/([\w-]+)/)?.[1];
      if (
        typeof id === "string" &&
        /^[\w-]{6,200}$/.test(id) &&
        (!routeId || routeId === id)
      ) {
        let account = page.searchParams.get("authuser") || "0";
        try {
          const referrer = new URL(doc.referrer);
          if (referrer.hostname === "drive.google.com")
            account = referrer.pathname.match(/\/u\/(\d+)/)?.[1] || account;
        } catch {}
        if (!/^\d{1,3}$/.test(account))
          throw new Error("Unsupported Drive account selector");
        const address = new URL(
          `https://drive.google.com/u/${account}/timedtext`,
        );
        for (const [key, value] of Object.entries({
          id,
          v: id,
          type: "list",
          tlangs: "1",
          vssids: "1",
        }))
          address.searchParams.set(key, value);
        check();
        const body = await read(address.href, true);
        check();
        if (body.length > F.MAX_BYTES || /<!DOCTYPE|<!ENTITY/i.test(body))
          throw new Error("Invalid Drive caption list");
        const xml = new DOMParser().parseFromString(body, "application/xml");
        if (xml.getElementsByTagName("parsererror").length)
          throw new Error("Malformed Drive caption list");
        const tracks = [...xml.getElementsByTagName("track")].slice(0, 100);
        const current = player.getOption?.("captions", "track")?.languageCode;
        tracks.sort(
          (a, b) =>
            Number(
              (b.getAttribute("lang_code") || b.getAttribute("lang")) ===
                current || b.getAttribute("lang_default") === "true",
            ) -
            Number(
              (a.getAttribute("lang_code") || a.getAttribute("lang")) ===
                current || a.getAttribute("lang_default") === "true",
            ),
        );
        for (const track of tracks) {
          const lang =
            track.getAttribute("lang_code") || track.getAttribute("lang");
          if (!/^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/i.test(lang || "")) continue;
          const url = new URL(address);
          url.searchParams.delete("tlangs");
          url.searchParams.delete("vssids");
          for (const [key, value] of Object.entries({
            type: "track",
            fmt: "json3",
            lang,
            name: track.getAttribute("name") || "",
          }))
            url.searchParams.set(key, value);
          for (const [key, value] of Object.entries({
            kind: track.getAttribute("kind"),
            vssid: track.getAttribute("vss_id") || track.getAttribute("vssid"),
          }))
            if (value) url.searchParams.set(key, value);
          const data = await json(url.href, true);
          if (player.getVideoData?.()?.video_id !== id)
            throw new Error("Drive video changed");
          yield { cues: root.VeloaCaptions.json3(data), language: lang };
        }
      }
    }
  }
  root.VocalmReaders = {
    discover,
    manifestAllowed,
    incrementalCues,
    objects,
    scriptJson,
    mediaUrls,
    sourceCaptions,
    dataObjects,
    playbackHeaders,
    motionRequest,
    captionUrl,
    observedKind,
    observedTracks,
  };
  if (typeof module !== "undefined") module.exports = root.VocalmReaders;
})(globalThis);

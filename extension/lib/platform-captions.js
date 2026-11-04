(function (root) {
  "use strict";
  const F = root.VeloaSubtitleFormats,
    M = root.VeloaMedia;
  const list = (value) => (Array.isArray(value) ? value.slice(0, 100) : []);
  function nextData(doc) {
    const value = doc.querySelector("script#__NEXT_DATA__")?.textContent;
    if (!value || value.length > F.MAX_BYTES) return null;
    try {
      return JSON.parse(value);
    } catch {
      return null;
    }
  }
  function track(url, language = "auto", base = location.href, extra = {}) {
    if (typeof url !== "string" || !url.trim()) return null;
    try {
      return {
        url: F.safeUrl(url, base),
        language: M.language(language),
        ...extra,
      };
    } catch {
      return null;
    }
  }
  function entries(rows, urlField, languageField, base) {
    return list(rows)
      .map((r) => track(r?.[urlField], r?.[languageField], base))
      .filter(Boolean);
  }
  function videojsTracks(video, win = window, href = location.href) {
    const rows = [],
      seen = new Set();
    const container = video.closest(".video-js, video-js, [data-vjs-player]");
    const owned = new Set(
      [
        video.player,
        video.player_,
        container?.player,
        container?.player_,
      ].filter(Boolean),
    );
    let registry;
    try {
      registry = win.videojs?.getPlayers?.() || win.videojs?.players;
    } catch {}
    const players = new Set([
      ...owned,
      ...Object.values(registry || {}).slice(0, 100),
    ]);
    const array = (value) => {
      if (Array.isArray(value?.tracks_)) return value.tracks_.slice(0, 100);
      if (!value || !Number.isInteger(value.length) || value.length < 0)
        return [];
      return Array.from(
        { length: Math.min(value.length, 100) },
        (_, i) => value[i],
      );
    };
    for (const player of players) {
      try {
        if (!owned.has(player) && !player?.el?.()?.contains(video)) continue;
        for (const getTracks of [
          () => player.mediainfo?.text_tracks,
          () => player.options?.()?.tracks,
          () => player.remoteTextTrackEls?.(),
          () => player.textTracks?.(),
          () => player.remoteTextTracks?.(),
          () => player.textTracks_,
          () => player.remoteTextTracks_,
        ]) {
          let values;
          try {
            values = array(getTracks());
          } catch {
            continue;
          }
          for (const item of values) {
            if (!item) continue;
            const kind =
              item.kind ||
              item.kind_ ||
              item.options_?.kind ||
              item.track?.kind;
            if (
              kind &&
              !["captions", "subtitles"].includes(String(kind).toLowerCase())
            )
              continue;
            const url =
              item.src ||
              item.src_ ||
              item.file ||
              item.url ||
              item.options_?.src ||
              item.track?.src;
            const lang =
              item.language ||
              item.srclang ||
              item.srcLang ||
              item.language_ ||
              item.options_?.language ||
              item.options_?.srclang ||
              item.track?.language;
            const candidate = track(url, lang, href, {
              default: Boolean(item.default),
            });
            if (candidate && !seen.has(candidate.url)) {
              seen.add(candidate.url);
              rows.push(candidate);
            }
          }
        }
      } catch {
        /* One disposed SDK player must not hide another owned source. */
      }
    }
    return rows;
  }
  function metadataMatches(address, data, href = location.href) {
    const page = new URL(href),
      request = new URL(address, href);
    const lecture =
      page.pathname.match(/\/learn\/lecture\/(\d+)/)?.[1] ||
      page.hash.match(/\/lecture\/(\d+)/)?.[1];
    if (/(^|\.)udemy\.[a-z.]+$/.test(page.hostname) && lecture) {
      const requested = request.pathname.match(/\/lectures\/(\d+)\/?$/)?.[1];
      return (
        requested === lecture &&
        (data?.id === undefined || String(data.id) === lecture)
      );
    }
    if (page.hostname === "app.chartacademy.com") {
      const current = page.pathname.match(
        /\/masterclasses\/([^/]+)\/video\/([^/]+)/,
      );
      const api = request.pathname.match(
        /\/master_classes\/([^/]+)\/videos\/([^/]+)/,
      );
      return Boolean(
        current && api && current[1] === api[1] && current[2] === api[2],
      );
    }
    return true;
  }
  function parse(value, format) {
    if (format !== "edx") return F.parse(value);
    if (typeof value !== "string" || value.length > F.MAX_BYTES)
      throw new Error("Subtitle byte limit exceeded");
    const data = JSON.parse(value);
    if (
      !Array.isArray(data.start) ||
      !Array.isArray(data.end) ||
      !Array.isArray(data.text) ||
      data.start.length !== data.end.length ||
      data.start.length !== data.text.length ||
      data.start.length > F.MAX_CUES
    )
      throw new Error("Invalid edX transcript arrays");
    return F.normalize(
      data.start.map((start, i) => ({
        start: start / 1000,
        end: data.end[i] / 1000,
        text: data.text[i],
      })),
    );
  }
  async function* discover({
    video,
    read,
    check,
    win = window,
    doc = document,
    href = location.href,
  }) {
    const page = new URL(href),
      rules = M.rules(href),
      families = new Set(rules.map((r) => r.family));
    const json = async (url, session = false) => {
      check();
      const value = JSON.parse(await read(F.safeUrl(url, href), session));
      check();
      return value;
    };
    const next = () => nextData(doc);
    const props = (data) => data?.props?.pageProps || data?.pageProps;
    if (families.has("udemy")) {
      const lecture = page.pathname.match(/\/learn\/lecture\/(\d+)/)?.[1];
      const raw = doc
        .querySelector('[data-module-id="course-taking"]')
        ?.getAttribute("data-module-args");
      let course;
      if (raw && raw.length <= F.MAX_BYTES) course = JSON.parse(raw)?.courseId;
      if (lecture && /^\d+$/.test(String(course || ""))) {
        const url = new URL(
          `/api-2.0/users/me/subscribed-courses/${course}/lectures/${lecture}/`,
          href,
        );
        url.searchParams.set("fields[lecture]", "id,asset");
        url.searchParams.set("fields[asset]", "id,captions");
        const data = await json(url.href, true);
        if (String(data.id) !== lecture)
          throw new Error("Udemy lecture changed");
        const rows = list(data.asset?.captions).filter(
          (r) =>
            r &&
            (r.status === undefined || r.status === 1) &&
            (r.asset_id === undefined ||
              String(r.asset_id) === String(data.asset.id)),
        );
        if (rows.length) {
          let language = "auto";
          try {
            const info = await json(
              `/api-2.0/courses/${course}/?fields[course]=id,locale`,
              true,
            );
            if (String(info.id) === String(course))
              language = M.language(info.locale?.locale);
          } catch {
            check();
          }
          const selected = [
            ...doc.querySelectorAll(
              '[role="menuitemradio"][aria-checked="true"]',
            ),
          ].map((el) => el.textContent.trim());
          const rank = (row) => {
            const lang = M.language(row.locale_id);
            return (
              (language !== "auto" &&
              lang.split("-")[0] === language.split("-")[0]
                ? 100
                : 0) +
              (selected.includes(row.video_label) ? 10 : 0) +
              (row.source === "manual" ? 1 : 0)
            );
          };
          rows.sort((a, b) => rank(b) - rank(a));
          if (
            language === "auto" &&
            rows.length > 1 &&
            rank(rows[0]) === rank(rows[1])
          )
            throw new Error("Udemy original caption language is ambiguous");
          yield* entries(rows, "url", "locale_id", href);
        }
      }
    }
    if (families.has("vidyard")) {
      const id = page.pathname.match(/^\/([\w-]+)\.html$/)?.[1];
      if (id) {
        const data = await json(`https://play.vidyard.com/player/${id}.json`);
        const chapters = list(data.payload?.chapters);
        const label = video.getAttribute("aria-label");
        const posterId = (
          video.getAttribute("poster") ||
          video.poster ||
          ""
        ).match(/\/thumbnails\/(\d+)\//)?.[1];
        const matches = chapters.filter(
          (c) =>
            (label && c.name === label) ||
            (posterId && String(c.videoId) === posterId),
        );
        const chapter =
          chapters.length === 1
            ? chapters[0]
            : matches.length === 1
              ? matches[0]
              : null;
        if (chapter)
          yield* entries(chapter.captions, "vttUrl", "language", href);
      }
    }
    if (families.has("adobetv")) {
      const id = page.pathname.match(/^\/v\/(\d+)/)?.[1];
      const bridge = win.bridge;
      if (id && String(bridge?.humanID ?? bridge?.viewBucketID) === id)
        for (const row of list(bridge.translations))
          yield track(
            row.vttPath,
            row.language_locale || row.language_w3c,
            href,
          );
    }
    if (families.has("feynmanlectures")) {
      const captions = list(win.FMLCaptions);
      const links = [...doc.querySelectorAll(".videolink")];
      let selected = links.findIndex((el) => el.classList.contains("current"));
      if (selected < 0) {
        const clean = (s) =>
          String(s || "")
            .replace(/\s+/g, " ")
            .trim();
        const title = clean(
          video.closest(".video-js")?.querySelector(".vjs-title-bar")
            ?.textContent,
        );
        const matches = list(win.FMLTitleBars)
          .map((row, index) => ({ row, index }))
          .filter(({ row }) => title && clean(row.title) === title);
        if (matches.length === 1) selected = matches[0].index;
      }
      // Reject ambiguous lecture state instead of silently choosing lecture one.
      if (selected >= 0 && captions[selected])
        yield track(
          captions[selected].src,
          captions[selected].srclang || "en",
          href,
        );
    }
    if (families.has("edx")) {
      const block = video.closest(".video[data-metadata]");
      const raw = block?.getAttribute("data-metadata");
      if (raw && raw.length <= F.MAX_BYTES) {
        const data = JSON.parse(raw),
          template = data.transcriptTranslationUrl;
        if (typeof template === "string") {
          const langs = Object.keys(data.transcriptLanguages || {}).slice(
            0,
            100,
          );
          langs.sort(
            (a, b) =>
              Number(b === data.transcriptLanguage) -
              Number(a === data.transcriptLanguage),
          );
          for (const language of langs)
            yield track(
              template.replace("__lang__", encodeURIComponent(language)),
              language,
              href,
              { format: "edx" },
            );
        }
      }
    }
    if (families.has("egghead")) {
      const data = props(next()),
        slug = decodeURIComponent(
          page.pathname.split("/").filter(Boolean).at(-1) || "",
        );
      const lesson = data?.initialLesson;
      const post = data?.post?.fields || data?.post;
      const fields =
        post?.slug === slug
          ? data?.videoResource?.fields
          : lesson?.slug === slug
            ? lesson.fields || lesson
            : null;
      const srt = fields?.srt || (lesson?.slug === slug ? lesson.srt : null);
      if (typeof srt === "string" && srt.trim())
        yield { cues: F.parse(srt), language: "en" };
    }
    if (families.has("datacamp")) {
      const key = page.searchParams.get("projector_key"),
        match = key?.match(/^course_(\d+)_[\w-]+$/);
      if (match) {
        yield track(
          `https://assets.datacamp.com/production/course_${match[1]}/subtitles/${key}.vtt`,
          "en",
          href,
        );
        for (const language of [
          "zh",
          "zh-tw",
          "ar",
          "bn",
          "nl",
          "fr",
          "de",
          "hi",
          "id",
          "it",
          "ja",
          "ko",
          "ms",
          "pl",
          "pt",
          "ru",
          "sk",
          "es",
          "th",
          "tr",
          "ur",
          "vi",
        ])
          yield track(
            `https://projector-subtitles.datacamp.com/course_${match[1]}/${key}__${language}.vtt`,
            language,
            href,
          );
      }
    }
    if (families.has("ted")) {
      const slug = decodeURIComponent(
        page.pathname.match(/\/talks\/([^/]+)/)?.[1] || "",
      );
      let data = next();
      const current = (value) => {
        const info = props(value)?.videoData;
        if (!info) return null;
        let player = info.videoPlayerData || info.playerData;
        if (typeof player === "string") {
          if (player.length > F.MAX_BYTES) return null;
          player = JSON.parse(player);
        }
        if (!player || typeof player !== "object") return null;
        const actual =
          player.slug ||
          info.slug ||
          (info.canonicalUrl &&
            new URL(info.canonicalUrl, href).pathname.match(
              /\/talks\/([^/]+)/,
            )?.[1]);
        return actual === slug ? player : null;
      };
      let player = current(data);
      if (!player && slug && /^[\w-]+$/.test(data?.buildId || "")) {
        data = await json(
          `/_next/data/${data.buildId}/talks/${encodeURIComponent(slug)}.json?slug=${encodeURIComponent(slug)}`,
        );
        player = current(data);
      }
      if (player?.resources?.hls?.metadata) {
        const url = F.safeUrl(player.resources.hls.metadata, href),
          metadata = await json(url);
        const tracks = entries(metadata.subtitles, "webvtt", "code", url);
        tracks.sort(
          (a, b) =>
            Number(b.language === M.language(player.nativeLanguage)) -
            Number(a.language === M.language(player.nativeLanguage)),
        );
        yield* tracks;
      }
      if (player?.resources?.hls?.stream)
        yield track(player.resources.hls.stream, "auto", href);
    }
    if (families.has("navertv")) {
      const clip = page.pathname.match(/^\/v\/([^/]+)/)?.[1];
      const data = next();
      let vod = props(data)?.vodInfo;
      if (
        clip &&
        String(vod?.clip?.clipNo) !== clip &&
        /^[\w-]+$/.test(data?.buildId || "")
      )
        vod = props(
          await json(
            `/_next/data/${data.buildId}/v/${encodeURIComponent(clip)}.json?clipNo=${encodeURIComponent(clip)}`,
          ),
        )?.vodInfo;
      if (
        clip &&
        String(vod?.clip?.clipNo) === clip &&
        vod?.clip?.videoId &&
        vod?.play?.inKey
      ) {
        const metadata = await json(
          `https://apis.naver.com/rmcnmv/rmcnmv/vod/play/v2.0/${encodeURIComponent(vod.clip.videoId)}?key=${encodeURIComponent(vod.play.inKey)}`,
        );
        for (const row of list(metadata.captions?.list))
          yield track(row.source, row.locale || row.language, href);
      }
    }
    if (families.has("rutube")) {
      const id = page.pathname.match(/^\/video\/([\w-]+)\/?$/)?.[1];
      if (id) {
        const address = new URL(`/api/play/options/${id}/`, href);
        address.search = new URLSearchParams({
          no_404: "true",
          referer: href,
          client: "wdp",
        }).toString();
        const data = await json(address.href);
        for (const row of list(data.captions))
          yield track(row.file, row.language || row.lang || row.code, href);
      }
    }
    if (families.has("substack")) {
      const id = video.getAttribute("data-video-id"),
        upload = win._preloads?.post?.videoUpload;
      if (id && String(upload?.id) === id) {
        const transcription =
          upload.extractedAudio?.transcription || upload.transcription;
        const url = track(
          transcription?.cdn_url,
          win._preloads?.post?.language,
          href,
        );
        if (url) {
          const address = new URL(url.url);
          if (
            address.hostname === "substackcdn.com" &&
            /^\/video_upload\/.+\/transcription\.json$/.test(address.pathname)
          )
            yield url;
        }
      }
    }
    if (families.has("bloomberg")) {
      const id = video
        .closest('[id^="skylight-vod-"]')
        ?.id?.slice("skylight-vod-".length);
      if (id && /^[\w-]+$/.test(id)) {
        const data = await json(
          `https://www.bloomberg.com/media-manifest/embed?id=${encodeURIComponent(id)}&variant=ANDROID&streamType=WIFI`,
        );
        if (!data.id || String(data.id) === id)
          yield track(data.captions, data.transcriptLanguage || "en", href);
      }
    }
    if (families.has("dailymotion")) {
      let id =
        page.searchParams.get("video") ||
        page.pathname.match(/\/video\/([a-z0-9]+)/i)?.[1];
      if (!id && doc.referrer) {
        const ref = new URL(doc.referrer);
        if (/(^|\.)dailymotion\.com$/.test(ref.hostname))
          id = ref.pathname.match(/\/video\/([a-z0-9]+)/i)?.[1];
      }
      if (/^[a-z0-9]+$/i.test(id || "")) {
        const player =
          page.pathname.match(/\/player\/([\w-]+)/)?.[1] || "xtv3w";
        const url = `https://geo.dailymotion.com/video/${id}.json?legacy=true&geo=1&player-id=${player}&locale=en`;
        const data = await json(url);
        if (data.subtitles?.enable !== false)
          for (const [language, row] of Object.entries(
            data.subtitles?.data || {},
          ).slice(0, 100))
            for (const address of list(row.urls))
              yield track(address, language, url);
      }
    }
    if (families.has("internet_archive")) {
      const identifier = page.pathname.match(
        /^\/(?:details|embed)\/([^/]+)/,
      )?.[1];
      const container = video.closest(".jwplayer");
      let item;
      try {
        if (typeof win.jwplayer === "function" && container)
          item = win.jwplayer(container.id).getPlaylistItem();
      } catch {}
      const file = item?.orig || item?.file || item?.sources?.[0]?.file;
      if (identifier && file) {
        const filename = decodeURIComponent(
          new URL(file, href).pathname.split("/").at(-1),
        );
        const stem = filename.replace(/\.[^.]+$/, "");
        const data = await json(`/metadata/${encodeURIComponent(identifier)}`);
        if (
          data.metadata?.identifier &&
          data.metadata.identifier !== identifier
        )
          throw new Error("Archive item changed");
        for (const row of Array.isArray(data.files)
          ? data.files.slice(0, 10000)
          : []) {
          const captionStem = row.name?.replace(/\.(?:srt|vtt)$/i, "");
          if (
            /\.(srt|vtt)$/i.test(row.name || "") &&
            (captionStem === stem || captionStem?.startsWith(stem + "."))
          )
            yield track(
              `/download/${encodeURIComponent(identifier)}/${row.name.split("/").map(encodeURIComponent).join("/")}`,
              data.metadata?.language,
              href,
            );
        }
      }
    }
  }
  root.VocalmPlatforms = {
    nextData,
    track,
    entries,
    videojsTracks,
    metadataMatches,
    parse,
    discover,
  };
  if (typeof module !== "undefined") module.exports = root.VocalmPlatforms;
})(globalThis);

(function (root) {
  "use strict";
  const MAX_BYTES = 4 * 1024 ** 2,
    MAX_CUES = 20000;
  function clean(value) {
    return String(value || "")
      .replace(/<br\s*\/?\s*>/gi, "\n")
      .replace(/<[^>]*>/g, "")
      .replace(/&(#x[\da-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi, (_, key) => {
        if (key[0] !== "#")
          return {
            amp: "&",
            lt: "<",
            gt: ">",
            quot: '"',
            apos: "'",
            nbsp: " ",
          }[key.toLowerCase()];
        const n =
          key[1].toLowerCase() === "x"
            ? parseInt(key.slice(2), 16)
            : +key.slice(1);
        return n > 0 && n <= 0x10ffff && !(n >= 0xd800 && n <= 0xdfff)
          ? String.fromCodePoint(n)
          : "";
      })
      .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, "")
      .trim();
  }
  function normalize(rows) {
    if (!Array.isArray(rows) || rows.length > MAX_CUES)
      throw new Error("Subtitle cue limit exceeded");
    const result = [],
      seen = new Set();
    for (const row of rows) {
      const start = Number(row.start),
        end = Number(row.end),
        text = clean(row.text);
      if (!text) continue;
      // Preview sprite coordinates use WebVTT timing too, but contain no speech.
      if (/^\S+#xywh=(?:pixel:)?\d+,\d+,\d+,\d+$/i.test(text))
        throw new Error("Thumbnail storyboard is not a subtitle track");
      if (
        !Number.isFinite(start) ||
        !Number.isFinite(end) ||
        start < 0 ||
        end <= start ||
        end - start > 120 ||
        end > 14400 ||
        text.length > 4000
      )
        throw new Error("Invalid subtitle timing or text");
      const key = `${start}|${end}|${text}`;
      if (!seen.has(key)) {
        result.push({ start, end, text });
        seen.add(key);
      }
    }
    if (!result.length) throw new Error("Subtitle response is empty");
    return result.sort((a, b) => a.start - b.start || a.end - b.end);
  }
  function time(value, fps = 30, tick = 1) {
    const s = String(value).trim();
    let m = s.match(/^(\d+(?:\.\d+)?)(ms|s|m|h|f|t)$/);
    if (m)
      return (
        +m[1] *
        { ms: 0.001, s: 1, m: 60, h: 3600, f: 1 / fps, t: 1 / tick }[m[2]]
      );
    m = s.match(/^(?:(\d+):)?(\d{2}):(\d{2})(?:[.,](\d+)|:(\d{2}))?$/);
    if (!m || +m[2] >= 60 || +m[3] >= 60)
      throw new Error("Invalid subtitle timestamp");
    return (
      +(m[1] || 0) * 3600 +
      +m[2] * 60 +
      +m[3] +
      (m[4] ? Number("0." + m[4]) : +(m[5] || 0) / fps)
    );
  }
  function vtt(text, allowEmpty = false) {
    const rows = [];
    for (const block of text
      .replace(/^\uFEFF/, "")
      .replace(/\r\n?/g, "\n")
      .split(/\n[ \t]*\n/)) {
      const lines = block.trim().split("\n");
      if (/^(WEBVTT|NOTE(?:\s|$)|STYLE$|REGION$)/.test(lines[0])) continue;
      const index = lines.findIndex((line) => line.includes("-->"));
      if (index < 0) continue;
      const m = lines[index].match(/^(\S+)\s+-->\s+(\S+)(?:\s.*)?$/);
      if (!m) throw new Error("Malformed VTT/SRT timing");
      rows.push({
        start: time(m[1]),
        end: time(m[2]),
        text: lines.slice(index + 1).join("\n"),
      });
    }
    return allowEmpty && !rows.length ? [] : normalize(rows);
  }
  function ttml(text) {
    if (/<!DOCTYPE|<!ENTITY/i.test(text))
      throw new Error("XML entities are not allowed");
    const doc = new DOMParser().parseFromString(text, "text/xml");
    if (doc.querySelector("parsererror"))
      throw new Error("Invalid subtitle XML");
    const attr = (node, key) =>
      [...node.attributes].find((a) => a.localName === key)?.value;
    const base = doc.documentElement;
    const multiplier = (attr(base, "frameRateMultiplier") || "1 1")
      .split(/\s+/)
      .map(Number);
    const fps =
        (Number(attr(base, "frameRate") || 30) * multiplier[0]) / multiplier[1],
      tick = Number(attr(base, "tickRate") || 1);
    if (!(fps > 0) || !(tick > 0)) throw new Error("Invalid TTML time base");
    const rows = [];
    function visit(node, parentStart = 0, parentEnd = Infinity) {
      if (attr(node, "timeContainer") === "seq")
        throw new Error("Sequential TTML needs player TextTrack timing");
      const begin = attr(node, "begin"),
        end = attr(node, "end"),
        dur = attr(node, "dur");
      const start = parentStart + (begin ? time(begin, fps, tick) : 0);
      const finish = Math.min(
        parentEnd,
        end ? parentStart + time(end, fps, tick) : Infinity,
        dur ? start + time(dur, fps, tick) : Infinity,
      );
      if (node.localName === "p") {
        if (
          [...node.querySelectorAll("*")].some((child) =>
            ["begin", "end", "dur"].some((key) => attr(child, key)),
          )
        )
          throw new Error("Timed TTML spans require native TextTrack timing");
        for (const br of node.getElementsByTagNameNS("*", "br"))
          br.textContent = "\n";
        rows.push({ start, end: finish, text: node.textContent });
      } else for (const child of node.children) visit(child, start, finish);
    }
    visit(base);
    return normalize(rows);
  }
  function json(data) {
    if (Array.isArray(data?.body))
      return normalize(
        data.body.map((r) => ({ start: r.from, end: r.to, text: r.content })),
      );
    if (Array.isArray(data?.hash?.lines))
      return normalize(
        data.hash.lines.map((r) => ({
          start: r.start,
          end: r.end,
          text: Array.isArray(r.text) ? r.text.join("\n") : r.text,
        })),
      );
    if (Array.isArray(data?.events))
      return normalize(root.VeloaCaptions.json3(data));
    if (Array.isArray(data)) return normalize(data);
    throw new Error("Unrecognized subtitle JSON schema");
  }
  function ass(text) {
    let events = false,
      fields = null;
    const rows = [];
    for (const line of text.split(/\r?\n/)) {
      if (/^\s*\[/.test(line)) {
        events = /^\s*\[Events\]\s*$/i.test(line);
        fields = null;
        continue;
      }
      if (!events) continue;
      if (/^Format:/i.test(line)) {
        fields = line
          .slice(line.indexOf(":") + 1)
          .split(",")
          .map((x) => x.trim().toLowerCase());
        if (
          fields.at(-1) !== "text" ||
          !fields.includes("start") ||
          !fields.includes("end")
        )
          throw new Error("Unsupported ASS event format");
      } else if (/^Dialogue:/i.test(line)) {
        if (!fields) throw new Error("ASS event format is missing");
        const parts = line.slice(line.indexOf(":") + 1).split(",");
        if (parts.length < fields.length)
          throw new Error("Malformed ASS dialogue");
        let drawing = false,
          speech = "";
        for (const part of parts
          .slice(fields.length - 1)
          .join(",")
          .split(/(\{[^}]*\})/)) {
          if (part.startsWith("{")) {
            for (const match of part.matchAll(/\\p(\d+)\b/g))
              drawing = Number(match[1]) > 0;
          } else if (!drawing) speech += part;
        }
        rows.push({
          start: time(parts[fields.indexOf("start")].trim()),
          end: time(parts[fields.indexOf("end")].trim()),
          text: speech.replace(/\\[Nn]/g, "\n").replace(/\\h/g, " "),
        });
        if (rows.length > MAX_CUES)
          throw new Error("Subtitle cue limit exceeded");
      }
    }
    return normalize(rows);
  }
  function parse(text) {
    if (
      typeof text !== "string" ||
      new TextEncoder().encode(text).length > MAX_BYTES
    )
      throw new Error("Subtitle response exceeds 4 MiB");
    const value = text.trim();
    if (/^\[Script Info\]|^\[Events\]/i.test(value)) return ass(value);
    if (/^[{[]/.test(value)) return json(JSON.parse(value));
    if (value.startsWith("<")) return ttml(value);
    return vtt(value);
  }
  function attributes(line) {
    const result = {};
    for (const m of line.matchAll(/([A-Z0-9-]+)=(?:"([^"]*)"|([^,]*))(?:,|$)/g))
      result[m[1]] = m[2] ?? m[3];
    return result;
  }
  function safeUrl(value, base) {
    const url = new URL(value, base);
    if (url.protocol !== "https:" || url.username || url.password)
      throw new Error("Subtitle resource must use HTTPS");
    return url.href;
  }
  function playlist(text, base) {
    if (!text.trimStart().startsWith("#EXTM3U"))
      throw new Error("Invalid HLS playlist");
    const renditions = [],
      segments = [];
    let duration = null,
      elapsed = 0,
      discontinuity = false;
    for (const line of text.split(/\r?\n/).map((s) => s.trim())) {
      if (line.startsWith("#EXT-X-MEDIA:")) {
        const a = attributes(line.slice(13));
        if (a.TYPE === "SUBTITLES" && a.URI)
          renditions.push({
            url: safeUrl(a.URI, base),
            language: a.LANGUAGE || "auto",
            default: a.DEFAULT === "YES",
            label: a.NAME || "",
          });
      }
      if (
        line.startsWith("#EXT-X-KEY:") &&
        attributes(line.slice(11)).METHOD !== "NONE"
      )
        throw new Error("Encrypted subtitle playlists are unsupported");
      if (/^#EXT-X-(BYTERANGE|MAP|PART):/.test(line))
        throw new Error(
          "Fragmented subtitle playlist requires native TextTrack",
        );
      if (line === "#EXT-X-DISCONTINUITY") discontinuity = true;
      if (line.startsWith("#EXTINF:"))
        duration = Number(line.slice(8).split(",")[0]);
      if (line && !line.startsWith("#") && duration !== null) {
        if (!(duration > 0) || !Number.isFinite(duration))
          throw new Error("Invalid HLS duration");
        segments.push({
          url: safeUrl(line, base),
          start: elapsed,
          duration,
          discontinuity,
        });
        elapsed += duration;
        duration = null;
        discontinuity = false;
      }
    }
    if (segments.length > 1200 || elapsed > 14400)
      throw new Error("Subtitle playlist exceeds limits");
    return { renditions, segments, complete: text.includes("#EXT-X-ENDLIST") };
  }
  async function hls(text, url, load, language, options = {}) {
    const mediaTimeline = options.timing === "media";
    if (
      mediaTimeline &&
      !(Number.isFinite(options.duration) && options.duration > 0)
    )
      throw new Error(
        "Media duration is required for absolute subtitle timing",
      );
    let list = playlist(text, url);
    if (list.renditions.length) {
      const track =
        list.renditions.find((t) => t.language === language) ||
        list.renditions.find(
          (t) =>
            language &&
            language !== "auto" &&
            t.language.toLowerCase().split(/[-_]/)[0] ===
              language.toLowerCase().split(/[-_]/)[0],
        ) ||
        list.renditions.find((t) => t.default) ||
        list.renditions[0];
      url = track.url;
      language = track.language;
      text = await load(url);
      if (text.trimStart().startsWith("WEBVTT"))
        return { cues: vtt(text), language };
      list = playlist(text, url);
    }
    if (!list.complete || !list.segments.length)
      throw new Error(
        "No complete VOD subtitle playlist; enable CC or import SRT",
      );
    const values = new Array(list.segments.length);
    let cursor = 0,
      bytes = 0,
      failed = false;
    await Promise.all(
      Array.from({ length: Math.min(3, values.length) }, async () => {
        try {
          while (!failed && cursor < values.length) {
            const i = cursor++,
              value = await load(list.segments[i].url);
            bytes += new TextEncoder().encode(value).length;
            if (bytes > 16 * 1024 ** 2)
              throw new Error("HLS subtitles exceed 16 MiB");
            if (!value.trimStart().startsWith("WEBVTT"))
              throw new Error("HLS segment is not WebVTT subtitles");
            values[i] = value;
          }
        } catch (error) {
          failed = true;
          throw error;
        }
      }),
    );
    const rows = [];
    let origin = null,
      previousPts = null;
    for (let i = 0; i < values.length; i++) {
      const segment = list.segments[i],
        value = values[i];
      const map = value.match(/X-TIMESTAMP-MAP=([^\r\n]+)/)?.[1];
      let shift = 0;
      if (mediaTimeline) {
        // Medbridge segments already use the course clock, including overlapping cues.
        shift = 0;
      } else if (map) {
        const local = time(map.match(/LOCAL:([^,]+)/)?.[1]),
          raw = Number(map.match(/MPEGTS:(\d+)/)?.[1]);
        if (!Number.isFinite(raw)) throw new Error("Invalid HLS timestamp map");
        let pts = raw / 90000,
          wrap = 2 ** 33 / 90000;
        if (previousPts !== null && !segment.discontinuity)
          pts += Math.round((previousPts - pts) / wrap) * wrap;
        if (origin === null || segment.discontinuity)
          origin = pts - segment.start;
        shift = pts - origin - local;
        previousPts = pts;
      } else if (segment.discontinuity)
        throw new Error("HLS discontinuity requires a timestamp map");
      const cues = vtt(value, true).map((c) => ({
        ...c,
        start: c.start + shift,
        end: c.end + shift,
      }));
      if (
        cues.some((c) =>
          mediaTimeline
            ? c.start < 0 || c.end > options.duration + 1
            : c.end < segment.start - 0.5 ||
              c.start > segment.start + segment.duration + 1,
        )
      )
        throw new Error("Ambiguous HLS subtitle timing");
      rows.push(...cues);
      if (rows.length > MAX_CUES)
        throw new Error("Subtitle cue limit exceeded");
    }
    return { cues: normalize(rows), language: language || "auto" };
  }
  async function bounded(response) {
    if (!response.ok)
      throw new Error(`Subtitle request returned HTTP ${response.status}`);
    if (Number(response.headers.get("content-length")) > MAX_BYTES)
      throw new Error("Subtitle response exceeds 4 MiB");
    const reader = response.body?.getReader();
    if (!reader) throw new Error("Empty subtitle response");
    let bytes = 0;
    const parts = [];
    let expired = false;
    const timer = setTimeout(() => {
      expired = true;
      reader.cancel().catch(() => {});
    }, 8000);
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        bytes += value.length;
        if (bytes > MAX_BYTES) {
          reader.cancel().catch(() => {});
          throw new Error("Subtitle response exceeds 4 MiB");
        }
        parts.push(value);
      }
    } finally {
      clearTimeout(timer);
      reader.releaseLock();
    }
    if (expired) throw new Error("Subtitle response timed out");
    const output = new Uint8Array(bytes);
    let offset = 0;
    for (const part of parts) {
      output.set(part, offset);
      offset += part.length;
    }
    return new TextDecoder().decode(output);
  }
  function mpd(text, address) {
    if (text.length > MAX_BYTES || /<!DOCTYPE|<!ENTITY/i.test(text))
      throw new Error("Invalid MPD document");
    const xml = new DOMParser().parseFromString(text, "application/xml");
    if (
      xml.documentElement?.localName !== "MPD" ||
      xml.getElementsByTagName("parsererror").length
    )
      throw new Error("Invalid MPD XML");
    if (xml.documentElement.getAttribute("type") === "dynamic")
      throw new Error("Live DASH captions require a complete track");
    const periods = [...xml.documentElement.children].filter(
      (node) => node.localName === "Period",
    );
    if (
      periods.length > 1 ||
      periods.some(
        (node) =>
          node.hasAttribute("start") &&
          !/^PT0+(?:\.0+)?S$/.test(node.getAttribute("start")),
      )
    )
      throw new Error(
        "Multi-period DASH captions require explicit timestamp alignment",
      );
    const direct = (node, tag) =>
      [...node.children].filter((el) => el.localName === tag);
    const result = [];
    const visit = (
      node,
      base,
      language = "auto",
      mime = "",
      content = "",
      segmented = false,
    ) => {
      const tag = node.localName;
      language = node.getAttribute("lang") || language;
      mime = node.getAttribute("mimeType") || mime;
      content = node.getAttribute("contentType") || content;
      segmented ||= [
        "SegmentTemplate",
        "SegmentList",
        "SegmentBase",
        "ContentProtection",
      ].some((name) => direct(node, name).length);
      const bases = direct(node, "BaseURL");
      const ownBase = bases[0]?.textContent?.trim();
      if (ownBase) base = safeUrl(ownBase, base);
      if (
        ["AdaptationSet", "Representation"].includes(tag) &&
        !segmented &&
        (ownBase || /\.(?:vtt|webvtt|ttml)(?:[?#]|$)/i.test(base)) &&
        (tag === "Representation" || !direct(node, "Representation").length) &&
        (/^(text\/(?:web)?vtt|application\/ttml\+xml)$/.test(mime) ||
          (content === "text" && /\.(?:vtt|webvtt|ttml)(?:[?#]|$)/i.test(base)))
      ) {
        result.push({ url: base, language });
      }
      if (result.length > 100) throw new Error("Too many DASH subtitle tracks");
      for (const child of node.children)
        if (
          ["Period", "AdaptationSet", "Representation"].includes(
            child.localName,
          )
        )
          visit(child, base, language, mime, content, segmented);
    };
    visit(xml.documentElement, address);
    return result;
  }
  const api = {
    MAX_BYTES,
    clean,
    normalize,
    time,
    vtt,
    ttml,
    json,
    ass,
    parse,
    playlist,
    hls,
    mpd,
    bounded,
    safeUrl,
  };
  root.VeloaSubtitleFormats = api;
  if (typeof module !== "undefined") module.exports = api;
})(globalThis);

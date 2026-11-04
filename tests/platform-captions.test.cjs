const test = require("node:test");
const assert = require("node:assert/strict");
require("../extension/lib/sites.js");
require("../extension/lib/captions.js");
require("../extension/lib/media.js");
const F = require("../extension/lib/subtitle-formats.js");
const P = require("../extension/lib/platform-captions.js");

const vtt = "WEBVTT\n\n00:01.000 --> 00:03.000\nA complete sentence.";
function context(href, data = null, win = {}, video = {}) {
  return {
    href,
    win,
    video: { closest: () => null, getAttribute: () => null, ...video },
    doc: {
      referrer: "",
      querySelectorAll: () => [],
      querySelector: () =>
        data ? { textContent: JSON.stringify(data) } : null,
    },
    check: () => {},
    read: async () => {
      throw new Error("Unexpected metadata request");
    },
  };
}
async function collect(ctx) {
  const rows = [];
  for await (const row of P.discover(ctx)) if (row) rows.push(row);
  return rows;
}
test("Udemy metadata belongs to both current request and response lecture IDs", () => {
  const href = "https://www.udemy.com/course/test/learn/lecture/123";
  const api =
    "https://www.udemy.com/api-2.0/users/me/subscribed-courses/1/lectures/";
  assert.ok(P.metadataMatches(api + "123/", { id: 123 }, href));
  assert.ok(P.metadataMatches(api + "123/", null, href));
  assert.equal(P.metadataMatches(api + "122/", { id: 123 }, href), false);
  assert.equal(P.metadataMatches(api + "123/", { id: 122 }, href), false);
});
test("edX preserves milliseconds, validates parallel arrays and enforces size limits", () => {
  assert.deepEqual(
    P.parse(
      JSON.stringify({ start: [1234], end: [3500], text: ["Line"] }),
      "edx",
    ),
    [{ start: 1.234, end: 3.5, text: "Line" }],
  );
  assert.throws(() => P.parse('{"start":[1],"end":[],"text":["Line"]}', "edx"));
  assert.throws(() => P.parse(" ".repeat(F.MAX_BYTES + 1), "edx"), /limit/);
});
test("edX reads only the selected video block and prioritizes its active language", async () => {
  const ctx = context("https://courses.edx.org/courseware/test");
  ctx.video.closest = () => ({
    getAttribute: () =>
      JSON.stringify({
        transcriptTranslationUrl: "/transcript/__lang__",
        transcriptLanguages: { en: "English", vi: "Vietnamese" },
        transcriptLanguage: "vi",
      }),
  });
  const rows = await collect(ctx);
  assert.equal(rows[0].url, "https://courses.edx.org/transcript/vi");
  assert.equal(rows[0].format, "edx");
});
test("Egghead rejects stale Next data and preserves existing SRT timing", async () => {
  const data = {
    props: {
      pageProps: {
        post: { fields: { slug: "current" } },
        videoResource: { fields: { srt: vtt } },
      },
    },
  };
  assert.equal(
    (await collect(context("https://egghead.io/lessons/current", data)))[0]
      .cues[0].end,
    3,
  );
  assert.deepEqual(
    await collect(context("https://egghead.io/lessons/new", data)),
    [],
  );
});
test("TED follows current talk metadata and aborts when navigation invalidates ownership", async () => {
  const data = {
    props: {
      pageProps: {
        videoData: {
          playerData: JSON.stringify({
            slug: "current",
            resources: { hls: { metadata: "https://cdn.test/metadata" } },
          }),
        },
      },
    },
  };
  const ctx = context("https://www.ted.com/talks/current", data);
  ctx.read = async (url) => {
    assert.equal(url, "https://cdn.test/metadata");
    return JSON.stringify({
      subtitles: [{ code: "en", webvtt: "captions.vtt" }],
    });
  };
  assert.equal((await collect(ctx))[0].url, "https://cdn.test/captions.vtt");
  ctx.check = () => {
    throw new Error("Video changed");
  };
  await assert.rejects(collect(ctx), /Video changed/);
});
test("TED current live schema uses videoPlayerData object and native-language priority", async () => {
  const ctx = context("https://www.ted.com/talks/current", {
    props: {
      pageProps: {
        videoData: {
          slug: "current",
          videoPlayerData: {
            slug: "current",
            nativeLanguage: "en",
            resources: { hls: { metadata: "https://cdn.test/metadata" } },
          },
        },
      },
    },
  });
  ctx.read = async () =>
    JSON.stringify({
      subtitles: [
        { code: "pt-br", webvtt: "/pt.vtt" },
        { code: "en", webvtt: "/en.vtt" },
      ],
    });
  const rows = await collect(ctx);
  assert.equal(rows[0].language, "en");
  assert.ok(rows[0].url.endsWith("/en.vtt"));
});

test("DataCamp language probes are lazy and tied to projector course ID", async () => {
  const gen = P.discover(
    context("https://projector.datacamp.com/?projector_key=course_42_intro"),
  );
  assert.equal(
    (await gen.next()).value.url,
    "https://assets.datacamp.com/production/course_42/subtitles/course_42_intro.vtt",
  );
  await gen.return();
  assert.deepEqual(
    await collect(context("https://projector.datacamp.com/?projector_key=bad")),
    [],
  );
});
test("Naver requires matching clip number before using in-page playback key", async () => {
  const data = {
    props: {
      pageProps: {
        vodInfo: {
          clip: { clipNo: 123, videoId: "abc" },
          play: { inKey: "fixture" },
        },
      },
    },
  };
  const ctx = context("https://tv.naver.com/v/123", data);
  ctx.read = async (url) => {
    assert.ok(url.includes("/abc?key=fixture"));
    return JSON.stringify({
      captions: { list: [{ source: "https://cdn.test/a.vtt", locale: "ko" }] },
    });
  };
  assert.equal((await collect(ctx))[0].language, "ko");
  assert.deepEqual(
    await collect({ ...ctx, href: "https://tv.naver.com/v/124" }),
    [],
  );
});
test("Rutube reads caption descriptors and propagates denied metadata", async () => {
  const ctx = context("https://rutube.ru/video/abc/");
  ctx.read = async (url) => {
    assert.ok(url.includes("/api/play/options/abc/"));
    return JSON.stringify({
      captions: [{ file: "https://cdn.test/ru.srt", language: "ru" }],
    });
  };
  assert.equal((await collect(ctx))[0].language, "ru");
  ctx.read = async () => {
    throw new Error("HTTP 403");
  };
  await assert.rejects(collect(ctx), /403/);
});
test("Substack requires active videoUpload ID and exact transcription CDN", async () => {
  const upload = {
    id: 123,
    extractedAudio: {
      transcription: {
        cdn_url: "https://substackcdn.com/video_upload/123/transcription.json",
      },
    },
  };
  const ctx = context(
    "https://author.substack.com/p/post",
    null,
    { _preloads: { post: { videoUpload: upload } } },
    { getAttribute: () => "123" },
  );
  assert.equal((await collect(ctx)).length, 1);
  upload.id = 124;
  assert.deepEqual(await collect(ctx), []);
  upload.id = 123;
  upload.extractedAudio.transcription.cdn_url =
    "https://substackcdn.com.evil.test/video_upload/123/transcription.json";
  assert.deepEqual(await collect(ctx), []);
});
test("Bloomberg binds response ID to selected skylight player", async () => {
  const ctx = context(
    "https://www.bloomberg.com/news/videos/test",
    null,
    {},
    { closest: () => ({ id: "skylight-vod-123" }) },
  );
  ctx.read = async () =>
    JSON.stringify({ id: "123", captions: "/captions.ttml" });
  assert.equal((await collect(ctx)).length, 1);
  ctx.read = async () =>
    JSON.stringify({ id: "124", captions: "/captions.ttml" });
  assert.deepEqual(await collect(ctx), []);
});
test("Dailymotion respects subtitles enable flag and language URL lists", async () => {
  const ctx = context("https://geo.dailymotion.com/player/x1.html?video=x2");
  ctx.read = async () =>
    JSON.stringify({
      subtitles: { data: { fr: { urls: ["https://cdn.test/fr.srt"] } } },
    });
  assert.equal((await collect(ctx))[0].language, "fr");
  ctx.read = async () =>
    JSON.stringify({
      subtitles: {
        enable: false,
        data: { fr: { urls: ["https://cdn.test/fr.srt"] } },
      },
    });
  assert.deepEqual(await collect(ctx), []);
});
test("Archive finds late sidecars but never borrows another playlist file", async () => {
  const ctx = context(
    "https://archive.org/details/collection",
    null,
    { jwplayer: () => ({ getPlaylistItem: () => ({ orig: "lecture.mp4" }) }) },
    { closest: () => ({ id: "jw" }) },
  );
  ctx.read = async () =>
    JSON.stringify({
      metadata: { identifier: "collection" },
      files: [
        ...Array.from({ length: 200 }, (_, i) => ({ name: `other${i}.vtt` })),
        { name: "lecture.en.vtt" },
      ],
    });
  const rows = await collect(ctx);
  assert.equal(rows.length, 1);
  assert.ok(rows[0].url.endsWith("/lecture.en.vtt"));
});
test("Vidyard selects a unique current chapter instead of borrowing the first", async () => {
  const ctx = context(
    "https://play.vidyard.com/player1.html",
    null,
    {},
    { getAttribute: (key) => (key === "aria-label" ? "Second" : null) },
  );
  ctx.read = async () =>
    JSON.stringify({
      payload: {
        chapters: [
          { name: "First", captions: [{ vttUrl: "https://cdn.test/1.vtt" }] },
          { name: "Second", captions: [{ vttUrl: "https://cdn.test/2.vtt" }] },
        ],
      },
    });
  assert.equal((await collect(ctx))[0].url, "https://cdn.test/2.vtt");
  ctx.video.getAttribute = () => null;
  assert.deepEqual(await collect(ctx), []);
});
test("Adobe rejects stale bridge IDs and normalizes locale", async () => {
  const ctx = context("https://video.tv.adobe.com/v/123", null, {
    bridge: {
      humanID: 123,
      translations: [{ vttPath: "/en.vtt", language_locale: "en_US" }],
    },
  });
  assert.equal((await collect(ctx))[0].language, "en-US");
  ctx.win.bridge.humanID = 124;
  assert.deepEqual(await collect(ctx), []);
});
test("Video.js reads attached SDK tracks and ignores foreign players or thumbnails", () => {
  const own = {
    remoteTextTracks: () => ({
      tracks_: [
        { kind_: "subtitles", src_: "/own.vtt", language_: "en_US" },
        { options_: { kind: "metadata", src: "/thumbnails.vtt" } },
        {
          track: {
            kind: "captions",
            src: "/other-language.vtt",
            language: "fr",
          },
        },
        { src: "http://insecure.test/caption.vtt" },
      ],
    }),
  };
  const video = { closest: () => ({ player: own }) };
  const other = {
    el: () => ({ contains: () => false }),
    mediainfo: { text_tracks: [{ src: "/foreign.vtt" }] },
  };
  const rows = P.videojsTracks(
    video,
    { videojs: { getPlayers: () => ({ other }) } },
    "https://course.test/lesson",
  );
  assert.deepEqual(
    rows.map((r) => r.url),
    ["https://course.test/own.vtt", "https://course.test/other-language.vtt"],
  );
  assert.equal(rows[0].language, "en-US");
});

test("Udemy resolves original course locale without resource history or enabled CC", async () => {
  const ctx = context("https://www.udemy.com/course/test/learn/lecture/123");
  ctx.doc.querySelector = () => ({
    getAttribute: () => JSON.stringify({ courseId: 7 }),
  });
  const rows = [
    {
      url: "/de.vtt",
      locale_id: "de_DE",
      source: "auto",
      asset_id: 9,
      status: 1,
    },
    {
      url: "/fr.vtt",
      locale_id: "fr_FR",
      source: "manual",
      asset_id: 9,
      status: 1,
    },
    {
      url: "/wrong.vtt",
      locale_id: "en_US",
      source: "manual",
      asset_id: 8,
      status: 1,
    },
    {
      url: "/en.vtt",
      locale_id: "en_US",
      source: "manual",
      asset_id: 9,
      status: 1,
    },
  ];
  ctx.read = async (url, session) => {
    assert.equal(session, true);
    return JSON.stringify(
      url.includes("/lectures/")
        ? { id: 123, asset: { id: 9, captions: rows } }
        : { id: 7, locale: { locale: "en_US" } },
    );
  };
  const result = await collect(ctx);
  assert.equal(result[0].language, "en-US");
  assert.ok(result[0].url.endsWith("/en.vtt"));
  assert.ok(result.every((r) => !r.url.endsWith("/wrong.vtt")));
  ctx.read = async () =>
    JSON.stringify({ id: 124, asset: { id: 9, captions: rows } });
  await assert.rejects(collect(ctx), /lecture changed/);
});

test("Udemy does not guess among languages when locale is denied and selection ambiguous", async () => {
  const ctx = context("https://www.udemy.com/course/test/learn/lecture/123");
  ctx.doc.querySelector = () => ({
    getAttribute: () => JSON.stringify({ courseId: 7 }),
  });
  ctx.read = async (url) => {
    if (!url.includes("/lectures/")) throw new Error("HTTP 403");
    return JSON.stringify({
      id: 123,
      asset: {
        captions: [
          { url: "/a.vtt", locale_id: "fr_FR" },
          { url: "/b.vtt", locale_id: "de_DE" },
        ],
      },
    });
  };
  await assert.rejects(collect(ctx), /ambiguous/);
});

test("Feynman requires a selected lecture, with no implicit first-lecture fallback", async () => {
  const ctx = context(
    "https://www.feynmanlectures.caltech.edu/fml.html",
    null,
    { FMLCaptions: [{ src: "/one.vtt" }, { src: "/two.vtt" }] },
  );
  ctx.doc.querySelectorAll = () => [
    { classList: { contains: () => false } },
    { classList: { contains: () => true } },
  ];
  assert.ok((await collect(ctx))[0].url.endsWith("/two.vtt"));
  ctx.doc.querySelectorAll = () => [];
  assert.deepEqual(await collect(ctx), []);
});

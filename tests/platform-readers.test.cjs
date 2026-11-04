const test = require("node:test");
const assert = require("node:assert/strict");
require("../extension/lib/sites.js");
require("../extension/lib/captions.js");
require("../extension/lib/media.js");
const F = require("../extension/lib/subtitle-formats.js");
require("../extension/lib/platform-captions.js");
const R = require("../extension/lib/platform-readers.js");

test("thumbnail WebVTT cannot become translated or spoken text", () => {
  assert.throws(
    () =>
      F.vtt("WEBVTT\n\n00:00.000 --> 00:01.000\npreview.jpg#xywh=0,0,249,140"),
    /storyboard/,
  );
  assert.throws(
    () =>
      F.normalize([
        {
          start: 0,
          end: 1,
          text: "https://cdn.test/sprite.webp?token=abc#xywh=pixel:0,0,249,140",
        },
      ]),
    /storyboard/,
  );
  assert.equal(
    F.vtt("WEBVTT\n\n00:00.000 --> 00:01.000\nThe image shows a forest.")[0]
      .text,
    "The image shows a forest.",
  );
});

test("VK overlapping rolling captions do not repeat speech; separated repetitions survive", () => {
  const cues = [
    { start: 0, end: 3, text: "First sentence" },
    { start: 2, end: 5, text: "First sentence more words" },
    { start: 4, end: 7, text: "more words next line" },
    { start: 8, end: 9, text: "next line" },
  ];
  assert.deepEqual(
    R.incrementalCues(cues).map((c) => c.text),
    ["First sentence", "more words", "next line", "next line"],
  );
  assert.deepEqual(
    R.incrementalCues([
      { start: 0, end: 2, text: "Same" },
      { start: 1, end: 3, text: "Same" },
    ]),
    [{ start: 0, end: 3, text: "Same" }],
  );
  assert.equal(cues[0].end, 3);
});

test("MotionMagic transport is limited to two metadata operations and exact page item", () => {
  const href = "https://www.themotionmagic.com/course-item?item-id=current",
    url = "https://backend.codedamn.com/api";
  const request = R.motionRequest(
    url,
    { method: "get-course-item-information", item: "current" },
    href,
  );
  assert.equal(request.method, "POST");
  assert.equal(
    JSON.parse(request.body).data[0].data.fermionCourseItemId,
    "current",
  );
  assert.throws(() =>
    R.motionRequest(url, { method: "delete-course", item: "current" }, href),
  );
  assert.throws(() =>
    R.motionRequest(
      url,
      { method: "get-course-item-information", item: "other" },
      href,
    ),
  );
  assert.throws(() =>
    R.motionRequest(
      "https://evil.test/api",
      { method: "get-course-item-information", item: "current" },
      href,
    ),
  );
  assert.throws(() =>
    R.motionRequest(
      url,
      { method: "get-course-item-information", item: "current" },
      "https://evil.test/course-item?item-id=current",
    ),
  );
});

test("observed metadata classifiers do not capture unrelated origins", () => {
  assert.equal(
    R.observedKind(
      "https://evil.test/p/transcript/1",
      "https://www.dropbox.com/scl/fi/id/video",
    ),
    null,
  );
  assert.equal(
    R.observedKind(
      "https://other.circle.so/internal_api/courses/c/sections/s/lessons/1",
      "https://circle-academy.circle.so/c/c/sections/s/lessons/1",
    ),
    null,
  );
  assert.equal(
    R.observedKind(
      "https://h5-api.aoneroom.com.evil.test/wefeed-h5api-bff/subject/caption",
      "https://movebox.run/movies/a",
    ),
    null,
  );
});
test("Dropbox timing uses explicit seconds and rejects pre-player captures", () => {
  const row = {
    url: "https://www.dropbox.com/p/transcript/a",
    token: { node: 1 },
    text: JSON.stringify({
      transcriptLocale: "en_US",
      segments: [{ startTime: 1.25, endTime: 3.5, text: "Caption" }],
    }),
  };
  const href = "https://www.dropbox.com/scl/fi/id/video";
  assert.deepEqual(R.observedTracks(row, {}, href)[0].cues, [
    { start: 1.25, end: 3.5, text: "Caption" },
  ]);
  row.token.node = 0;
  assert.deepEqual(R.observedTracks(row, {}, href), []);
});
test("Circle chooses an attachment whose HLS belongs to the selected player", () => {
  const href = "https://circle-academy.circle.so/c/test/post";
  const row = {
    url: "https://circle-academy.circle.so/internal_api/spaces/123/posts",
    text: JSON.stringify({
      records: [
        {
          inline_attachments: [
            {
              video_variants: { hls: "https://media.test/other.m3u8" },
              media_transcript_id: "old",
            },
            {
              video_variants: {
                hls: "https://media.test/current.m3u8?token=expired",
              },
              media_transcript_id: "current",
            },
          ],
        },
      ],
    }),
  };
  const video = {
    src: "https://media.test/current.m3u8?token=new",
    getAttribute: () => null,
    closest: () => null,
  };
  assert.deepEqual(
    R.observedTracks(row, video, href).map((t) => t.url),
    ["https://circle-academy.circle.so/media_transcripts/current.vtt"],
  );
});

function context(href, overrides = {}) {
  return {
    href,
    video: { closest: () => null, getAttribute: () => null },
    win: { atob },
    doc: { querySelector: () => null, querySelectorAll: () => [] },
    check() {},
    read: async () => {
      throw Error("Unexpected request");
    },
    ...overrides,
  };
}
async function collect(ctx) {
  const rows = [];
  for await (const row of R.discover(ctx)) if (row) rows.push(row);
  return rows;
}
test("reader traversal handles cycles and enforces node limit", () => {
  const obj = { children: Array.from({ length: 10000 }, () => ({})) };
  obj.self = obj;
  assert.ok(R.objects(obj, 17).length <= 17);
  assert.deepEqual(R.objects({ self: null }), [{ self: null }]);
});
test("Brightcove policy header cannot be forwarded to another host or inject headers", () => {
  const url =
    "https://edge.api.brightcove.com/playback/v1/accounts/123/videos/456";
  assert.deepEqual(R.playbackHeaders(url, "public-policy"), {
    Accept: "application/json;pk=public-policy",
  });
  assert.throws(() =>
    R.playbackHeaders("https://other.test/path", "public-policy"),
  );
  assert.throws(() => R.playbackHeaders(url, "key\r\nAuthorization: secret"));
  assert.equal(R.playbackHeaders(url, null), undefined);
});
test("Plex unwraps only HTTPS VTT on its documented subtitle host", () => {
  const href = "https://watch.plex.tv/watch/movie/lesson";
  const wrapped =
    "https://vod.provider.plex.tv/sub?url=" +
    encodeURIComponent("https://vod-static.plex.tv/a.vtt?token=test");
  assert.equal(
    R.captionUrl(wrapped, href),
    "https://vod-static.plex.tv/a.vtt?token=test",
  );
  assert.equal(R.captionUrl(wrapped, "https://other.test/"), wrapped);
  const unsafe =
    "https://vod.provider.plex.tv/sub?url=" +
    encodeURIComponent("http://localhost/secret.vtt");
  assert.equal(R.captionUrl(unsafe, href), unsafe);
});
test("ArtStation rejects course mismatch and rechecks navigation after I/O", async () => {
  const ctx = context(
    "https://www.artstation.com/learning/courses/c/drawing/chapters/current/intro",
  );
  ctx.read = async () => JSON.stringify({ hash_id: "other" });
  await assert.rejects(collect(ctx), /course changed/);
  let calls = 0;
  ctx.read = async () => '{"chapters":[]}';
  ctx.check = () => {
    if (++calls > 1) throw Error("Navigation changed");
  };
  await assert.rejects(collect(ctx), /Navigation changed/);
});
test("Platzi decodes URL-safe descriptors and discards executable URLs", async () => {
  const ctx = context("https://platzi.com/cursos/course/lesson/");
  ctx.video.src =
    "https://cdn.test/media?subtitles=" +
    Buffer.from(
      JSON.stringify([
        { uri: "javascript:alert(1)" },
        { uri: "https://cdn.test/captions.vtt", language: "es" },
      ]),
    ).toString("base64url");
  assert.deepEqual(
    (await collect(ctx)).map((r) => r.language),
    ["es"],
  );
});
test("PandaVideo requires ready player and valid identity/language", async () => {
  const ctx = context(
    "https://player-vz-12345678-abc.tv.pandavideo.com.br/embed/?v=11111111-2222-3333-4444-555555555555",
  );
  ctx.win = {
    pandaLoad: { configVideoLoaded: true, playerLoaded: true },
    player_configs: {
      subtitles: [{ srclang: "../../secret" }, { srclang: "pt" }],
    },
  };
  const rows = await collect(ctx);
  assert.equal(rows.length, 1);
  assert.match(rows[0].url, /\/pt-BR\.vtt$/);
  ctx.win.pandaLoad.playerLoaded = false;
  assert.deepEqual(await collect(ctx), []);
});
test("Tella retains signed URL only for the exact story", async () => {
  const ctx = context("https://www.tella.tv/video/story/embed");
  const signed =
    "https://prod-stream.tella.tv/media/manifest.m3u8?story_id=story&token=test";
  ctx.read = async () => JSON.stringify({ signedManifestUrl: signed });
  assert.equal((await collect(ctx))[0].url, signed);
  ctx.read = async () =>
    JSON.stringify({
      signedManifestUrl: signed.replace("story_id=story", "story_id=old"),
    });
  assert.deepEqual(await collect(ctx), []);
});
test("Skillshare does not trust stale startingSession in a multi-lesson course", async () => {
  const ctx = context("https://www.skillshare.com/en/classes/test/123");
  ctx.win = {
    SS: {
      serverBootstrap: {
        pageData: {
          videoPlayerData: {
            startingSession: 1,
            units: [{ sessions: [{ id: 1 }, { id: 2 }] }],
          },
        },
      },
    },
  };
  assert.deepEqual(await collect(ctx), []);
});
test("Updraft binds embedUrl and prefers declared source language, then English", async () => {
  const href = "https://updraft.cyfrin.io/courses/course/chapter/lesson";
  const row = {
    "@type": "VideoObject",
    embedUrl: href,
    contentUrl: "https://stream.mux.com/id.m3u8?token=test",
  };
  const ctx = context(href);
  ctx.doc.querySelectorAll = () => [{ textContent: JSON.stringify(row) }];
  assert.equal((await collect(ctx))[0].language, "en");
  row.inLanguage = "es";
  assert.equal((await collect(ctx))[0].language, "es");
  row.embedUrl += "old";
  assert.deepEqual(await collect(ctx), []);
});
test("Osmosis rejects ambiguous caption owners and preserves regional path language", async () => {
  const ctx = context("https://www.osmosis.org/learn/es/Heart?from=library");
  ctx.read = async (url, session) => {
    assert.equal(session, true);
    assert.equal(new URL(url).searchParams.get("language"), "es");
    assert.equal(new URL(url).searchParams.get("query"), "Heart");
    return JSON.stringify({
      a: { captions: [{ src: "a.vtt" }] },
      b: { captions: [{ src: "b.vtt" }] },
    });
  };
  assert.deepEqual(await collect(ctx), []);
  ctx.read = async () =>
    JSON.stringify({
      a: { slug: "Heart", captions: [{ src: "a.vtt", srcLang: "es" }] },
      b: { slug: "Other", captions: [{ src: "b.vtt" }] },
    });
  assert.equal(
    (await collect(ctx))[0].url,
    "https://d16qt3wv6xm098.cloudfront.net/a.vtt",
  );
});
test("Gaia rejects changed player during metadata request and preview/full confusion", async () => {
  const ctx = context("https://www.gaia.com/video/lesson");
  ctx.video.player = { mediainfo: { id: 123 } };
  ctx.read = async (url) => {
    if (url.includes("/node/")) return '{"feature":{"nid":456}}';
    ctx.video.player.mediainfo.id = 124;
    return '{"textTracks":{"captions":{"en":"/captions/a.vtt"}}}';
  };
  await assert.rejects(collect(ctx), /player changed/);
  ctx.href += "?fullplayer=preview";
  ctx.video.player.mediainfo.id = 123;
  assert.deepEqual(await collect(ctx), []);
});
test("BBC fallback does not swallow navigation cancellation", async () => {
  const ctx = context("https://www.bbc.com/news/videos/p123");
  let stopped = false;
  ctx.check = () => {
    if (stopped) throw Error("Navigation changed");
  };
  ctx.read = async (url) => {
    if (url.includes("/xd/"))
      return '{"model":{"id":"p123","versionId":"v123"}}';
    stopped = true;
    throw Error("Request cancelled");
  };
  await assert.rejects(collect(ctx), /Navigation changed/);
});
test("Loom refuses an ambiguous page with two independent VTT tracks", async () => {
  const ctx = context(
    "https://www.loom.com/embed/1234567890abcdef1234567890abcdef",
  );
  ctx.read = async () =>
    '"https://cdn.loom.com/mediametadata/captions/a.vtt" "https://cdn.loom.com/mediametadata/captions/b.vtt"';
  assert.deepEqual(await collect(ctx), []);
});
test("HLS matches source language region before unrelated first/default tracks", async () => {
  const text =
    '#EXTM3U\n#EXT-X-MEDIA:TYPE=SUBTITLES,LANGUAGE="bg-BG",DEFAULT=YES,URI="bg.m3u8"\n#EXT-X-MEDIA:TYPE=SUBTITLES,LANGUAGE="en-US",URI="en.m3u8"';
  const result = await F.hls(
    text,
    "https://cdn.test/master.m3u8",
    async (url) => {
      assert.ok(!url.includes("bg.m3u8"));
      return url.endsWith("en.m3u8")
        ? "#EXTM3U\n#EXTINF:5,\na.vtt\n#EXT-X-ENDLIST"
        : "WEBVTT\n\n00:01.000 --> 00:03.000\nSource caption.";
    },
    "en",
  );
  assert.equal(result.language, "en-US");
  assert.equal(result.cues.length, 1);
});

test("Pluralsight accepts only the current clip master, including player-route selection", () => {
  const id = "00000000-0000-0000-0000-000000000001";
  const other = "00000000-0000-0000-0000-000000000002";
  const href = `https://app.pluralsight.com/ilx/video-courses/${id}/${id}/${id}`;
  const address = (clip, suffix = "hls/master.m3u8") => {
    const body = Buffer.from(
      JSON.stringify({ path: `clips2/${clip}/${suffix}` }),
    ).toString("base64url");
    return `https://app.pluralsight.com/video/delivery/api/v1/manifests/header.${body}.signature.m3u8`;
  };
  const R = globalThis.VocalmReaders;
  assert.equal(R.manifestAllowed(address(id), null, href), true);
  assert.equal(R.manifestAllowed(address(other), null, href), false);
  assert.equal(
    R.manifestAllowed(address(id, "hls/audio.m3u8"), null, href),
    false,
  );
  assert.equal(
    R.manifestAllowed(
      address(id).replace("app.pluralsight.com", "example.org"),
      null,
      href,
    ),
    false,
  );
  assert.equal(
    R.manifestAllowed(
      "https://app.pluralsight.com/video/delivery/api/v1/manifests/bad.m3u8",
      null,
      href,
    ),
    false,
  );
  const doc = {
    querySelectorAll: () => [
      { href, getAttribute: (k) => (k === "aria-current" ? "page" : null) },
    ],
  };
  const player = `https://app.pluralsight.com/ilx/video-courses/${id}/player`;
  assert.equal(R.manifestAllowed(address(id), null, player, doc), true);
  assert.equal(
    R.manifestAllowed(address(id), null, player, {
      querySelectorAll: () => [],
    }),
    false,
  );
});

test("Medbridge absolute VTT timeline preserves repeats and rejects out-of-course timestamps", async () => {
  const playlist =
    "#EXTM3U\n#EXTINF:4,\na.vtt\n#EXTINF:4,\nb.vtt\n#EXT-X-ENDLIST";
  const first =
    "WEBVTT\nX-TIMESTAMP-MAP=LOCAL:00:00.000,MPEGTS:900000\n\n00:01.000 --> 00:03.000\nFirst.\n\n00:04.000 --> 00:06.000\nSecond.";
  const second =
    "WEBVTT\nX-TIMESTAMP-MAP=LOCAL:00:00.000,MPEGTS:1260000\n\n00:04.000 --> 00:06.000\nSecond.\n\n00:07.000 --> 00:08.000\nFirst.";
  const load = async (url) => (url.endsWith("a.vtt") ? first : second);
  const result = await F.hls(
    playlist,
    "https://cdn.test/subs.m3u8",
    load,
    "en",
    { timing: "media", duration: 8 },
  );
  assert.deepEqual(
    result.cues.map((c) => [c.start, c.end, c.text]),
    [
      [1, 3, "First."],
      [4, 6, "Second."],
      [7, 8, "First."],
    ],
  );
  await assert.rejects(
    F.hls(playlist, "https://cdn.test/subs.m3u8", load, "en", {
      timing: "media",
    }),
    /duration is required/,
  );
  await assert.rejects(
    F.hls(playlist, "https://cdn.test/subs.m3u8", load, "en", {
      timing: "media",
      duration: 4,
    }),
    /Ambiguous HLS/,
  );
});

test("Facebook reads only data descriptors from one owned video, never accessors", () => {
  let getterCalls = 0;
  const item = {
    videoFBID: "123456789012345",
    sideLoadCaptionsUrl: "https://scontent.test.fbcdn.net/current.vtt",
  };
  Object.defineProperty(item, "danger", {
    enumerable: true,
    get() {
      getterCalls++;
      throw Error("getter");
    },
  });
  const video = {
    __reactProps$test: { video: item },
    querySelectorAll: () => [],
    parentElement: null,
  };
  const href = "https://www.facebook.com/watch/?v=123456789012345";
  assert.equal(R.sourceCaptions(video, href)[0].url, item.sideLoadCaptionsUrl);
  assert.equal(getterCalls, 0);
  video.__reactProps$test.other = {
    videoFBID: "999999999999999",
    sideLoadCaptionsUrl: item.sideLoadCaptionsUrl,
  };
  assert.deepEqual(R.sourceCaptions(video, href), []);
  assert.equal(getterCalls, 0);
  const cyclic = {};
  cyclic.self = cyclic;
  assert.equal(R.dataObjects(cyclic, 3).length, 1);
});

test("Twitter captions require an exact poster media ID and official media host", () => {
  const video = {
    poster: "https://pbs.twimg.com/amplify_video_thumb/12345/img/sample.jpg",
  };
  const href = "https://x.com/user/status/999";
  const url = "https://video.twimg.com/amplify_video/12345/pl/master.m3u8";
  const row = {
    url: "https://x.com/i/api/graphql/hash/TweetDetail",
    text: JSON.stringify({
      video_info: {
        variants: [{ content_type: "application/x-mpegURL", url }],
      },
    }),
  };
  assert.equal(R.observedTracks(row, video, href)[0].url, url);
  assert.equal(R.manifestAllowed(url, video, href), true);
  assert.equal(
    R.manifestAllowed(url.replace("/12345/", "/67890/"), video, href),
    false,
  );
  assert.equal(
    R.manifestAllowed(
      url.replace("video.twimg.com", "video.twimg.com.evil.test"),
      video,
      href,
    ),
    false,
  );
  assert.deepEqual(
    R.observedTracks(
      { ...row, url: "https://evil.test/i/api/graphql/hash/TweetDetail" },
      video,
      href,
    ),
    [],
  );
});

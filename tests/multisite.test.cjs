const test = require("node:test");
const assert = require("node:assert/strict");
require("../extension/lib/sites.js");
require("../extension/lib/captions.js");
const M = require("../extension/lib/media.js");
const F = require("../extension/lib/subtitle-formats.js");

test("registry routes domains, wildcard roots and embeds without suffix confusion", () => {
  assert.equal(globalThis.VeloaSites.length, 159);
  assert.ok(
    M.rules("https://www.coursera.org/learn/science/lecture/one").some(
      (r) => r.site === "coursera",
    ),
  );
  assert.ok(
    M.rules("https://fast.wistia.net/embed/iframe/abc").some(
      (r) => r.family === "wistia",
    ),
  );
  assert.equal(
    M.matches("*://*.youtube.com/*", "https://youtube.com/watch?v=abc"),
    true,
  );
  for (const url of [
    "https://www.youtube.com.evil.test/watch",
    "https://youtube.com@evil.test/watch",
    "https://evil.test/?next=https://youtube.com/watch",
  ])
    assert.equal(M.matches("*://*.youtube.com/*", url), false);
  assert.equal(
    M.youtubeId("https://www.youtube-nocookie.com/embed/3BndvjrGwyE"),
    "3BndvjrGwyE",
  );
  assert.equal(
    M.youtubeId("https://www.youtube.com/shorts/3BndvjrGwyE"),
    "3BndvjrGwyE",
  );
  assert.equal(
    M.youtubeId("https://youtube.com.evil.test/watch?v=3BndvjrGwyE"),
    null,
  );
  assert.equal(M.language("en_US"), "en-US");
  assert.equal(M.language("zh-Hans"), "zh");
  assert.equal(M.language("unknown"), "auto");
  assert.ok(
    M.rules("https://www.coindesk.com/video/current-clip").some(
      (r) => r.family === "coindesk_jwplayer",
    ),
  );
  assert.equal(
    M.rules("https://coindesk.com.evil.test/video/current-clip").length,
    0,
  );
});
test("VTT/SRT preserve IDs, settings, multiline and entities without markup", () => {
  const rows = F.parse(
    "WEBVTT\n\nNOTE ignored\n\nintro\n00:01.000 --> 00:03.500 align:start\n<v Alice>Hello &amp; world</v>\nSecond line\n\n2\n00:00:04,000 --> 00:00:05,000\nBye",
  );
  assert.deepEqual(rows, [
    { start: 1, end: 3.5, text: "Hello & world\nSecond line" },
    { start: 4, end: 5, text: "Bye" },
  ]);
  assert.throws(() => F.parse("WEBVTT\n\n00:62.000 --> 01:04.000\nBad"));
  assert.throws(() => F.parse("WEBVTT\n\n00:01.000 --> 00:00.000\nBad"));
  assert.throws(() => F.parse("x".repeat(F.MAX_BYTES + 1)));
  assert.throws(() => F.parse("WEBVTT\n\nNOTE no cues"));
});
test("explicit JSON schemas do not guess timestamp units", () => {
  assert.deepEqual(
    F.json({ body: [{ from: 1.2, to: 2.4, content: "Bili" }] }),
    [{ start: 1.2, end: 2.4, text: "Bili" }],
  );
  assert.deepEqual(
    F.json({
      hash: { lines: [{ start: 1, end: 3, text: ["Wistia", "line"] }] },
    }),
    [{ start: 1, end: 3, text: "Wistia\nline" }],
  );
  assert.equal(
    F.json({
      events: [
        { tStartMs: 1000, dDurationMs: 2000, segs: [{ utf8: "YouTube" }] },
      ],
    })[0].start,
    1,
  );
  assert.throws(() => F.json({ captions: [{ text: "No times" }] }));
  assert.throws(() => F.normalize([{ start: 0, end: 1000, text: "Too long" }]));
});
test("HLS renditions retain signed relative URLs and default language", async () => {
  const master =
    '#EXTM3U\n#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="cc",LANGUAGE="en",NAME="English, original",DEFAULT=YES,URI="sub/en.m3u8?sig=x"\n#EXT-X-STREAM-INF:BANDWIDTH=1000,SUBTITLES="cc"\nvideo.m3u8';
  const files = {
    "https://cdn.test/sub/en.m3u8?sig=x":
      "#EXTM3U\n#EXTINF:5,\na.vtt\n#EXTINF:5,\nb.vtt\n#EXT-X-ENDLIST",
    "https://cdn.test/sub/a.vtt":
      "WEBVTT\nX-TIMESTAMP-MAP=LOCAL:00:00.000,MPEGTS:900000\n\n00:01.000 --> 00:03.000\nOne",
    "https://cdn.test/sub/b.vtt":
      "WEBVTT\nX-TIMESTAMP-MAP=LOCAL:00:00.000,MPEGTS:1350000\n\n00:01.000 --> 00:03.000\nTwo",
  };
  const result = await F.hls(
    master,
    "https://cdn.test/master.m3u8",
    async (url) => {
      assert.ok(files[url], url);
      return files[url];
    },
  );
  assert.equal(result.language, "en");
  assert.deepEqual(
    result.cues.map((c) => c.start),
    [1, 6],
  );
});
test("HLS discontinuities and PTS wrap map to continuous video time", async () => {
  for (const discontinuity of [false, true]) {
    const list =
      "#EXTM3U\n#EXTINF:5,\na.vtt\n" +
      (discontinuity ? "#EXT-X-DISCONTINUITY\n" : "") +
      "#EXTINF:5,\nb.vtt\n#EXT-X-ENDLIST";
    const base = 2 ** 33 - 270000;
    const result = await F.hls(
      list,
      "https://cdn.test/list.m3u8",
      async (url) =>
        "WEBVTT\nX-TIMESTAMP-MAP=LOCAL:00:00.000,MPEGTS:" +
        (url.endsWith("a.vtt") ? base : discontinuity ? 0 : 180000) +
        "\n\n00:01.000 --> 00:02.000\n" +
        url,
    );
    assert.ok(Math.abs(result.cues[1].start - 6) < 1e-6);
  }
});
test("HLS never treats audio/video segments, live windows or encrypted streams as subtitles", async () => {
  assert.throws(() =>
    F.playlist(
      '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key"',
      "https://cdn.test/m",
    ),
  );
  assert.throws(() =>
    F.playlist('#EXTM3U\n#EXT-X-MAP:URI="init.mp4"', "https://cdn.test/m"),
  );
  assert.throws(() =>
    F.playlist(
      "#EXTM3U\n#EXTINF:2,\nhttp://insecure.test/a",
      "https://cdn.test/m",
    ),
  );
  await assert.rejects(
    F.hls("#EXTM3U\n#EXTINF:2,\na.vtt", "https://cdn.test/m", async () => ""),
    /complete VOD/,
  );
  await assert.rejects(
    F.hls(
      "#EXTM3U\n#EXTINF:2,\na.ts\n#EXT-X-ENDLIST",
      "https://cdn.test/m",
      async () => "binary",
    ),
    /not WebVTT/,
  );
});
test("stream byte limit applies to chunked bodies without Content-Length", async () => {
  const response = new Response(
    new ReadableStream({
      start(c) {
        c.enqueue(new Uint8Array(F.MAX_BYTES));
        c.enqueue(new Uint8Array(1));
        c.close();
      },
    }),
  );
  await assert.rejects(F.bounded(response), /exceeds/);
  assert.equal(await F.bounded(new Response("WEBVTT")), "WEBVTT");
});

const test = require("node:test");
const assert = require("node:assert/strict");
require("../extension/lib/sites.js");
require("../extension/lib/captions.js");
const M = require("../extension/lib/media.js");
const F = require("../extension/lib/subtitle-formats.js");
const P = require("../extension/lib/platform-captions.js");
const R = require("../extension/lib/platform-readers.js");

test("international Bilibili distinguishes video, season and selected episode", () => {
  const href = "https://www.bilibili.tv/en/play/37976";
  const doc = {
    querySelectorAll: () => [{ getAttribute: () => "/en/play/37976/10344255" }],
  };
  assert.deepEqual(M.biliInternationalRoute(href, doc), {
    kind: "episode_id",
    id: "10344255",
    season: "37976",
  });
  assert.equal(M.biliInternationalRoute(href).id, null);
  assert.equal(
    M.biliInternationalRoute(href + "/10344397", doc).id,
    "10344397",
  );
  doc.querySelectorAll = () => [{ getAttribute: () => "/en/play/999/123" }];
  assert.equal(M.biliInternationalRoute(href, doc).id, null);
  assert.deepEqual(
    M.biliInternationalRoute("https://www.bilibili.tv/vi/video/204123"),
    { kind: "aid", id: "204123" },
  );
  assert.equal(
    M.biliInternationalRoute("https://bilibili.tv.evil.test/en/video/123"),
    null,
  );
  assert.ok(M.rules(href).some((r) => r.family === "biliintl"));
});

test("international subtitles require current episode, successful response and official caption host", () => {
  const href = "https://www.bilibili.tv/en/play/37976/10344255";
  const data = {
    code: 0,
    data: {
      video_subtitle: [
        {
          lang_key: "en",
          srt: { url: "https://s.bstarstatic.com/ogv/subtitle/a.json" },
          ass: null,
        },
        {
          lang_key: "vi",
          srt: { url: "https://bstarstatic.com.evil.test/a.json" },
        },
      ],
    },
  };
  const row = {
    url: "https://api.bilibili.tv/intl/gateway/web/v2/subtitle?episode_id=10344255",
    text: JSON.stringify(data),
  };
  assert.equal(R.observedTracks(row, {}, href).length, 1);
  assert.equal(
    R.observedTracks(row, {}, href.replace("10344255", "10344397")).length,
    0,
  );
  assert.deepEqual(R.internationalTracks({ ...data, code: -403 }, href), []);
  assert.equal(
    R.observedKind(
      row.url.replace("api.bilibili.tv", "api.bilibili.tv.evil.test"),
      href,
    ),
    null,
  );
});

test("international direct discovery supplies required locale and rejects episode changes", async () => {
  const href = "https://www.bilibili.tv/en/play/37976",
    doc = {
      querySelectorAll: () => [
        { getAttribute: () => "/en/play/37976/10344255" },
      ],
    };
  let called = 0;
  const options = {
    href,
    video: {},
    win: {},
    doc,
    check() {},
    read: async (url, session) => {
      called++;
      const u = new URL(url);
      assert.equal(u.searchParams.get("s_locale"), "en_US");
      assert.equal(u.searchParams.get("episode_id"), "10344255");
      assert.equal(session, true);
      return JSON.stringify({
        code: 0,
        data: {
          video_subtitle: [
            {
              lang_key: "en",
              srt: { url: "https://s.bstarstatic.com/a.json" },
            },
          ],
        },
      });
    },
  };
  const rows = [];
  for await (const row of R.discover(options)) rows.push(row);
  assert.equal(rows.length, 1);
  assert.equal(called, 1);
  const read = options.read;
  options.read = async (...args) => {
    const data = await read(...args);
    doc.querySelectorAll = () => [];
    return data;
  };
  await assert.rejects(async () => {
    for await (const row of R.discover(options)) {
    }
  }, /episode changed/);
});

test("ASS dialogue retains commas, speech and timing, ignores drawing and comments", () => {
  const ass = String.raw`[Script Info]
Title: Labelled fixture
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.20,0:00:03.50,Default,,0,0,0,,{\i1}Hello, world.\NNext line.
Comment: 0,0:00:01.20,0:00:03.50,Default,,0,0,0,,Not speech
Dialogue: 0,0:00:04.00,0:00:05.00,Default,,0,0,0,,{\p1}m 0 0 l 10 10{\p0}Speech`;
  assert.deepEqual(F.parse(ass), [
    { start: 1.2, end: 3.5, text: "Hello, world.\nNext line." },
    { start: 4, end: 5, text: "Speech" },
  ]);
  assert.throws(() => F.parse("[Events]\nDialogue: 0,foo"), /format/);
});

test("Douyin identity remains precise across feed/modal and rejects stale owners", () => {
  const id = "6961737553342991651",
    other = "6963263655114722595";
  const video = {
    closest: () => ({
      getAttribute: (k) => (k === "data-aweme-id" ? id : null),
    }),
  };
  assert.equal(M.douyinId("https://www.douyin.com/", video), id);
  assert.equal(
    M.douyinId(`https://www.douyin.com/?modal_id=${other}`, video),
    null,
  );
  assert.equal(M.douyinId(`https://www.douyin.com/video/${id}`, video), id);
  assert.equal(
    M.douyinId(`https://douyin.com.evil.test/video/${id}`, video),
    null,
  );
});

test("Douyin captions are selected from exact aweme without unsafe URLs or timing guesses", () => {
  const id = "6961737553342991651",
    href = `https://www.douyin.com/video/${id}`;
  const owner = {
    aweme_id: id,
    video: {
      cla_info: {
        caption_infos: [
          { url: "https://media.test/current.vtt", lang: "zh" },
          { url: "http://127.0.0.1/private.vtt", lang: "zh" },
        ],
      },
    },
    interaction_stickers: [
      {
        auto_video_caption_info: {
          auto_captions: [
            {
              language: "zh",
              url: { url_list: ["https://media.test/current.json"] },
            },
          ],
        },
      },
    ],
  };
  const data = {
    aweme_list: [{ ...owner, aweme_id: "6963263655114722595" }, owner],
  };
  const tracks = R.douyinTracks(data, id, href);
  assert.equal(tracks.length, 2);
  assert.equal(tracks[1].format, "douyin-utterances");
  assert.deepEqual(R.douyinTracks(data, "9999999999999", href), []);
  assert.deepEqual(
    P.parse(
      JSON.stringify({
        utterances: [{ start_time: 1250, end_time: 3600, text: "Caption." }],
      }),
      "douyin-utterances",
    ),
    [{ start: 1.25, end: 3.6, text: "Caption." }],
  );
  assert.throws(() =>
    P.parse(
      '{"utterances":[{"start_time":4000,"end_time":1000,"text":"Bad"}]}',
      "douyin-utterances",
    ),
  );
});

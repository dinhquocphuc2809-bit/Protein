const test = require("node:test");
const assert = require("node:assert/strict");
require("../extension/lib/captions.js");
require("../extension/lib/subtitle-formats.js");
const M = require("../extension/lib/media.js");
require("../extension/lib/sites.js");
const B = require("../extension/lib/bilibili.js");
const url = "https://www.bilibili.com/video/BV1WqYV6cEwq/";
const state = {
  aid: 123,
  cid: 456,
  bvid: "BV1WqYV6cEwq",
  videoData: {
    aid: 123,
    cid: 456,
    bvid: "BV1WqYV6cEwq",
    pages: [
      { page: 1, cid: 456 },
      { page: 2, cid: 789 },
    ],
  },
};

test("Bilibili identity distinguishes parts, rejects hostile hosts and stale state", () => {
  assert.equal(
    M.biliRoute(url.replace("/video/", "/en/video/")).key,
    M.biliRoute(url).key,
  );
  assert.equal(M.rules(url.replace("/video/", "/en/video/"))[0].site, "bili");
  assert.equal(B.resolve(M.biliRoute(url), state).cid, "456");
  assert.equal(B.resolve(M.biliRoute(url + "?p=2"), state).cid, "789");
  assert.equal(B.resolve(M.biliRoute(url + "?p=3"), state), null);
  assert.equal(
    B.resolve(M.biliRoute(url.replace("BV1WqYV6cEwq", "BVother")), state),
    null,
  );
  assert.equal(
    M.biliRoute(url.replace("bilibili.com", "bilibili.com.evil.test")),
    null,
  );
  assert.equal(M.biliRoute(url + "?p=-1"), null);
  assert.equal(M.biliRoute(url + "?p=1.5"), null);
  assert.notEqual(M.biliRoute(url).key, M.biliRoute(url + "?p=2").key);
  assert.equal(
    B.resolve(
      M.biliRoute("https://player.bilibili.com/player.html?aid=123&cid=789"),
      state,
    ).cid,
    "789",
  );
});

test("Bilibili metadata binds CID and normalizes AI language prefixes", () => {
  const info = B.resolve(M.biliRoute(url), state);
  assert.equal(
    B.matches(
      B.owner(
        { data: { cid: 789 } },
        "https://api.bilibili.com/x/player/v2?aid=123&cid=456",
      ),
      info,
    ),
    false,
  );
  assert.equal(
    B.matches(
      B.owner(
        { data: { cid: 456 } },
        "https://api.bilibili.com/x/player/v2?aid=123&cid=456",
      ),
      info,
    ),
    true,
  );
  assert.equal(B.matches({ cid: "456", bvid: "BVother" }, info), false);
  assert.equal(B.language("ai-zh"), "zh");
  assert.equal(B.language("ai-en"), "en");
  assert.equal(
    B.tracks([{ subtitle_url: "javascript:alert(1)" }], url).length,
    0,
  );
  assert.equal(B.tracks([{ lan: "zh" }], url).length, 0);
  assert.equal(
    B.tracks(
      [{ subtitle_url: "//i.hdslb.com/bfs/subtitle/test.json", lan: "ai-en" }],
      url,
    )[0].language,
    "en",
  );
});

test("Bilibili missed response is recovered with authenticated primary/legacy requests", async () => {
  globalThis.location = { href: url };
  globalThis.window = { __INITIAL_STATE__: state };
  const requested = [];
  const result = await B.discover({
    observed: () => [],
    check: () => {},
    read: async (address, session) => {
      requested.push({ address, session });
      if (address.includes("/wbi/")) return JSON.stringify({ code: -403 });
      return JSON.stringify({
        code: 0,
        data: {
          cid: 456,
          subtitle: {
            subtitles: [
              {
                subtitle_url: "//i.hdslb.com/bfs/subtitle/a.json",
                lan: "ai-zh",
              },
            ],
          },
        },
      });
    },
  });
  assert.equal(result.tracks[0].language, "zh");
  assert.equal(requested.length, 2);
  assert.ok(
    requested.every(
      (r) => r.session && new URL(r.address).searchParams.get("cid") === "456",
    ),
  );
});

test("Bilibili reuses current metadata but does not reuse another part", async () => {
  globalThis.location = { href: url + "?p=2" };
  globalThis.window = { __INITIAL_STATE__: state };
  let requests = 0;
  const result = await B.discover({
    check: () => {},
    observed: () => [
      {
        owner: { cid: "456" },
        tracks: [{ url: "https://i.hdslb.com/wrong.json" }],
      },
      {
        owner: { cid: "789" },
        tracks: [{ url: "https://i.hdslb.com/right.json" }],
      },
    ],
    read: async () => {
      requests++;
      throw new Error("Should use captured metadata");
    },
  });
  assert.equal(requests, 0);
  assert.deepEqual(result.tracks, [{ url: "https://i.hdslb.com/right.json" }]);
});

test("Bilibili empty results remain uncertain and navigation aborts acquisition", async () => {
  globalThis.location = { href: url };
  globalThis.window = { __INITIAL_STATE__: state };
  const empty = await B.discover({
    check: () => {},
    observed: () => [],
    read: async () =>
      JSON.stringify({ code: 0, data: { subtitle: { subtitles: [] } } }),
  });
  assert.equal(empty.diagnostic, "bili_empty");
  await assert.rejects(
    B.discover({
      check: () => {
        throw new Error("Video changed");
      },
      observed: () => [],
      read: async () => "{}",
    }),
    /Video changed/,
  );
});

test("Bilibili resolves missing page state using the current view, never stale fallback lists", async () => {
  globalThis.location = { href: url + "?p=2" };
  globalThis.window = {
    __INITIAL_STATE__: {
      bvid: "BVwrong",
      videoData: {
        aid: 1,
        cid: 2,
        subtitle: { list: [{ subtitle_url: "https://i.hdslb.com/wrong" }] },
      },
    },
  };
  const calls = [];
  const result = await B.discover({
    check: () => {},
    observed: () => [],
    read: async (address) => {
      calls.push(address);
      if (address.includes("/view?"))
        return JSON.stringify({ code: 0, data: state.videoData });
      return JSON.stringify({
        code: 0,
        data: {
          cid: 789,
          subtitle: {
            subtitles: [
              { subtitle_url: "https://i.hdslb.com/right", lan: "en" },
            ],
          },
        },
      });
    },
  });
  assert.equal(result.tracks[0].url, "https://i.hdslb.com/right");
  assert.ok(calls[1].includes("cid=789"));
});

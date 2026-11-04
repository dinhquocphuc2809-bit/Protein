const test = require("node:test");
const assert = require("node:assert/strict");
require("../extension/lib/core.js");
const { Mixer, stretch } = require("../extension/lib/audio.js");
const { WindowQueue } = require("../extension/lib/window-queue.js");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rows = (count = 12) =>
  Array.from({ length: count }, (_, i) => ({
    id: i,
    start: i * 2,
    end: i * 2 + 2,
    text: `Source ${i}.`,
    translated: `Speech ${i}.`,
  }));
class Video extends EventTarget {
  currentTime = 0;
  playbackRate = 1;
  paused = true;
  volume = 0.8;
  muted = false;
  seeking = false;
  async play() {
    this.paused = false;
    this.dispatchEvent(new Event("play"));
  }
  pause() {
    this.paused = true;
    this.dispatchEvent(new Event("pause"));
  }
}
class Buffer {
  constructor(length, rate) {
    this.length = length;
    this.sampleRate = rate;
    this.duration = length / rate;
    this.numberOfChannels = 1;
    this.samples = new Float32Array(length).fill(0.3);
  }
  getChannelData() {
    return this.samples;
  }
  copyToChannel(value) {
    this.samples.set(value);
  }
}
class Context {
  currentTime = 0;
  state = "running";
  destination = {};
  sources = [];
  createGain() {
    return {
      connect() {},
      disconnect() {},
      gain: {
        value: 1,
        setValueAtTime() {},
        linearRampToValueAtTime() {},
        cancelScheduledValues() {},
        setTargetAtTime() {},
      },
    };
  }
  createBuffer(channels, length, rate) {
    return new Buffer(length, rate);
  }
  async decodeAudioData() {
    return new Buffer(2000, 1000);
  }
  createBufferSource() {
    const source = {
      context: this,
      connect() {},
      disconnect() {},
      start(time, offset = 0) {
        this.started = { time, offset };
      },
      stop(time) {
        this.stopped = time;
      },
    };
    this.sources.push(source);
    return source;
  }
  async resume() {}
  async close() {
    this.state = "closed";
  }
}
globalThis.AudioContext = Context;
test("advertisement events cannot seek, play or synthesize against content time", async () => {
  const { video, mixer, requests } = await fixture();
  let ad = false;
  mixer.isBlocked = () => ad;
  await mixer.prime();
  await video.play();
  await sleep(10);
  ad = true;
  video.currentTime = 90;
  video.dispatchEvent(new Event("seeking"));
  assert.equal(mixer.suspended, true);
  assert.equal(mixer.active, null);
  assert.equal(mixer.running, false);
  const count = requests.length,
    starts = mixer.context.sources.length;
  for (const name of [
    "play",
    "playing",
    "pause",
    "ended",
    "ratechange",
    "waiting",
  ])
    video.dispatchEvent(new Event(name));
  await mixer.tick();
  assert.equal(requests.length, count);
  assert.equal(mixer.context.sources.length, starts);
  video.currentTime = 4;
  ad = false;
  await mixer.tick();
  assert.equal(mixer.suspended, false);
  assert.equal(mixer.cursor, 2);
  assert.equal(mixer.running, true);
  assert.equal(mixer.cues.length, 12);
  await mixer.close();
});
test("video node replacement during an ad retains clips and detaches old events", async () => {
  const { video, mixer } = await fixture();
  await mixer.prime();
  let ad = true;
  mixer.isBlocked = () => ad;
  mixer.syncSuspension();
  const replacement = new Video();
  mixer.replaceVideo(replacement);
  assert.equal(mixer.clips.size, 1);
  video.currentTime = 20;
  video.dispatchEvent(new Event("seeking"));
  assert.equal(mixer.cursor, 0);
  replacement.currentTime = 6;
  ad = false;
  await mixer.tick();
  assert.equal(mixer.cursor, 3);
  assert.equal(mixer.running, false);
  await mixer.close();
});
async function fixture(send, requireTranslation = false) {
  const video = new Video(),
    requests = [];
  const mixer = new Mixer(
    video,
    async (msg) => {
      requests.push(msg);
      if (send) return send(msg);
      if (msg.type === "voiceIdentity") return "voice";
      if (msg.type === "cachedAudio") return { audio: btoa("fixture") };
    },
    () => {},
  );
  clearInterval(mixer.timer);
  await mixer.configure(rows(), "voice", "vi", requireTranslation);
  return { video, mixer, requests };
}
test("unity-speed speech has smooth zero endpoints without dropping samples", async () => {
  const input = new Float32Array(24000).fill(0.4),
    out = await stretch(input, 1, 24000);
  assert.equal(out.length, input.length);
  assert.equal(out[0], 0);
  assert.equal(out.at(-1), 0);
  assert.equal(out[500], input[500]);
  assert.ok(
    Math.max(
      ...out.slice(0, 200).map((x, i) => (i ? Math.abs(x - out[i - 1]) : 0)),
    ) < 0.005,
  );
});
test("startup primes one sentence, not the whole video or distant neighborhood", async () => {
  const { mixer, requests } = await fixture();
  try {
    await mixer.prime();
    assert.deepEqual([...mixer.clips.keys()], [0]);
    assert.equal(requests.filter((m) => m.type === "cachedAudio").length, 1);
  } finally {
    await mixer.close();
  }
});
test("ordinary delayed playback starts at audio zero, not late video offset", async () => {
  const { video, mixer } = await fixture();
  try {
    await mixer.prime();
    video.currentTime = 0.65;
    mixer.running = true;
    await mixer.tick();
    assert.equal(mixer.active.offset, 0);
    assert.equal(mixer.context.sources[0].started.offset, 0);
  } finally {
    await mixer.close();
  }
});
test("manual pause resumes at actual audio progress and stops with a fade", async () => {
  const { video, mixer } = await fixture();
  try {
    await mixer.prime();
    mixer.running = true;
    video.paused = false;
    await mixer.tick();
    mixer.context.currentTime = 0.4;
    const source = mixer.active.source;
    video.pause();
    assert.ok(source.stopped > 0.4);
    assert.equal(mixer.resumeOffset.seconds, 0.4);
    mixer.running = true;
    await mixer.tick();
    assert.equal(mixer.active.offset, 0.4);
  } finally {
    await mixer.close();
  }
});
test("explicit seek reanchors current work and rejects obsolete synthesis results", async () => {
  let resolve;
  const cancellations = [];
  const { video, mixer } = await fixture(async (msg) => {
    if (msg.type === "voiceIdentity") return "voice";
    if (msg.type === "cachedAudio") return null;
    if (msg.type === "synthesize") return new Promise((r) => (resolve = r));
    if (msg.type === "cancelAudio") {
      cancellations.push(msg.id);
      return true;
    }
    if (msg.type === "pollAudio")
      return { state: "done", audio: btoa("fixture") };
  });
  try {
    const prime = mixer.prime();
    while (!resolve) await sleep(1);
    video.currentTime = 16.5;
    video.dispatchEvent(new Event("seeking"));
    resolve({});
    await prime;
    assert.equal(mixer.cursor, 8);
    assert.ok(cancellations.length);
    assert.equal(mixer.clips.has(0), false);
  } finally {
    await mixer.close();
  }
});
test("translation-pending units never send original-language text to TTS", async () => {
  const { mixer, requests } = await fixture(undefined, true);
  try {
    mixer.cues.forEach((c) => delete c.translated);
    mixer.running = true;
    await mixer.tick();
    assert.equal(
      requests.filter(
        (r) => r.type === "cachedAudio" || r.type === "synthesize",
      ).length,
      0,
    );
    assert.equal(mixer.hold, "buffering");
  } finally {
    await mixer.close();
  }
});

test("a late speech cursor still requests its own translation before lookahead", async () => {
  const { video, mixer } = await fixture(undefined, true);
  const requested = [];
  try {
    mixer.cues.forEach((c) => delete c.translated);
    mixer.onNeed = (position) => requested.push(position);
    video.currentTime = 2.4;
    mixer.running = true;
    await mixer.tick();
    assert.equal(requested[0], 0);
    assert.equal(mixer.hold, "buffering");
  } finally {
    await mixer.close();
  }
});
test("video holds only after 750ms allowance; current audio tail is never cut", async () => {
  const { video, mixer } = await fixture();
  try {
    await mixer.prime();
    mixer.running = true;
    video.paused = false;
    await mixer.tick();
    const source = mixer.active.source;
    video.currentTime = 2.5;
    await mixer.tick();
    assert.equal(video.paused, false);
    video.currentTime = 2.76;
    await mixer.tick();
    assert.equal(mixer.hold, "finishing");
    assert.equal(source.stopped, undefined);
    video.dispatchEvent(new Event("ended"));
    assert.equal(source.stopped, undefined);
  } finally {
    await mixer.close();
  }
});
test("speech finishes completely before next unit, even if playhead passed a short boundary", async () => {
  const { video, mixer } = await fixture();
  try {
    await mixer.prime();
    mixer.running = true;
    await mixer.tick();
    const source = mixer.active.source;
    video.currentTime = 2.4;
    source.onended();
    await sleep(30);
    assert.equal(mixer.cursor, 1);
    if (mixer.active) assert.equal(mixer.active.offset, 0);
  } finally {
    await mixer.close();
  }
});
test("pause and voice changes keep synthesis neighborhood and decoded memory bounded", async () => {
  const { video, mixer } = await fixture();
  try {
    await mixer.prime();
    mixer.running = true;
    await mixer.tick();
    await sleep(30);
    assert.ok(mixer.clips.size <= 4);
    video.pause();
    assert.equal(mixer.pending.size, 0);
    await mixer.configure(rows(), "other", "vi");
    assert.equal(mixer.clips.size, 0);
    assert.equal(mixer.fitted.size, 0);
    for (let i = 0; i < 50; i++) mixer.clips.set(i, new Buffer(200000, 24000));
    mixer.evict();
    assert.ok(
      [...mixer.clips.values()].reduce((s, b) => s + b.length * 4, 0) <=
        12 * 1024 ** 2,
    );
  } finally {
    await mixer.close();
  }
});
test("window queue translates near playback only; seek preempts obsolete window", async () => {
  const cues = rows(100).map((c) => ({ ...c, translated: undefined })),
    submitted = [],
    cancelled = [];
  let resolveFirst;
  const queue = new WindowQueue(
    cues,
    "a".repeat(32),
    async (msg) => {
      if (msg.type === "windowJob") {
        submitted.push(msg.payload);
        const id = String(submitted.length).padStart(32, "0");
        if (submitted.length === 1)
          return new Promise(
            (resolve) => (resolveFirst = () => resolve({ id })),
          );
        return { id };
      }
      if (msg.type === "cancelJob") {
        cancelled.push(msg.id);
        return {};
      }
      const position = submitted[Number(msg.id) - 1].position,
        index = position / 2;
      return {
        state: "done",
        result: { cues: [{ ...cues[index], translated: "Translated." }] },
      };
    },
    () => {},
    (e) => {
      throw e;
    },
  );
  try {
    queue.request(0, false);
    await sleep(1);
    queue.request(100, false);
    resolveFirst();
    await sleep(30);
    assert.deepEqual(
      submitted.map((v) => v.position),
      [0, 100],
    );
    assert.equal(cues[0].translated, undefined);
    assert.equal(cues[50].translated, "Translated.");
    assert.ok(cancelled.length);
  } finally {
    queue.close();
  }
});
test("lookahead window is not cancelled every tick just because it starts ahead of playhead", async () => {
  const cues = rows(100);
  for (let i = 3; i < cues.length; i++) delete cues[i].translated;
  let resolve;
  const sent = [];
  const queue = new WindowQueue(
    cues,
    "a".repeat(32),
    async (msg) => {
      sent.push(msg);
      if (msg.type === "windowJob") return new Promise((r) => (resolve = r));
      return {};
    },
    () => {},
    () => {},
  );
  queue.request(0, true);
  await sleep(1);
  const generation = queue.generation;
  for (let i = 0; i < 20; i++) queue.request(0, true);
  assert.equal(queue.generation, generation);
  assert.equal(sent.filter((m) => m.type === "windowJob").length, 1);
  queue.close();
  resolve({ id: "b".repeat(32) });
  await sleep(5);
  assert.ok(sent.some((m) => m.type === "cancelJob"));
});

test("seek interrupts slow initial submission without waiting for its network response", async () => {
  let submitted, release;
  const { video, mixer } = await fixture(async (msg) => {
    if (msg.type === "voiceIdentity") return "voice";
    if (msg.type === "cachedAudio") return null;
    if (msg.type === "synthesize") {
      submitted = true;
      return new Promise((resolve) => {
        release = resolve;
      });
    }
    return {};
  });
  try {
    const preparation = mixer.prime();
    const interrupted = assert.rejects(preparation, { name: "AbortError" });
    while (!submitted) await sleep(1);
    video.currentTime = 8;
    video.dispatchEvent(new Event("seeking"));
    await Promise.race([
      interrupted,
      sleep(250).then(() => {
        throw new Error("Seek remained blocked");
      }),
    ]);
    assert.equal(mixer.cursor, 4);
    assert.equal(mixer.clips.size, 0);
  } finally {
    release?.({});
    await mixer.close();
  }
});

test("native pause then ended event order preserves the last audible tail", async () => {
  const { video, mixer } = await fixture();
  try {
    await mixer.prime();
    mixer.running = true;
    await mixer.tick();
    const source = mixer.active.source;
    video.ended = true;
    video.pause();
    video.dispatchEvent(new Event("ended"));
    assert.equal(source.stopped, undefined);
    assert.equal(mixer.running, false);
    source.onended();
    assert.equal(mixer.active, null);
  } finally {
    await mixer.close();
  }
});

test("stall and playback-rate changes preserve actual spoken progress", async () => {
  const { video, mixer } = await fixture();
  try {
    await mixer.prime();
    mixer.running = true;
    await mixer.tick();
    mixer.context.currentTime = 0.4;
    video.dispatchEvent(new Event("waiting"));
    assert.equal(mixer.active, null);
    assert.equal(mixer.resumeOffset.seconds, 0.4);
    await mixer.tick();
    assert.equal(mixer.active, null);
    video.dispatchEvent(new Event("playing"));
    await sleep(40);
    assert.equal(mixer.active.offset, 0.4);
    video.playbackRate = 1.5;
    video.dispatchEvent(new Event("ratechange"));
    await mixer.tick();
    assert.ok(Math.abs(mixer.active.offset * mixer.active.speed - 0.4) < 0.001);
    assert.ok(mixer.active.source.buffer.duration < 2);
  } finally {
    await mixer.close();
  }
});

test("changing voice during a buffering hold resumes with cached translations", async () => {
  const { video, mixer, requests } = await fixture(undefined, true);
  try {
    mixer.running = true;
    video.paused = false;
    mixer.pauseFor("buffering");
    const translated = mixer.cues.map((c) => c.translated);
    await mixer.configure(mixer.cues, "second-voice", "vi", true);
    assert.equal(mixer.running, true);
    await mixer.prime();
    await mixer.tick();
    assert.equal(video.paused, false);
    assert.deepEqual(
      mixer.cues.map((c) => c.translated),
      translated,
    );
    assert.equal(
      requests.some((m) => m.type === "windowJob" || m.type === "job"),
      false,
    );
  } finally {
    await mixer.close();
  }
});

test("seek during voice lookup keeps the selected voice and new cursor", async () => {
  const { video, mixer } = await fixture();
  let resolve;
  try {
    mixer.send = async () =>
      new Promise((r) => {
        resolve = r;
      });
    const configuring = mixer.configure(rows(), "second", "vi");
    video.currentTime = 10;
    video.dispatchEvent(new Event("seeking"));
    resolve("second-identity");
    await configuring;
    assert.equal(mixer.voiceHash, "second-identity");
    assert.equal(mixer.cursor, 5);
  } finally {
    await mixer.close();
  }
});

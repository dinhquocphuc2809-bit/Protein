(function (root) {
  "use strict";
  const A = root.Auvirel;
  async function stretch(samples, speed, rate, cancelled = () => false) {
    if (!Number.isFinite(speed) || speed < 0.5 || speed > 2)
      throw new Error("Unsupported speech stretch ratio.");
    if (Math.abs(speed - 1) < 0.015) return edgeFade(samples.slice(), rate);
    const frame = Math.round(rate * 0.04),
      hop = Math.floor(frame / 2),
      search = Math.round(rate * 0.008);
    const length = Math.max(1, Math.round(samples.length / speed));
    const output = new Float32Array(length + frame),
      weights = new Float32Array(length + frame);
    const window = Float32Array.from(
      { length: frame },
      (_, i) => 0.5 - 0.5 * Math.cos((2 * Math.PI * (i + 0.5)) / frame),
    );
    let previous = 0;
    for (let target = 0, n = 0; target < length; target += hop, n++) {
      if (n % 16 === 0) {
        if (cancelled()) throw new DOMException("Cancelled", "AbortError");
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
      let source = Math.min(
        Math.max(0, samples.length - frame),
        Math.round(target * speed),
      );
      if (target > 0 && source + frame < samples.length) {
        let best = -Infinity,
          bestSource = source;
        const low = Math.max(0, source - search),
          high = Math.min(samples.length - frame, source + search);
        for (let candidate = low; candidate <= high; candidate += 4) {
          let cross = 0,
            energy = 1e-12,
            refEnergy = 1e-12;
          for (let k = 0; k < hop; k += 4) {
            const a = samples[previous + hop + k] || 0,
              b = samples[candidate + k];
            cross += a * b;
            energy += b * b;
            refEnergy += a * a;
          }
          const score =
            cross / Math.sqrt(energy * refEnergy) -
            Math.abs(candidate - source) * 1e-6;
          if (score > best) {
            best = score;
            bestSource = candidate;
          }
        }
        source = bestSource;
      }
      for (let k = 0; k < frame && target + k < output.length; k++) {
        output[target + k] += (samples[source + k] || 0) * window[k];
        weights[target + k] += window[k];
      }
      previous = source;
    }
    const result = output.subarray(0, length);
    for (let i = 0; i < length; i++)
      result[i] = Math.max(
        -1,
        Math.min(1, result[i] / Math.max(1e-6, weights[i])),
      );
    return edgeFade(result, rate);
  }

  function edgeFade(samples, rate) {
    const fade = Math.min(
      Math.round(rate * 0.008),
      Math.floor(samples.length / 2),
    );
    for (let i = 0; i < fade; i++) {
      const gain = 0.5 - 0.5 * Math.cos((Math.PI * i) / Math.max(1, fade - 1));
      samples[i] *= gain;
      samples[samples.length - i - 1] *= gain;
    }
    return samples;
  }

  class Mixer {
    constructor(video, send, onState, onNeed = () => {}, onPause = () => {}) {
      this.video = video;
      this.send = send;
      this.onState = onState;
      this.onNeed = onNeed;
      this.onPause = onPause;
      this.context = new AudioContext({ sampleRate: 24000 });
      this.gain = this.context.createGain();
      this.gain.connect(this.context.destination);
      this.musicGain = this.context.createGain();
      this.musicGain.gain.value = 0.12;
      this.musicGain.connect(this.context.destination);
      this.original = { volume: video.volume, muted: video.muted };
      this.epoch = 0;
      this.clips = new Map();
      this.fitted = new Map();
      this.pending = new Map();
      this.failed = new Map();
      this.active = null;
      this.running = false;
      this.hold = null;
      this.expectedPause = false;
      this.stalled = false;
      this.listeners = new AbortController();
      this.cursor = 0;
      this.resumeOffset = null;
      this.anchor = null;
      const listen = (event, fn) =>
        video.addEventListener(event, fn, { signal: this.listeners.signal });
      listen("seeking", () => this.reanchor());
      listen("ratechange", () => {
        this.captureOffset();
        this.invalidate();
        this.fitted.clear();
      });
      listen("play", () => {
        this.hold = null;
        this.running = true;
        this.context.resume().catch((e) => this.fail(e));
        this.startMusic();
        this.tick().catch((e) => this.fail(e));
      });
      listen("pause", () => {
        if (this.expectedPause) {
          this.expectedPause = false;
          return;
        }
        // Native media emits pause before ended. Let the final spoken word finish.
        if (this.video.ended) return;
        this.captureOffset();
        this.running = false;
        this.invalidate();
        this.stopMusic();
        this.onPause();
      });
      listen("waiting", () => {
        if (this.running && !this.hold) {
          this.stalled = true;
          this.captureOffset();
          this.stopAudio();
          this.stopMusic();
        }
      });
      listen("playing", () => {
        this.stalled = false;
        this.startMusic();
        this.tick().catch((e) => this.fail(e));
      });
      listen("ended", () => {
        this.running = false;
        this.stopMusic();
        this.onPause();
        for (const task of this.pending.values()) {
          task.abort = true;
          if (task.id)
            this.send({ type: "cancelAudio", id: task.id }).catch(() => {});
        }
        this.pending.clear();
      });
      this.timer = setInterval(
        () => this.tick().catch((e) => this.fail(e)),
        40,
      );
    }
    async configure(cues, voiceId, language, requireTranslation = false) {
      const configuration = (this.configuration =
        (this.configuration || 0) + 1);
      const continueHold = Boolean(this.hold) && this.running;
      this.invalidate();
      this.clips.clear();
      this.fitted.clear();
      this.failed.clear();
      this.voiceHash = null;
      this.cues = cues;
      this.voiceId = voiceId;
      this.language = language.split("-")[0];
      this.requireTranslation = requireTranslation;
      this.cursor = this.indexAt(this.video.currentTime);
      this.anchor = this.video.currentTime;
      this.resumeOffset = null;
      const identity = await this.send({ type: "voiceIdentity", voiceId });
      if (configuration !== this.configuration) return;
      this.voiceHash = identity;
      await this.context.resume();
      if (configuration !== this.configuration) return;
      this.running = !this.video.paused || (continueHold && Boolean(this.hold));
    }
    indexAt(time) {
      const i = this.cues?.findIndex((c) => c.end > time);
      return i >= 0 ? i : this.cues?.length || 0;
    }
    invalidate() {
      this.epoch++;
      this.stopAudio();
      for (const task of this.pending.values()) {
        task.abort = true;
        if (task.id)
          this.send({ type: "cancelAudio", id: task.id }).catch(() => {});
      }
      this.pending.clear();
      this.preparing = null;
    }
    captureOffset() {
      if (this.active) {
        const a = this.active;
        this.resumeOffset = {
          index: a.index,
          seconds:
            (a.offset + Math.max(0, this.context.currentTime - a.started)) *
            a.speed,
        };
      }
    }
    reanchor() {
      const resume = Boolean(this.hold);
      this.invalidate();
      this.hold = null;
      this.failed.clear();
      this.cursor = this.indexAt(this.video.currentTime);
      this.anchor = this.video.currentTime;
      this.resumeOffset = null;
      this.running = !this.video.paused || resume;
      this.onNeed(this.video.currentTime, this.running);
      if (resume)
        this.video
          .play()
          .catch(() => this.onState("ready", "Press play to continue"));
    }
    pauseFor(reason) {
      if (!this.video.paused) {
        this.expectedPause = true;
        this.video.pause();
      }
      this.hold = reason;
      this.stopMusic();
    }
    resumeHold() {
      if (!this.hold || !this.running) return;
      this.hold = null;
      this.video.play().catch(() => {
        this.running = false;
        this.onState("ready", "Press play to continue");
      });
    }
    stopAudio() {
      if (!this.active) return;
      const { source, envelope } = this.active;
      this.active = null;
      source.onended = null;
      const now = this.context.currentTime;
      envelope.gain.cancelScheduledValues(now);
      envelope.gain.setValueAtTime(envelope.gain.value, now);
      envelope.gain.linearRampToValueAtTime(0, now + 0.008);
      try {
        source.stop(now + 0.009);
      } catch {}
      setTimeout(() => {
        source.disconnect();
        envelope.disconnect();
      }, 20);
    }
    fail(error) {
      if (error.name === "AbortError") return;
      this.onState("error", error.message);
      this.running = false;
      this.invalidate();
      this.stopMusic();
      this.onPause();
      this.hold = null;
    }
    async fit(index, epoch) {
      const rate = this.video.playbackRate,
        key = index + ":" + rate;
      if (this.fitted.has(key)) return this.fitted.get(key);
      const buffer = this.clips.get(index),
        cue = this.cues[index];
      const available = Math.max(
        0.2,
        Math.min(cue.end, this.cues[index + 1]?.start ?? cue.end) - cue.start,
      );
      // Do not stretch short speech to fill silence, or crush syllables to hit a cue edge.
      const speed = Math.max(
        0.5,
        Math.min(
          2,
          Math.max(0.92, Math.min(1.22, buffer.duration / available)) * rate,
        ),
      );
      const samples = await stretch(
        buffer.getChannelData(0),
        speed,
        buffer.sampleRate,
        () => epoch !== this.epoch,
      );
      if (epoch !== this.epoch)
        throw new DOMException("Cancelled", "AbortError");
      const fitted = this.context.createBuffer(
        1,
        samples.length,
        buffer.sampleRate,
      );
      fitted.copyToChannel(samples, 0);
      const result = { buffer: fitted, speed };
      this.fitted.set(key, result);
      return result;
    }
    async synth(index, epoch) {
      if (this.pending.has(index)) return this.pending.get(index).promise;
      const task = { abort: false, id: null };
      this.pending.set(index, task);
      task.promise = (async () => {
        try {
          const cue = this.cues[index],
            text =
              cue.translated || (!this.requireTranslation ? cue.text : null);
          if (!text) return;
          const key = await A.sha256(
            JSON.stringify({
              text,
              voice: this.voiceHash,
              language: this.language,
              engine: "omnivoice-0.2.1-16-natural-sentence-dsp2",
            }),
          );
          if (task.abort || epoch !== this.epoch) return;
          let result = await this.send({ type: "cachedAudio", key });
          if (task.abort) return;
          if (!result) {
            const idem = await A.sha256(key + A.random());
            task.id = idem;
            try {
              await this.send({
                type: "synthesize",
                text,
                voiceId: this.voiceId,
                duration: null,
                language: this.language,
                idem,
              });
            } catch (error) {
              if (!/Submission in progress/.test(error.message)) throw error;
            }
            const deadline = Date.now() + 180000;
            while (!task.abort && Date.now() < deadline) {
              result = await this.send({ type: "pollAudio", id: idem, key });
              if (result.state === "done") break;
              await new Promise((resolve) => setTimeout(resolve, 350));
            }
            if (!task.abort && result?.state !== "done")
              throw new Error("Voice generation timed out.");
          }
          if (task.abort || epoch !== this.epoch) return;
          const bytes = Uint8Array.from(atob(result.audio), (c) =>
            c.charCodeAt(0),
          );
          const buffer = await this.context.decodeAudioData(bytes.buffer);
          if (
            !Number.isFinite(buffer.duration) ||
            buffer.duration <= 0 ||
            buffer.duration > 60
          )
            throw new Error("Invalid voice clip duration.");
          if (task.abort || epoch !== this.epoch) return;
          this.clips.set(index, buffer);
          await this.fit(index, epoch);
          this.evict();
        } catch (error) {
          if (
            !task.abort &&
            epoch === this.epoch &&
            error.name !== "AbortError"
          )
            this.failed.set(index, error.message);
        } finally {
          if (task.abort && task.id)
            this.send({ type: "cancelAudio", id: task.id }).catch(() => {});
          if (this.pending.get(index) === task) this.pending.delete(index);
        }
      })();
      return task.promise;
    }
    evict() {
      for (const index of this.clips.keys())
        if (index < this.cursor - 1 || index > this.cursor + 5)
          this.clips.delete(index);
      for (const key of this.fitted.keys())
        if (!this.clips.has(Number(key.split(":")[0]))) this.fitted.delete(key);
      const size = () =>
        [
          ...this.clips.values(),
          ...[...this.fitted.values()].map((v) => v.buffer),
        ].reduce((s, b) => s + b.length * b.numberOfChannels * 4, 0);
      for (const index of [...this.clips.keys()].sort(
        (a, b) => Math.abs(b - this.cursor) - Math.abs(a - this.cursor),
      )) {
        if (size() <= 12 * 1024 ** 2) break;
        if (index === this.cursor) continue;
        this.clips.delete(index);
        for (const key of this.fitted.keys())
          if (key.startsWith(index + ":")) this.fitted.delete(key);
      }
    }
    async prime() {
      const index = this.cursor,
        epoch = this.epoch;
      if (!this.cues[index]) return;
      this.onState("buffering", "Preparing the first complete sentence");
      let timer;
      try {
        await Promise.race([
          this.synth(index, epoch),
          new Promise((_, reject) => {
            timer = setInterval(() => {
              if (epoch !== this.epoch)
                reject(new DOMException("Cancelled", "AbortError"));
            }, 40);
          }),
        ]);
      } finally {
        clearInterval(timer);
      }
      if (epoch !== this.epoch) return;
      if (this.failed.has(index)) throw new Error(this.failed.get(index));
    }
    async tick() {
      if (
        !this.running ||
        !this.cues?.length ||
        !this.voiceHash ||
        this.video.seeking ||
        this.stalled
      )
        return;
      const epoch = this.epoch,
        time = this.video.currentTime,
        index = this.cursor,
        cue = this.cues[index];
      if (!cue) return;
      // The speech cursor owns unfinished words even when the video is slightly ahead.
      this.onNeed(cue.start, true);
      this.evict();
      for (let i = index; i < Math.min(this.cues.length, index + 4); i++) {
        if (i > index && this.cues[i].start > time + 30) break;
        if (this.pending.size >= 2) break;
        if (this.requireTranslation && !this.cues[i].translated) continue;
        if (!this.clips.has(i) && !this.pending.has(i) && !this.failed.has(i))
          this.synth(i, epoch).catch((e) => this.fail(e));
      }
      if (this.active) {
        if (time >= this.active.end + 0.75) this.pauseFor("finishing");
        return;
      }
      if (time < cue.start - 0.015) return;
      if (this.failed.has(index)) {
        this.pauseFor("error");
        throw new Error(this.failed.get(index));
      }
      if (!this.clips.has(index)) {
        this.pauseFor("buffering");
        this.onState(
          "buffering",
          this.requireTranslation && !cue.translated
            ? "Translating the current sentence"
            : "Preparing the next complete sentence",
        );
        return;
      }
      if (this.preparing) return;
      this.preparing = index + ":" + epoch;
      try {
        const { buffer, speed } = await this.fit(index, epoch);
        if (epoch !== this.epoch || !this.running || this.stalled) return;
        const source = this.context.createBufferSource(),
          envelope = this.context.createGain();
        source.buffer = buffer;
        source.connect(envelope);
        envelope.connect(this.gain);
        let offset = 0;
        if (this.resumeOffset?.index === index)
          offset = this.resumeOffset.seconds / speed;
        else if (this.anchor !== null && this.anchor > cue.start + 0.25)
          offset =
            ((this.anchor - cue.start) / (cue.end - cue.start)) *
            buffer.duration;
        // Only an explicit seek/start anchor or a manual pause may skip audio.
        this.anchor = null;
        this.resumeOffset = null;
        offset = Math.min(
          Math.max(0, offset),
          Math.max(0, buffer.duration - 0.001),
        );
        const now = this.context.currentTime;
        envelope.gain.setValueAtTime(0, now);
        envelope.gain.linearRampToValueAtTime(1, now + 0.008);
        this.active = {
          source,
          envelope,
          index,
          end: Math.min(cue.end, this.cues[index + 1]?.start ?? cue.end),
          offset,
          speed,
          started: now,
        };
        source.onended = () => {
          if (this.active?.source !== source) return;
          this.active = null;
          source.disconnect();
          envelope.disconnect();
          this.cursor = index + 1;
          this.resumeHold();
          this.tick().catch((e) => this.fail(e));
        };
        source.start(now, offset);
        this.resumeHold();
        this.onState("playing", "Single voice - complete sentences");
      } finally {
        if (this.preparing === index + ":" + epoch) this.preparing = null;
      }
    }
    setOriginal(value) {
      this.video.volume = value;
      if (value > 0) this.video.muted = false;
    }
    setDub(value) {
      this.gain.gain.setTargetAtTime(value, this.context.currentTime, 0.02);
    }
    setMusic(value) {
      this.musicGain.gain.setTargetAtTime(
        value,
        this.context.currentTime,
        0.03,
      );
    }
    async loadMusic(url) {
      this.stopMusic();
      this.music = null;
      if (!url) return;
      const response = await fetch(url),
        data = await response.arrayBuffer();
      if (data.byteLength > 16 * 1024 ** 2)
        throw new Error("Background music exceeds limit.");
      this.music = await this.context.decodeAudioData(data);
      this.startMusic();
    }
    startMusic() {
      if (!this.music || this.musicSource || !this.running || this.hold) return;
      const source = this.context.createBufferSource();
      source.buffer = this.music;
      source.loop = true;
      source.connect(this.musicGain);
      source.start();
      this.musicSource = source;
    }
    stopMusic() {
      if (this.musicSource) {
        this.musicSource.stop();
        this.musicSource.disconnect();
        this.musicSource = null;
      }
    }
    async close() {
      this.configuration = (this.configuration || 0) + 1;
      this.running = false;
      this.invalidate();
      this.stopMusic();
      clearInterval(this.timer);
      this.listeners.abort();
      this.video.volume = this.original.volume;
      this.video.muted = this.original.muted;
      this.clips.clear();
      this.fitted.clear();
      this.onPause();
      await this.context.close();
    }
  }
  A.stretch = stretch;
  A.Mixer = Mixer;
  if (typeof module !== "undefined")
    module.exports = { stretch, edgeFade, Mixer };
})(globalThis);

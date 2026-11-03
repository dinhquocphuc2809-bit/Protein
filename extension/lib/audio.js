(function (root) {
  "use strict";
  const A = root.Auvirel;
  async function stretch(samples, speed, rate, cancelled = () => false) {
    if (!Number.isFinite(speed) || speed < 0.5 || speed > 2)
      throw new Error("Unsupported speech stretch ratio.");
    if (Math.abs(speed - 1) < 0.015) return samples.slice();
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
    const fade = Math.min(Math.round(rate * 0.005), Math.floor(length / 2));
    for (let i = 0; i < fade; i++) {
      result[i] *= i / fade;
      result[length - i - 1] *= i / fade;
    }
    return result;
  }

  class Mixer {
    constructor(video, send, onState) {
      this.video = video;
      this.send = send;
      this.onState = onState;
      this.context = new AudioContext({ sampleRate: 24000 });
      this.gain = this.context.createGain();
      this.gain.connect(this.context.destination);
      this.musicGain = this.context.createGain();
      this.musicGain.gain.value = 0.12;
      this.musicGain.connect(this.context.destination);
      this.original = { volume: video.volume, muted: video.muted };
      this.epoch = 0;
      this.clips = new Map();
      this.pending = new Map();
      this.failed = new Map();
      this.active = null;
      this.running = false;
      this.hold = null;
      this.expectedPause = false;
      this.listeners = new AbortController();
      const listen = (event, fn) =>
        video.addEventListener(event, fn, { signal: this.listeners.signal });
      listen("seeking", () => this.reanchor());
      listen("ratechange", () => this.reanchor());
      listen("play", () => {
        this.hold = null;
        this.running = true;
        this.context.resume();
        this.startMusic();
      });
      listen("pause", () => {
        if (this.expectedPause) {
          this.expectedPause = false;
          return;
        }
        this.running = false;
        this.invalidate();
        this.stopMusic();
      });
      listen("ended", () => {
        this.running = false;
        this.stopMusic();
        for (const task of this.pending.values()) {
          task.abort = true;
          if (task.id)
            this.send({ type: "cancelAudio", id: task.id }).catch(() => {});
        }
        this.pending.clear();
      });
      this.timer = setInterval(
        () => this.tick().catch((error) => this.fail(error)),
        60,
      );
    }
    async configure(cues, voiceId, language) {
      this.invalidate();
      this.clips.clear();
      this.failed.clear();
      this.voiceHash = null;
      this.cues = cues;
      this.voiceId = voiceId;
      this.language = language.split("-")[0];
      const epoch = this.epoch;
      const identity = await this.send({ type: "voiceIdentity", voiceId });
      if (epoch !== this.epoch) return;
      this.voiceHash = identity;
      await this.context.resume();
      this.running = !this.video.paused;
      this.onState("ready", "Voice ready");
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
    reanchor() {
      const resume = Boolean(this.hold);
      this.invalidate();
      this.hold = null;
      this.failed.clear();
      this.running = !this.video.paused || resume;
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
      if (this.active) {
        this.active.source.onended = null;
        try {
          this.active.source.stop();
        } catch {}
        this.active.source.disconnect();
        this.active = null;
      }
    }
    fail(error) {
      if (error.name === "AbortError") return;
      this.onState("error", error.message);
      this.running = false;
      this.invalidate();
      this.stopMusic();
      if (this.hold) {
        this.hold = null;
      }
    }
    async synth(index, epoch) {
      const cue = this.cues[index],
        text = cue.translated || cue.text;
      const next = this.cues[index + 1];
      const duration = Math.min(
        30,
        Math.max(0.2, Math.min(cue.end, next?.start ?? cue.end) - cue.start),
      );
      const key = await A.sha256(
        JSON.stringify({
          text,
          voice: this.voiceHash,
          duration,
          language: this.language,
          engine: "omnivoice-0.2.1-16-dsp1",
        }),
      );
      if (epoch !== this.epoch) return;
      const task = { abort: false, id: null };
      this.pending.set(index, task);
      try {
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
              duration,
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
            await new Promise((resolve) => setTimeout(resolve, 700));
          }
          if (!task.abort && result?.state !== "done")
            throw new Error("Voice generation timed out.");
        }
        if (task.abort || epoch !== this.epoch) return;
        const bytes = Uint8Array.from(atob(result.audio), (c) =>
          c.charCodeAt(0),
        );
        const buffer = await this.context.decodeAudioData(bytes.buffer);
        if (buffer.duration > 60)
          throw new Error("Voice clip exceeds duration limit.");
        if (!task.abort && epoch === this.epoch) {
          this.clips.set(index, buffer);
          let size = [...this.clips.values()].reduce(
            (sum, value) => sum + value.length * value.numberOfChannels * 4,
            0,
          );
          const current = A.atTime(this.cues, this.video.currentTime);
          for (const id of [...this.clips.keys()].sort(
            (a, b) => Math.abs(b - current) - Math.abs(a - current),
          )) {
            if (size <= 12 * 1024 ** 2) break;
            if (id === current) continue;
            const value = this.clips.get(id);
            size -= value.length * value.numberOfChannels * 4;
            this.clips.delete(id);
          }
        }
      } catch (error) {
        if (!task.abort && epoch === this.epoch)
          this.failed.set(index, error.message);
      } finally {
        if (task.abort && task.id)
          this.send({ type: "cancelAudio", id: task.id }).catch(() => {});
        if (this.pending.get(index) === task) this.pending.delete(index);
      }
    }
    async tick() {
      if (
        !this.running ||
        !this.cues?.length ||
        !this.voiceHash ||
        this.video.seeking
      )
        return;
      const time = this.video.currentTime,
        index = A.atTime(this.cues, time);
      const start = Math.max(0, index),
        epoch = this.epoch;
      // Retain only the playhead neighborhood; compressed cache lives in extension IndexedDB.
      let bytes = 0;
      for (const [id, buffer] of this.clips) {
        bytes += buffer.length * buffer.numberOfChannels * 4;
        if (id < start - 1 || id > start + 7) this.clips.delete(id);
      }
      if (bytes > 12 * 1024 ** 2)
        for (const id of [...this.clips.keys()].sort((a, b) => b - a)) {
          if (id > start + 2) this.clips.delete(id);
        }
      for (let i = start; i < Math.min(this.cues.length, start + 7); i++) {
        if (this.cues[i].end <= time || this.cues[i].start > time + 45)
          continue;
        if (this.pending.size >= 2) break;
        if (!this.clips.has(i) && !this.pending.has(i) && !this.failed.has(i)) {
          this.pending.set(i, { abort: false, id: null });
          this.synth(i, epoch).catch((error) => this.fail(error));
        }
      }
      if (this.active) {
        if (
          time >= this.active.end - 0.02 &&
          this.active.source.context.state === "running"
        )
          this.pauseFor("finishing");
        return;
      }
      const cue = this.cues[index];
      if (!cue || time >= cue.end) return;
      if (this.played?.index === index && this.played.epoch === epoch) {
        this.resumeHold();
        return;
      }
      if (this.failed.has(index)) {
        this.pauseFor("error");
        throw new Error(this.failed.get(index));
      }
      if (!this.clips.has(index)) {
        this.pauseFor("buffering");
        this.onState("buffering", "Preparing the next sentence");
        return;
      }
      if (this.preparing) return;
      this.preparing = index + ":" + epoch;
      try {
        const buffer = this.clips.get(index),
          end = Math.min(cue.end, this.cues[index + 1]?.start ?? cue.end);
        const available = Math.max(0.2, end - cue.start),
          speed = Math.min(
            1.8,
            Math.max(
              0.6,
              (buffer.duration / available) * this.video.playbackRate,
            ),
          );
        const samples = await stretch(
          buffer.getChannelData(0),
          speed,
          buffer.sampleRate,
          () => epoch !== this.epoch,
        );
        if (epoch !== this.epoch || !this.running) return;
        const fitted = this.context.createBuffer(
          1,
          samples.length,
          buffer.sampleRate,
        );
        fitted.copyToChannel(samples, 0);
        const source = this.context.createBufferSource();
        source.buffer = fitted;
        source.connect(this.gain);
        const offset = Math.min(
          fitted.duration - 0.001,
          Math.max(
            0,
            (this.video.currentTime - cue.start) / this.video.playbackRate,
          ),
        );
        this.active = { source, index, end };
        source.onended = () => {
          if (this.active?.source === source) {
            this.active = null;
            source.disconnect();
            this.played = { index, epoch };
            this.resumeHold();
          }
        };
        if (this.played?.index === index && this.played.epoch === epoch) {
          this.active = null;
          source.disconnect();
          this.resumeHold();
          return;
        }
        source.start(0, offset);
        this.resumeHold();
        this.onState("playing", "Single voice · synchronized");
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
      this.running = false;
      this.invalidate();
      this.stopMusic();
      clearInterval(this.timer);
      this.listeners.abort();
      this.video.volume = this.original.volume;
      this.video.muted = this.original.muted;
      this.clips.clear();
      await this.context.close();
    }
  }
  A.stretch = stretch;
  A.Mixer = Mixer;
  if (typeof module !== "undefined") module.exports = { stretch };
})(globalThis);

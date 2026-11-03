(() => {
  "use strict";
  if (globalThis.__auvirelLoaded) return;
  globalThis.__auvirelLoaded = true;
  const api = globalThis.browser || chrome,
    A = globalThis.Auvirel;
  const send = async (message) => {
    const response = await api.runtime.sendMessage(message);
    if (!response?.ok)
      throw new Error(response?.error || "Extension connection lost.");
    return response.value;
  };
  const host = document.createElement("div");
  host.id = "auvirel-surface";
  host.style.cssText =
    "all:initial;position:fixed;inset:0;z-index:2147483646;pointer-events:none";
  const shadow = host.attachShadow({ mode: "closed" });
  const style = document.createElement("link");
  style.rel = "stylesheet";
  style.href = api.runtime.getURL("content.css");
  shadow.append(style);
  const surface = document.createElement("div");
  surface.className = "auvirel-root";
  surface.innerHTML = `<button class="launcher" aria-label="Open Auvirel" title="Auvirel"><svg viewBox="0 0 32 32" aria-hidden="true"><path d="m6 24 9-18h3l8 18M10 17h12M16 13v12"/></svg></button>
  <section class="panel" aria-label="Auvirel video companion" hidden>
    <header><div class="brand"><span class="brand-mark"><svg viewBox="0 0 32 32" aria-hidden="true"><path d="m6 25 9-19h3l8 19M10 18h12M16 13v13"/></svg></span><div><strong>Auvirel</strong><small>Listen. Understand. Explore.</small></div></div><button class="icon" id="settings" aria-label="Settings"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 3-.6 2.3-2 .9-2.1-.6-1.8 3.2 1.6 1.7v2.4l-1.6 1.7 1.8 3.2 2.2-.6 2 .9.5 2.3h3.8l.6-2.3 2-.9 2.1.6 1.8-3.2-1.6-1.7v-2.4l1.6-1.7-1.8-3.2-2.1.6-2-.9-.6-2.3Z"/><circle cx="11" cy="11.7" r="3"/></svg></button><button class="icon" id="collapse" aria-label="Minimize"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14"/></svg></button></header>
    <div class="video-title">Choose a video to begin</div>
    <div class="status" role="status" aria-live="polite"><span class="dot"></span><span id="state">Ready when you are</span></div>
    <div class="setup"><label>Voice<select id="voice"></select></label><div class="row"><label>Translate to<select id="language"><option value="vi">Vietnamese</option><option value="en">English</option><option value="ja">Japanese</option><option value="ko">Korean</option><option value="zh">Chinese</option><option value="fr">French</option><option value="de">German</option><option value="es">Spanish</option></select></label><label>Translation<select id="model"><option value="basic">Gemini · Essential</option><option value="advanced">Gemini · Advanced</option><option value="deepseek">DeepSeek</option></select></label></div>
    <div class="row"><label>When captions are unavailable<select id="asr"><option value="fast">Fast · Deepgram</option><option value="quality">Quality · Qwen ASR</option></select></label><label class="file-button">Import SRT<input id="srt" type="file" accept=".srt"></label></div>
    <label class="check"><input type="checkbox" id="translated">Imported subtitles are already translated</label>
    <div class="row actions"><button class="primary" id="start">Prepare this video</button><button id="stop" class="secondary" disabled>Stop</button></div></div>
    <div class="mixer" aria-label="Audio mixer"><label><span>Original video</span><output id="original-value">20%</output><input id="original" type="range" min="0" max="100" value="20"></label><label><span>Dubbed voice</span><output id="dub-value">100%</output><input id="dub" type="range" min="0" max="100" value="100"></label><label><span>Background music</span><select id="bgm"><option value="">Off</option></select><input id="music" aria-label="Background music volume" type="range" min="0" max="100" value="12"></label></div>
    <div class="tabs" role="tablist"><button role="tab" aria-selected="true" data-tab="transcript">Transcript</button><button role="tab" aria-selected="false" data-tab="summary">Summary</button><button role="tab" aria-selected="false" data-tab="chat">Study chat</button></div>
    <section id="transcript" role="tabpanel"><div class="transcript-tools"><select id="mode" aria-label="Subtitle display"><option value="bilingual">Bilingual</option><option value="translated">Translation</option><option value="original">Original</option><option value="off">Hide overlay</option></select><button class="text-button" id="export">Export SRT</button></div><div id="cues" class="reading"><p class="empty">Your transcript will appear here, with every sentence linked to the video.</p></div></section>
    <section id="summary" role="tabpanel" hidden><button class="secondary wide" id="summarize">Create timestamped summary</button><div id="sections" class="reading"><p class="empty">Revisit the key ideas, one moment at a time.</p></div></section>
    <section id="chat" role="tabpanel" hidden><div id="messages" class="reading" aria-live="polite"><p class="empty">Ask about the ideas in this video.</p></div><form id="question-form"><label class="sr-only" for="question">Question about this video</label><textarea id="question" rows="2" maxlength="4000" placeholder="Explain a concept or ask a question"></textarea><button class="primary" type="submit">Ask</button></form></section>
    <footer>One voice. Your pace.<span id="cue-count"></span></footer>
  </section><div class="subtitles" hidden aria-live="off"><div id="sub-translated"></div><div id="sub-original"></div></div>`;
  shadow.append(surface);
  document.documentElement.append(host);
  const $ = (id) => shadow.getElementById(id),
    panel = shadow.querySelector(".panel"),
    overlay = shadow.querySelector(".subtitles");
  let video = null,
    mixer = null,
    cues = [],
    videoJob = null,
    imported = null,
    history = [],
    work = 0,
    activeJob = null,
    tab = "transcript",
    renderedStart = -1,
    selectedCue = -1,
    lastUrl = location.href;
  function status(kind, text) {
    const element = shadow.querySelector(".status");
    element.dataset.state = kind;
    $("state").textContent = text;
  }
  function error(reason) {
    status("error", reason.message || String(reason));
  }
  function options(select, rows) {
    select.replaceChildren(
      ...rows.map((row) => {
        const option = document.createElement("option");
        option.value = row.id;
        option.textContent = row.name;
        return option;
      }),
    );
  }
  async function init() {
    const conf = await send({ type: "publicSettings" });
    options($("voice"), conf.voices);
    $("voice").value = conf.voiceId;
    if (!$("voice").value && conf.voices.length)
      $("voice").value = conf.voices[0].id;
    for (const key of ["language", "model", "asr"]) $(key).value = conf[key];
    $("mode").value = conf.subtitleMode;
    options($("bgm"), [
      { id: "", name: "Off" },
      ...conf.bgm.map((row) => ({ id: row.path, name: row.name })),
    ]);
    if (!conf.connected)
      status("ready", "Open settings to activate your access code");
  }
  shadow.querySelector(".launcher").onclick = () => {
    panel.hidden = !panel.hidden;
    if (!panel.hidden) init().catch(error);
  };
  $("collapse").onclick = () => {
    panel.hidden = true;
  };
  $("settings").onclick = () => send({ type: "openSettings" }).catch(error);
  async function stop(reset = false) {
    work++;
    if (activeJob) send({ type: "cancelJob", id: activeJob }).catch(() => {});
    activeJob = null;
    const current = mixer;
    mixer = null;
    if (current) await current.close();
    $("start").disabled = false;
    $("stop").disabled = true;
    if (reset) {
      cues = [];
      imported = null;
      videoJob = null;
      history = [];
      renderedStart = -1;
      $("cues").replaceChildren();
      $("sections").replaceChildren();
      $("messages").replaceChildren();
      overlay.hidden = true;
    }
    status("ready", "Stopped");
  }
  $("stop").onclick = () => stop().catch(error);
  function chooseVideo() {
    const candidates = [...document.querySelectorAll("video")].filter(
      (v) =>
        v.getBoundingClientRect().width > 100 &&
        v.getBoundingClientRect().height > 60,
    );
    candidates.sort(
      (a, b) => b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight,
    );
    const next = candidates[0] || null;
    if (video && (next !== video || location.href !== lastUrl))
      stop(true).catch(error);
    video = next;
    lastUrl = location.href;
    shadow.querySelector(".launcher").hidden = !video;
    shadow.querySelector(".video-title").textContent = video
      ? document.title
      : "No video player found";
  }
  async function pageCaptions() {
    for (const track of [...video.textTracks]) {
      if (!["subtitles", "captions"].includes(track.kind)) continue;
      const previous = track.mode;
      track.mode = "hidden";
      try {
        for (let i = 0; i < 8 && !track.cues?.length; i++)
          await new Promise((resolve) => setTimeout(resolve, 150));
        if (track.cues?.length)
          return {
            cues: A.cues(
              [...track.cues].map((c) => ({
                start: c.startTime,
                end: c.endTime,
                text: c.text,
              })),
            ),
            language: track.language || "auto",
          };
      } finally {
        track.mode = previous;
      }
    }
    if (/(^|\.)youtube\.com$/.test(location.hostname))
      return send({ type: "youtubeCaptions" }).catch(() => null);
    return null;
  }
  async function waitJob(job, epoch) {
    activeJob = job.id;
    const deadline = Date.now() + 32 * 60 * 1000;
    while (Date.now() < deadline) {
      if (epoch !== work) {
        await send({ type: "cancelJob", id: job.id }).catch(() => {});
        throw new DOMException("Cancelled", "AbortError");
      }
      const state = await send({ type: "pollJob", id: job.id });
      if (state.state === "done") {
        activeJob = null;
        return state.result;
      }
      if (state.state === "failed" || state.state === "cancelled") {
        activeJob = null;
        throw new Error(state.error || "Task cancelled.");
      }
      status(
        "buffering",
        {
          queued: "Waiting for the server",
          resolving_media: "Finding the audio source",
          recognizing: "Recognizing speech",
          aligning: "Aligning words to the video",
          translating: "Translating with context",
          summarizing: "Connecting the key ideas",
        }[state.stage] || state.stage,
      );
      await new Promise((resolve) => setTimeout(resolve, 1100));
    }
    await send({ type: "cancelJob", id: job.id }).catch(() => {});
    activeJob = null;
    throw new Error("Task deadline exceeded.");
  }
  $("srt").onchange = async (event) => {
    try {
      const file = event.target.files[0];
      if (!file) return;
      if (file.size > 2 * 1024 ** 2) throw new Error("SRT exceeds 2 MiB.");
      imported = A.parseSrt(
        new TextDecoder("utf-8", { fatal: true }).decode(
          await file.arrayBuffer(),
        ),
      );
      status("ready", `${imported.length} subtitles imported`);
    } catch (reason) {
      imported = null;
      error(reason);
    }
  };
  async function createMixer() {
    if (mixer) await mixer.close();
    mixer = new A.Mixer(video, send, status);
    await mixer.configure(cues, $("voice").value, $("language").value);
    mixer.setOriginal(+$("original").value / 100);
    mixer.setDub(+$("dub").value / 100);
    if ($("bgm").value)
      await mixer.loadMusic(api.runtime.getURL("assets/" + $("bgm").value));
  }
  $("start").onclick = async () => {
    try {
      if (!video) throw new Error("Open a page with a video first.");
      $("start").disabled = true;
      $("stop").disabled = false;
      if (cues.length && videoJob) {
        await createMixer();
        await video.play();
        return;
      }
      const epoch = ++work,
        capturedVideo = video,
        url = location.href;
      status("buffering", "Reading the available subtitles");
      const found = imported
        ? { cues: imported, language: "auto" }
        : await pageCaptions();
      if (epoch !== work || video !== capturedVideo || location.href !== url)
        return;
      const payload = {
        url,
        title: document.title.slice(0, 300),
        source_language: found?.language || "auto",
        target_language: $("language").value,
        model: $("model").value,
        asr: $("asr").value,
        already_translated: Boolean(imported && $("translated").checked),
      };
      if (found?.cues) payload.cues = found.cues;
      const job = await send({ type: "job", payload, idem: A.random() });
      const result = await waitJob(job, epoch);
      if (epoch !== work) return;
      cues = A.cues(result.cues);
      videoJob = job.id;
      renderTranscript(true);
      $("cue-count").textContent = `${cues.length} cues`;
      await createMixer();
      status("ready", "Ready. Press play to listen.");
      $("start").textContent = "Resume dubbing";
      $("start").disabled = false;
    } catch (reason) {
      if (reason.name !== "AbortError") error(reason);
      $("start").disabled = false;
    }
  };
  $("voice").onchange = async () => {
    try {
      if (mixer)
        await mixer.configure(cues, $("voice").value, $("language").value);
    } catch (reason) {
      error(reason);
    }
  };
  for (const id of ["language", "model", "asr"])
    $(id).onchange = () => {
      stop(true).catch(error);
      $("start").textContent = "Prepare this video";
    };
  for (const [id, method] of [
    ["original", "setOriginal"],
    ["dub", "setDub"],
    ["music", "setMusic"],
  ])
    $(id).oninput = () => {
      if ($(id + "-value")) $(id + "-value").textContent = $(id).value + "%";
      mixer?.[method](+$(id).value / 100);
    };
  $("bgm").onchange = () =>
    mixer
      ?.loadMusic(
        $("bgm").value ? api.runtime.getURL("assets/" + $("bgm").value) : "",
      )
      .catch(error);
  shadow.querySelectorAll("[data-tab]").forEach((button) => {
    button.onclick = () => {
      tab = button.dataset.tab;
      shadow
        .querySelectorAll("[data-tab]")
        .forEach((b) => b.setAttribute("aria-selected", String(b === button)));
      for (const name of ["transcript", "summary", "chat"])
        $(name).hidden = name !== tab;
    };
    button.onkeydown = (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      const buttons = [...shadow.querySelectorAll("[data-tab]")],
        index = buttons.indexOf(button);
      const next = buttons[(index + (event.key === "ArrowRight" ? 1 : 2)) % 3];
      next.focus();
      next.click();
    };
  });
  function seek(seconds) {
    if (!video || !Number.isFinite(seconds)) return;
    video.currentTime = seconds;
  }
  function renderTranscript(force = false) {
    if (!cues.length || !video) return;
    const index = Math.max(0, A.atTime(cues, video.currentTime)),
      start = Math.max(0, index - 10);
    if (
      !force &&
      renderedStart >= 0 &&
      index >= renderedStart &&
      index < renderedStart + 55
    ) {
      if (selectedCue !== index) {
        $("cues")
          .querySelector('[aria-current="true"]')
          ?.removeAttribute("aria-current");
        $("cues")
          .querySelector(`[data-cue="${index}"]`)
          ?.setAttribute("aria-current", "true");
        selectedCue = index;
      }
      return;
    }
    renderedStart = start;
    selectedCue = index;
    const fragment = document.createDocumentFragment();
    for (const cue of cues.slice(start, start + 70)) {
      const button = document.createElement("button");
      button.className = "cue";
      button.dataset.cue = cue.id;
      button.onclick = () => seek(cue.start);
      const time = document.createElement("time");
      time.textContent = A.stamp(cue.start);
      button.append(time);
      const content = document.createElement("span"),
        translated = document.createElement("strong"),
        original = document.createElement("small");
      translated.textContent = cue.translated || cue.text;
      original.textContent = cue.text;
      content.append(translated, original);
      button.append(content);
      if (cue.id === index) button.setAttribute("aria-current", "true");
      fragment.append(button);
    }
    $("cues").replaceChildren(fragment);
  }
  $("summarize").onclick = async () => {
    if (!videoJob) return error(new Error("Prepare the video first."));
    $("summarize").disabled = true;
    try {
      const epoch = work,
        job = await send({
          type: "summary",
          payload: { video_job_id: videoJob, model: $("model").value },
          idem: A.random(),
        });
      const result = await waitJob(job, epoch);
      $("sections").replaceChildren(
        ...result.sections.map((section) => {
          const card = document.createElement("article"),
            button = document.createElement("button"),
            paragraph = document.createElement("p");
          button.className = "chapter";
          button.textContent = `${A.stamp(section.start)}  ${section.title}`;
          button.onclick = () => seek(section.start);
          paragraph.textContent = section.text;
          card.append(button, paragraph);
          return card;
        }),
      );
      status("ready", "Summary ready");
    } catch (reason) {
      if (reason.name !== "AbortError") error(reason);
    } finally {
      $("summarize").disabled = false;
    }
  };
  function chatMessage(role, text) {
    $("messages").querySelector(".empty")?.remove();
    const message = document.createElement("p");
    message.className = "message " + role;
    let last = 0;
    for (const match of text.matchAll(/\[(\d{1,3}):(\d{2})\]/g)) {
      message.append(document.createTextNode(text.slice(last, match.index)));
      const button = document.createElement("button");
      button.className = "text-button";
      button.textContent = match[0];
      button.onclick = () => seek(+match[1] * 60 + +match[2]);
      message.append(button);
      last = match.index + match[0].length;
    }
    message.append(document.createTextNode(text.slice(last)));
    $("messages").append(message);
    message.scrollIntoView({ block: "nearest" });
  }
  $("question-form").onsubmit = async (event) => {
    event.preventDefault();
    const question = $("question").value.trim(),
      button = event.submitter;
    if (!videoJob) return error(new Error("Prepare the video first."));
    if (!question) return;
    button.disabled = true;
    try {
      const epoch = work,
        job = await send({
          type: "chat",
          payload: {
            video_job_id: videoJob,
            model: $("model").value,
            question,
            history: history.slice(-10),
          },
          idem: A.random(),
        });
      chatMessage("user", question);
      $("question").value = "";
      const result = await waitJob(job, epoch);
      chatMessage("assistant", result.answer);
      history.push(
        { role: "user", content: question },
        { role: "assistant", content: result.answer.slice(0, 8000) },
      );
      history = history.slice(-10);
      status("ready", "Answer ready");
    } catch (reason) {
      if (reason.name !== "AbortError") error(reason);
    } finally {
      button.disabled = false;
    }
  };
  $("export").onclick = () => {
    if (!cues.length) return;
    const stamp = (seconds) => {
      const n = Math.round(seconds * 1000);
      return `${String(Math.floor(n / 3600000)).padStart(2, "0")}:${String(Math.floor(n / 60000) % 60).padStart(2, "0")}:${String(Math.floor(n / 1000) % 60).padStart(2, "0")},${String(n % 1000).padStart(3, "0")}`;
    };
    const body = cues
      .map(
        (cue, index) =>
          `${index + 1}\n${stamp(cue.start)} --> ${stamp(cue.end)}\n${cue.translated || cue.text}\n`,
      )
      .join("\n");
    const url = URL.createObjectURL(
      new Blob([body], { type: "application/x-subrip;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "auvirel-subtitles.srt";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  };
  function draw() {
    if (!video || !cues.length || $("mode").value === "off") {
      overlay.hidden = true;
      return;
    }
    const rect = video.getBoundingClientRect(),
      cue = cues[A.atTime(cues, video.currentTime)];
    if (!cue || cue.end <= video.currentTime || rect.width <= 0) {
      overlay.hidden = true;
      return;
    }
    overlay.hidden = false;
    overlay.style.left = `${Math.max(8, rect.left + rect.width * 0.08)}px`;
    overlay.style.top = `${Math.min(innerHeight - 40, rect.bottom - 68)}px`;
    overlay.style.width = `${rect.width * 0.84}px`;
    $("sub-translated").textContent =
      $("mode").value === "original" ? "" : cue.translated || cue.text;
    $("sub-original").textContent =
      $("mode").value === "translated" ? "" : cue.text;
    if (!panel.hidden && tab === "transcript") renderTranscript();
  }
  setInterval(chooseVideo, 1200);
  setInterval(draw, 100);
  document.addEventListener("fullscreenchange", () => {
    const parent = document.fullscreenElement || document.documentElement;
    if (parent.tagName !== "VIDEO") parent.append(host);
  });
  window.addEventListener("pagehide", () => stop().catch(() => {}), {
    once: true,
  });
  chooseVideo();
  init().catch(error);
})();

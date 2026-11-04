"use strict";
if (typeof importScripts === "function")
  importScripts(
    "lib/core.js",
    "lib/cache.js",
    "lib/captions.js",
    "lib/media.js",
    "lib/voice-transport.js",
  );
const api = globalThis.browser || chrome;
const A = globalThis.Auvirel;
const ownOrigin = api.runtime.getURL("");
const defaults = {
  backend: "https://ubuntu-a1.tail5dab10.ts.net",
  voiceEndpoint: "",
  voiceId: "vi-dang-khoa",
  language: "vi",
  model: "basic",
  asr: "fast",
  subtitleMode: "bilingual",
};
const get = async (key) => (await api.storage.local.get(key))[key];
const settings = async () => ({ ...defaults, ...(await get("settings")) });
if (api.storage.local.setAccessLevel)
  api.storage.local
    .setAccessLevel({ accessLevel: "TRUSTED_CONTEXTS" })
    .catch(() => {});

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    signal: AbortSignal.timeout(24000),
    credentials: "omit",
    redirect: "error",
    cache: "no-store",
  });
  const length = +response.headers.get("content-length");
  if (length > 12 * 1024 ** 2) throw new Error("Service response too large.");
  const reader = response.body.getReader(),
    chunks = [];
  let size = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > 12 * 1024 ** 2) {
      await reader.cancel();
      throw new Error("Service response too large.");
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.length;
  }
  let data;
  try {
    data = JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    throw new Error(
      `Service returned unreadable data (HTTP ${response.status}).`,
    );
  }
  if (!response.ok) {
    const message =
      typeof data.detail === "string"
        ? data.detail.slice(0, 240)
        : `Request failed (HTTP ${response.status}).`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}

async function backend(method, path, payload, idem) {
  const conf = await settings();
  let session = await get("session");
  if (
    !session ||
    session.expires * 1000 <= Date.now() + (session.clockOffset || 0)
  )
    throw new Error("Activate your access code in settings.");
  const origin = A.endpoint(conf.backend),
    body = payload === undefined ? "" : JSON.stringify(payload);
  if (
    session.expires * 1000 < Date.now() + (session.clockOffset || 0) + 120000 &&
    session.ticket_expires > session.expires + 1
  ) {
    const headers = await A.signedHeaders(
      session,
      "POST",
      "/v1/session/refresh",
      "",
    );
    session = await fetchJson(origin + "/v1/session/refresh", {
      method: "POST",
      headers,
    });
    session.clockOffset = session.server_time * 1000 - Date.now();
    await api.storage.local.set({ session });
  }
  for (let attempt = 0; attempt < 2; attempt++) {
    const headers = await A.signedHeaders(session, method, path, body);
    if (idem) headers["Idempotency-Key"] = idem;
    try {
      return await fetchJson(origin + path, {
        method,
        headers,
        ...(body ? { body } : {}),
      });
    } catch (error) {
      if (
        attempt ||
        (error.status && error.status < 500) ||
        (method === "POST" && !idem)
      )
        throw error;
    }
  }
}

async function voice(method, path, payload, idem) {
  const conf = await settings(),
    credentials = await get("voiceProxy");
  if (!credentials?.id || !credentials?.secret)
    throw new Error("Connect your Modal voice worker in settings.");
  const headers = {
    "Modal-Key": credentials.id,
    "Modal-Secret": credentials.secret,
    "Content-Type": "application/json",
  };
  if (idem) headers["Idempotency-Key"] = idem;
  const options = {
    method,
    headers,
    ...(payload ? { body: JSON.stringify(payload) } : {}),
  };
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      return await fetchJson(
        A.endpoint(conf.voiceEndpoint, true) + path,
        options,
      );
    } catch (error) {
      if (
        attempt ||
        (error.status && error.status < 500) ||
        (method === "POST" && !idem)
      )
        throw error;
    }
  }
}

async function presets() {
  return (await fetch(api.runtime.getURL("assets/presets.json"))).json();
}
const voiceTransport = new A.VoiceTransport(
  voice,
  async () => {
    const conf = await settings(),
      proxy = await get("voiceProxy");
    return conf.voiceEndpoint + ":" + (proxy?.id || "");
  },
  reference,
);
async function reference(id) {
  if (id === "custom") {
    const custom = await get("customVoice");
    if (!custom) throw new Error("Upload a WAV and its transcript first.");
    return custom;
  }
  const preset = (await presets()).find((p) => p.id === id);
  if (!preset) throw new Error("Unknown voice preset.");
  const bytes = new Uint8Array(
    await (
      await fetch(api.runtime.getURL("assets/" + preset.path))
    ).arrayBuffer(),
  );
  let binary = "";
  for (let start = 0; start < bytes.length; start += 8192)
    binary += String.fromCharCode(...bytes.subarray(start, start + 8192));
  return {
    reference: btoa(binary),
    reference_text: preset.transcript,
    hash: await A.sha256(bytes),
  };
}

async function youtubeCaptions(sender, message) {
  const href = message?.href || sender.url;
  if (
    !sender.tab?.id ||
    !VeloaMedia.youtubeId(href || "") ||
    new URL(href).origin !== new URL(sender.url).origin
  )
    throw new Error("YouTube captions require the active watch page.");
  const videoId = VeloaMedia.youtubeId(href);
  const target = { tabId: sender.tab.id, frameIds: [sender.frameId] };
  // Also supports pages that were open before the extension was reloaded.
  await api.scripting.executeScript({
    target,
    world: "MAIN",
    files: ["lib/captions.js", "lib/media.js", "youtube-main.js"],
  });
  const results = await api.scripting.executeScript({
    target,
    world: "MAIN",
    args: [videoId],
    func: async (id) => globalThis.__veloaYoutubeCaptions?.acquire(id),
  });
  return VeloaCaptions.acquisition(results[0]?.result, videoId, A.cues);
}

async function siteCaptions(message, sender) {
  if (
    !sender.tab?.id ||
    !Number.isInteger(sender.frameId) ||
    !/^https:\/\//.test(sender.url || "")
  )
    throw new Error("Subtitles require an HTTPS video page.");
  if (
    typeof message.href !== "string" ||
    message.href.length > 12000 ||
    new URL(message.href).origin !== new URL(sender.url).origin ||
    typeof message.src !== "string" ||
    message.src.length > 12000
  )
    throw new Error("Video changed. Retry subtitle acquisition.");
  const target = { tabId: sender.tab.id, frameIds: [sender.frameId] };
  await api.scripting.executeScript({
    target,
    world: "MAIN",
    files: [
      "lib/captions.js",
      "lib/sites.js",
      "lib/media.js",
      "lib/subtitle-formats.js",
      "multisite-main.js",
    ],
  });
  const results = await api.scripting.executeScript({
    target,
    world: "MAIN",
    args: [{ href: message.href, src: message.src }],
    func: async (expected) => globalThis.__veloaSiteCaptions?.acquire(expected),
  });
  const result = results[0]?.result;
  if (
    result?.state === "ready" &&
    result.href === message.href &&
    result.src === message.src
  )
    return {
      cues: A.cues(result.cues),
      language: VeloaMedia.language(result.language),
    };
  return { state: result?.state === "failed" ? "failed" : "unknown" };
}

async function handle(message, sender) {
  if (
    !message ||
    sender.id !== api.runtime.id ||
    typeof message.type !== "string"
  )
    throw new Error("Invalid extension request.");
  const trusted = (sender.url || "").startsWith(ownOrigin);
  const conf = await settings();
  if (message.type === "publicSettings") {
    const catalog = await presets();
    const custom = await get("customVoice");
    return {
      ...conf,
      voices: catalog
        .map(({ id, name }) => ({ id, name }))
        .concat(custom ? [{ id: "custom", name: "Personal voice" }] : []),
      bgm: await (await fetch(api.runtime.getURL("assets/bgm.json"))).json(),
      connected: Boolean(await get("session")),
      voiceReady: Boolean(await get("voiceProxy")),
    };
  }
  if (message.type === "openSettings") {
    try {
      await api.action.openPopup();
      return true;
    } catch {
      throw new Error(
        "Bấm biểu tượng Vocalm trên thanh công cụ rồi chọn Cài đặt.",
      );
    }
  }
  if (message.type === "youtubeCaptions")
    return youtubeCaptions(sender, message);
  if (message.type === "siteCaptions") return siteCaptions(message, sender);
  if (message.type === "job")
    return backend("POST", "/v1/jobs", message.payload, message.idem);
  if (message.type === "windowJob")
    return backend("POST", "/v1/windows", message.payload, message.idem);
  if (message.type === "summary" || message.type === "chat")
    return backend(
      "POST",
      "/v1/" + message.type,
      message.payload,
      message.idem,
    );
  if (message.type === "pollJob" || message.type === "cancelJob") {
    if (!/^[a-f0-9]{32}$/.test(message.id)) throw new Error("Invalid job ID.");
    return backend(
      message.type === "pollJob" ? "GET" : "DELETE",
      "/v1/jobs/" + message.id,
    );
  }
  if (message.type === "cachedAudio")
    return A.cache.get("audio:" + message.key);
  if (message.type === "prepareVoice")
    return voiceTransport.prepare(message.voiceId);
  if (message.type === "synthesize") {
    if (
      typeof message.text !== "string" ||
      message.text.length > 800 ||
      !/^[a-f0-9]{64}$/.test(message.idem)
    )
      throw new Error("Invalid synthesis request.");
    return voiceTransport.synthesize(message);
  }
  if (message.type === "voiceIdentity") {
    const ref = await reference(message.voiceId);
    return A.sha256(ref.hash + ref.reference_text);
  }
  if (message.type === "pollAudio" || message.type === "cancelAudio") {
    if (!/^[a-f0-9]{64}$/.test(message.id))
      throw new Error("Invalid synthesis ID.");
    const result =
      message.type === "pollAudio"
        ? await voiceTransport.poll(message.id)
      : await voiceTransport.cancel(message.id);
    if (
      message.type === "pollAudio" &&
      result.state === "done" &&
      /^[a-f0-9]{64}$/.test(message.key)
    ) {
      await A.cache
        .put("audio:" + message.key, result, result.audio.length)
        .catch(() => {});
    }
    return result;
  }
  if (!trusted)
    throw new Error("Open the extension settings to perform this operation.");
  if (message.type === "activate") {
    const origin = A.endpoint(message.backend);
    const session = await fetchJson(origin + "/v1/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: message.code.trim() }),
    });
    session.clockOffset = session.server_time * 1000 - Date.now();
    await api.storage.local.set({
      settings: { ...conf, backend: origin },
      session,
    });
    return { expires: session.ticket_expires };
  }
  if (message.type === "saveSettings") {
    const next = { ...conf };
    for (const key of ["model", "asr", "language", "voiceId", "subtitleMode"])
      if (typeof message.values[key] === "string")
        next[key] = message.values[key];
    if (message.values.voiceEndpoint)
      next.voiceEndpoint = A.endpoint(message.values.voiceEndpoint, true);
    await api.storage.local.set({ settings: next });
    return true;
  }
  if (message.type === "connectVoice") {
    const origin = A.endpoint(message.endpoint, true);
    if (!/^wk-[\w-]+$/.test(message.id) || !/^ws-[\w-]+$/.test(message.secret))
      throw new Error("Use Modal workspace proxy credentials (wk-/ws-).");
    const health = await fetchJson(origin + "/v1/health", {
      headers: { "Modal-Key": message.id, "Modal-Secret": message.secret },
    });
    if (health.engine !== "omnivoice" || health.single_voice !== true)
      throw new Error("Unexpected voice worker.");
    await api.storage.local.set({
      voiceProxy: { id: message.id, secret: message.secret },
      settings: { ...conf, voiceEndpoint: origin },
    });
    return true;
  }
  if (message.type === "customVoice") {
    if (
      typeof message.reference !== "string" ||
      message.reference.length > 5600000 ||
      typeof message.text !== "string" ||
      !message.text.trim() ||
      message.text.length > 1200
    )
      throw new Error("Invalid voice reference.");
    const bytes = Uint8Array.from(atob(message.reference), (c) =>
      c.charCodeAt(0),
    );
    if (new TextDecoder().decode(bytes.slice(0, 4)) !== "RIFF")
      throw new Error("WAV required.");
    await api.storage.local.set({
      customVoice: {
        reference: message.reference,
        reference_text: message.text.trim(),
        hash: await A.sha256(bytes),
      },
      settings: { ...conf, voiceId: "custom" },
    });
    return true;
  }
  if (message.type === "deployVoice") {
    const credentials = message.command
      ? A.parseModal(message.command)
      : message.credentials;
    if (
      !/^ak-[\w-]+$/.test(credentials?.token_id) ||
      !/^as-[\w-]+$/.test(credentials?.token_secret) ||
      !["T4", "L4"].includes(message.gpu)
    )
      throw new Error("Invalid Modal credentials or GPU.");
    return api.runtime.sendNativeMessage("com.auvirel.modal", {
      operation: "start",
      credentials,
      gpu: message.gpu,
    });
  }
  if (message.type === "deployStatus") {
    const result = await api.runtime.sendNativeMessage("com.auvirel.modal", {
      operation: "status",
    });
    if (result.state === "done") {
      await api.storage.local.set({
        voiceProxy: { id: result.proxy_id, secret: result.proxy_secret },
        settings: { ...conf, voiceEndpoint: A.endpoint(result.endpoint, true) },
      });
      return { state: "done", endpoint: result.endpoint };
    }
    return result;
  }
  if (message.type === "clearCache") {
    await A.cache.clear();
    return true;
  }
  if (message.type === "disconnect") {
    await api.storage.local.remove(["session", "voiceProxy"]);
    return true;
  }
  throw new Error("Unsupported operation.");
}
api.runtime.onMessage.addListener((message, sender, respond) => {
  handle(message, sender).then(
    (value) => respond({ ok: true, value }),
    (error) =>
      respond({ ok: false, error: error.message || "Operation failed." }),
  );
  return true;
});

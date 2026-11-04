"use strict";
document.documentElement.classList.toggle(
  "embedded",
  new URLSearchParams(location.search).has("embedded"),
);
const api = globalThis.browser || chrome,
  $ = (id) => document.getElementById(id);
const send = async (message) => {
  const result = await api.runtime.sendMessage(message);
  if (!result?.ok) throw new Error(result?.error || "Extension unavailable.");
  return result.value;
};
function status(text, failed = false) {
  $("status").textContent = text;
  $("status").dataset.error = failed;
}
const fail = (error) => status(error.message, true);
if (document.documentElement.classList.contains("embedded")) {
  for (const [index, section] of [
    ...document.querySelectorAll(".grid > section"),
  ].entries()) {
    const details = document.createElement("details"),
      summary = document.createElement("summary"),
      heading = section.querySelector("h2");
    details.className = "connection-details";
    details.open = index === 0;
    summary.textContent = heading.textContent;
    heading.remove();
    details.append(summary, ...section.childNodes);
    section.append(details);
  }
}
let catalog = [],
  deploymentTimer;
async function initialize() {
  const conf = await send({ type: "publicSettings" });
  for (const key of ["backend", "language", "model", "asr"])
    $(key).value = conf[key];
  $("endpoint").value = conf.voiceEndpoint;
  $("subtitle-mode").value = conf.subtitleMode;
  $("voice").replaceChildren(
    ...conf.voices.map((voice) => {
      const option = document.createElement("option");
      option.value = voice.id;
      option.textContent = voice.name;
      return option;
    }),
  );
  $("voice").value = conf.voiceId;
  catalog = await (
    await fetch(api.runtime.getURL("assets/presets.json"))
  ).json();
  if (conf.connected)
    $("expiry").textContent = "Ticket đã kết nối trên thiết bị này.";
  status(
    conf.connected
      ? conf.voiceReady
        ? "Ticket & giọng đọc đã kết nối."
        : "Ticket đã kết nối. Thêm giọng đọc để bắt đầu."
      : "Kết nối Ticket và giọng đọc của bạn.",
  );
}
function form(id, action) {
  $(id).onsubmit = async (event) => {
    event.preventDefault();
    const button = event.submitter;
    button.disabled = true;
    try {
      await action();
    } catch (error) {
      fail(error);
    } finally {
      button.disabled = false;
    }
  };
}
form("access-form", async () => {
  const result = await send({
    type: "activate",
    backend: $("backend").value,
    code: $("ticket").value,
  });
  $("ticket").value = "";
  $("expiry").textContent =
    "Access expires " + new Date(result.expires * 1000).toLocaleString();
  status("Access activated.");
});
async function pollDeployment() {
  try {
    const result = await send({ type: "deployStatus" });
    $("deployment").textContent = result.stage || result.error || result.state;
    if (result.state === "done") {
      clearInterval(deploymentTimer);
      $("endpoint").value = result.endpoint;
      status("OmniVoice deployed and connected.");
    }
    if (result.state === "failed" || result.state === "idle")
      clearInterval(deploymentTimer);
  } catch (error) {
    clearInterval(deploymentTimer);
    fail(error);
  }
}
form("deploy-form", async () => {
  const result = await send({
    type: "deployVoice",
    command: $("command").value.trim(),
    credentials: {
      token_id: $("token-id").value.trim(),
      token_secret: $("token-secret").value.trim(),
    },
    gpu: $("gpu").value,
  });
  $("command").value = "";
  $("token-id").value = "";
  $("token-secret").value = "";
  if (result.state === "failed") throw new Error(result.error);
  status("Deployment started on this computer.");
  clearInterval(deploymentTimer);
  deploymentTimer = setInterval(pollDeployment, 2000);
  await pollDeployment();
});
form("endpoint-form", async () => {
  await send({
    type: "connectVoice",
    endpoint: $("endpoint").value.trim(),
    id: $("proxy-id").value.trim(),
    secret: $("proxy-secret").value.trim(),
  });
  $("proxy-id").value = "";
  $("proxy-secret").value = "";
  status("Voice worker verified and connected.");
});
form("defaults-form", async () => {
  await send({
    type: "saveSettings",
    values: {
      language: $("language").value,
      model: $("model").value,
      asr: $("asr").value,
      voiceId: $("voice").value,
      subtitleMode: $("subtitle-mode").value,
    },
  });
  status("Preferences saved.");
});
$("voice").onchange = () =>
  send({ type: "saveSettings", values: { voiceId: $("voice").value } }).catch(
    fail,
  );
$("preview").onclick = () => {
  const preset = catalog.find((row) => row.id === $("voice").value);
  if (!preset)
    return status("Personal voice preview is available in the source WAV.");
  $("sample").src = api.runtime.getURL("assets/" + preset.path);
  $("sample").hidden = false;
  $("sample").play().catch(fail);
};
form("voice-form", async () => {
  const file = $("wav").files[0];
  if (!file || file.size > 4 * 1024 ** 2)
    throw new Error("WAV must be at most 4 MiB.");
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (
    new TextDecoder().decode(bytes.slice(0, 4)) !== "RIFF" ||
    new TextDecoder().decode(bytes.slice(8, 12)) !== "WAVE"
  )
    throw new Error("A RIFF WAV file is required.");
  const context = new AudioContext();
  let buffer;
  try {
    buffer = await context.decodeAudioData(bytes.buffer.slice(0));
  } finally {
    await context.close();
  }
  if (
    buffer.duration < 1 ||
    buffer.duration > 30 ||
    buffer.numberOfChannels > 2
  )
    throw new Error("Use a mono/stereo sample between 1 and 30 seconds.");
  // Normalize arbitrary decoded WAV to PCM16 mono; the CPU ingress validates this format.
  const samples = buffer.getChannelData(0),
    pcm = new ArrayBuffer(44 + samples.length * 2),
    view = new DataView(pcm);
  const text = (offset, value) =>
    [...value].forEach((character, i) =>
      view.setUint8(offset + i, character.charCodeAt(0)),
    );
  text(0, "RIFF");
  view.setUint32(4, pcm.byteLength - 8, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, buffer.sampleRate, true);
  view.setUint32(28, buffer.sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    if (!Number.isFinite(samples[i])) throw new Error("Invalid waveform.");
    view.setInt16(
      44 + i * 2,
      Math.round(Math.max(-1, Math.min(1, samples[i])) * 32767),
      true,
    );
  }
  const normalized = new Uint8Array(pcm);
  let binary = "";
  for (let offset = 0; offset < normalized.length; offset += 8192)
    binary += String.fromCharCode(
      ...normalized.subarray(offset, offset + 8192),
    );
  await send({
    type: "customVoice",
    reference: btoa(binary),
    text: $("reference-text").value,
  });
  status("Personal voice saved.");
  await initialize();
});
$("clear").onclick = () =>
  send({ type: "clearCache" })
    .then(() => status("Audio cache cleared."))
    .catch(fail);
$("disconnect").onclick = () =>
  send({ type: "disconnect" })
    .then(() => status("Access and voice credentials disconnected."))
    .catch(fail);
initialize().catch(fail);

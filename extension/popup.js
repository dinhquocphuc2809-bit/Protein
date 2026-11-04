"use strict";
const api = globalThis.browser || chrome,
  A = globalThis.Auvirel,
  $ = (id) => document.getElementById(id);
let target = null,
  frameId = 0,
  pageReady = false,
  polling = false;
let activeView = "listen",
  readyToPlay = false;
const voicePicker = new A.VoicePicker($("voice"));
const send = async (message) => {
  const result = await api.runtime.sendMessage(message);
  if (!result?.ok)
    throw new Error(result?.error || "Không thể kết nối extension.");
  return result.value;
};
function status(text, failed = false) {
  $("status").textContent = text;
  $("status").dataset.error = failed;
}
const fail = (error) => status(error.message, true);
async function player(command, values = {}) {
  if (!target) throw new Error("Hãy mở một trang có video.");
  const response = await api.tabs.sendMessage(
    target,
    { type: "veloaPlayer", command, ...values },
    { frameId },
  );
  if (!response?.ok)
    throw new Error(
      response?.error ||
        "Không tìm thấy video. Hãy tải lại trang sau khi cập nhật extension.",
    );
  return response.value;
}
function fill(select, values, selected) {
  select.replaceChildren(
    ...values.map(({ id, name, gender, baseId }) => {
      const option = document.createElement("option");
      option.value = id;
      option.textContent = name;
      if (gender) option.dataset.gender = gender;
      if (baseId) option.dataset.baseId = baseId;
      return option;
    }),
  );
  select.value = selected;
  if (!select.value && values.length) select.value = values[0].id;
}
function settingsView(open) {
  $("home").hidden = open;
  $("preferences").hidden = !open;
  $("settings").setAttribute("aria-pressed", String(open));
  if (open && !$("settings-frame").getAttribute("src"))
    $("settings-frame").src = "options.html?embedded=1";
  if (!open) initialize(false).catch(fail);
  document
    .querySelectorAll("[data-view]")
    .forEach((button) =>
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.view === (open ? "account" : activeView)),
      ),
    );
}
document.querySelectorAll("[data-view]").forEach((button) => {
  button.onclick = () => {
    const view = button.dataset.view;
    if (view !== "account") {
      activeView = view;
      $("listen-view").hidden = view !== "listen";
      $("sound-view").hidden = view !== "sound";
    }
    settingsView(view === "account");
  };
});
$("settings").onclick = () => settingsView($("preferences").hidden);
$("back").onclick = () => settingsView(false);
async function refresh() {
  if (polling || !target) return;
  polling = true;
  try {
    const state = await player("state");
    pageReady = state.available;
    readyToPlay = Boolean(state.ready);
    $("video-title").textContent = state.title || "Mở một video để bắt đầu";
    $("video-title").title = state.title || "";
    $("start").disabled = !pageReady || state.busy;
    $("use-asr").hidden = !state.asrAvailable;
    $("use-asr").disabled = state.busy;
    $("stop").disabled = !state.running && !state.busy;
    $("start").querySelector("span").textContent = state.busy
      ? "Đang chuẩn bị…"
      : state.ready
        ? "Sẵn sàng · Phát video"
        : state.cueCount
          ? "Tiếp tục lồng tiếng"
          : "Lồng tiếng";
    if (state.busy || state.running || state.error)
      status(
        state.ready
          ? "Đã sẵn sàng. Bấm phát để bắt đầu nghe."
          : {
              "Single voice - complete sentences":
                "Đang lồng tiếng · Đọc trọn câu",
              "Reading the available subtitles": "Đang lấy phụ đề có sẵn…",
              "Preparing the first complete sentence":
                "Đang chuẩn bị câu đầu tiên…",
              "Preparing the next complete sentence":
                "Đang chuẩn bị câu kế tiếp…",
              "Translating the current sentence": "Đang dịch đoạn đang xem…",
            }[state.status] || state.status,
        Boolean(state.error),
      );
    $("ready-label").textContent = state.cueCount
      ? `${state.preparedCount ?? state.cueCount}/${state.cueCount} cụm lời đã dịch · Chuẩn bị theo vùng xem`
      : "Dành cho khoảnh khắc bạn muốn hiểu hơn.";
  } catch {
    pageReady = false;
    $("start").disabled = true;
  } finally {
    polling = false;
  }
}
async function initialize(first = true) {
  const conf = await send({ type: "publicSettings" });
  fill($("voice"), conf.voices, conf.voiceId);
  fill(
    $("bgm"),
    [
      { id: "", name: "Tắt" },
      ...conf.bgm.map((x) => ({ id: x.path, name: x.name })),
    ],
    "",
  );
  for (const key of ["language", "model", "asr"]) $(key).value = conf[key];
  $("mode").value = conf.subtitleMode;
  const connected = conf.connected && conf.voiceReady;
  $("connection-dot").dataset.ready = connected;
  $("connection-text").textContent = connected
    ? "Ticket & giọng đọc đã kết nối"
    : conf.connected
      ? "Kết nối giọng đọc trong Cài đặt"
      : "Nhập Ticket trong Cài đặt để bắt đầu";
  if (first) {
    const tabs = await api.tabs.query({ active: true, currentWindow: true });
    target = tabs[0]?.id;
    try {
      const frames = await api.scripting.executeScript({
        target: { tabId: target, allFrames: true },
        func: () =>
          Math.max(
            0,
            ...(
              globalThis.VeloaMedia?.videos() || [
                ...document.querySelectorAll("video"),
              ]
            ).map((v) => {
              const r = v.getBoundingClientRect();
              return r.width > 100 && r.height > 60 ? r.width * r.height : 0;
            }),
          ),
      });
      frameId = frames.sort((a, b) => b.result - a.result)[0]?.frameId || 0;
    } catch {}
  }
  try {
    const state = await player("state");
    if (state.values)
      for (const [key, value] of Object.entries(state.values))
        if (
          $(key) &&
          (first || ["original", "dub", "music", "bgm"].includes(key))
        )
          $(key).value = value;
    $("translated").checked = Boolean(state.translated);
    for (const key of ["original", "dub", "music"])
      $(key + "-value").textContent = $(key).value + "%";
  } catch {}
  await refresh();
  voicePicker.refresh();
}
const values = () =>
  Object.fromEntries(
    [
      "voice",
      "language",
      "mode",
      "model",
      "asr",
      "original",
      "dub",
      "music",
      "bgm",
    ].map((key) => [key, $(key).value]),
  );
async function configure() {
  await send({
    type: "saveSettings",
    values: {
      voiceId: $("voice").value,
      language: $("language").value,
      model: $("model").value,
      asr: $("asr").value,
      subtitleMode: $("mode").value,
    },
  });
  if (pageReady) await player("configure", { values: values() });
}
for (const key of ["voice", "language", "mode", "model", "asr", "bgm"])
  $(key).onchange = () => configure().catch(fail);
for (const key of ["original", "dub", "music"])
  $(key).oninput = () => {
    $(key + "-value").textContent = $(key).value + "%";
    if (pageReady)
      player("volume", { key, value: Number($(key).value) }).catch(fail);
  };
$("start").onclick = async () => {
  $("start").disabled = true;
  try {
    if (!readyToPlay) await configure();
    await player("start");
    status("Đang chuẩn bị phụ đề và giọng đọc…");
    await refresh();
  } catch (error) {
    fail(error);
    $("start").disabled = !pageReady;
  }
};
$("use-asr").onclick = () => player("asr").then(refresh).catch(fail);
$("stop").onclick = () =>
  player("stop")
    .then(() => {
      status("Đã dừng lồng tiếng.");
      return refresh();
    })
    .catch(fail);
$("srt").onchange = async (event) => {
  try {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 2 * 1024 ** 2) throw new Error("SRT tối đa 2 MiB.");
    const text = new TextDecoder("utf-8", { fatal: true }).decode(
      await file.arrayBuffer(),
    );
    A.parseSrt(text);
    await player("import", { text, translated: $("translated").checked });
    $("file-name").textContent = file.name;
    status("Đã nhập phụ đề.");
  } catch (error) {
    fail(error);
  }
};
$("translated").onchange = () =>
  player("translated", { value: $("translated").checked }).catch(fail);
document.querySelectorAll("[data-section]").forEach(
  (button) =>
    (button.onclick = () =>
      player("show", { section: button.dataset.section })
        .then(() =>
          status("Đã mở " + button.textContent.trim() + " trên trang video."),
        )
        .catch(fail)),
);
initialize().catch(fail);
setInterval(refresh, 1000);

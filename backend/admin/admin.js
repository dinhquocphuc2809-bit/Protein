"use strict";
const $ = (id) => document.getElementById(id);
let token = "";
function status(text, error = false) {
  $("status").textContent = text;
  $("status").classList.toggle("error", error);
}
async function api(path, method = "GET", body) {
  const response = await fetch("/admin/" + path, {
    method,
    headers: {
      Authorization: "Bearer " + token,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(30000),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string" ? data.detail : "Yêu cầu không hợp lệ",
    );
  return data;
}
function node(tag, text, cls) {
  const el = document.createElement(tag);
  if (text != null) el.textContent = String(text);
  if (cls) el.className = cls;
  return el;
}
function action(text, callback, danger = false) {
  const button = node("button", text, danger ? "danger" : "");
  button.type = "button";
  button.addEventListener("click", () => guarded(callback));
  return button;
}
async function guarded(callback) {
  try {
    status("Đang xử lý…");
    await callback();
    status("Đã cập nhật.");
  } catch (error) {
    status(error.message, true);
  }
}
const date = (value) =>
  value ? new Date(value * 1000).toLocaleString("vi-VN") : "Chưa kích hoạt";
const gib = (bytes) => (bytes / 1073741824).toFixed(1) + " GiB";
function row(values) {
  const tr = node("tr");
  for (const value of values) {
    const td = node("td");
    if (value instanceof Node) td.append(value);
    else td.textContent = String(value ?? "—");
    tr.append(td);
  }
  return tr;
}
async function refresh() {
  const [stats, tickets, keys, jobs] = await Promise.all([
    api("stats"),
    api("tickets"),
    api("keys"),
    api("jobs"),
  ]);
  const system = stats.system;
  const hits = stats.cache_events.find((x) => x.event === "hit")?.count || 0;
  const total = stats.cache_events.reduce((sum, x) => sum + x.count, 0);
  $("metrics").replaceChildren(
    ...[
      ["CPU", system.cpu_percent.toFixed(1) + "%", "Tải hệ thống hiện tại"],
      ["Bộ nhớ", gib(system.memory_used), "/ " + gib(system.memory_total)],
      [
        "Ổ đĩa còn trống",
        gib(system.disk_free),
        "Tổng " + gib(system.disk_total),
      ],
      [
        "Cache hit",
        total ? Math.round((hits / total) * 100) + "%" : "—",
        stats.cache.entries + " mục đã lưu",
      ],
    ].map(([label, value, detail]) => {
      const card = node("article", null, "metric");
      card.append(
        node("span", label),
        node("strong", value),
        node("small", detail),
      );
      return card;
    }),
  );
  $("tickets").replaceChildren(
    ...tickets.map((ticket) => {
      const actions = node("div");
      actions.append(
        action(ticket.active ? "Khóa" : "Mở", async () => {
          await api("tickets/" + ticket.id, "PATCH", {
            active: !ticket.active,
          });
          await refresh();
        }),
        action("+30 ngày", async () => {
          await api("tickets/" + ticket.id, "PATCH", {
            extend_seconds: 2592000,
          });
          await refresh();
        }),
        action(
          "Xóa",
          async () => {
            if (
              confirm(
                "Xóa quyền truy cập Ticket này? Lịch sử sử dụng được giữ lại.",
              )
            ) {
              await api("tickets/" + ticket.id, "DELETE");
              await refresh();
            }
          },
          true,
        ),
      );
      const usage = node(
        "span",
        `${ticket.jobs} jobs / ${Math.round(ticket.asr_seconds)}s ASR / ${ticket.translated_cues} cues / ${ticket.cache_hits} cache hits`,
      );
      return row([
        ticket.label,
        node(
          "span",
          ticket.active ? "Hoạt động" : "Đã khóa",
          "badge" + (ticket.active ? "" : " bad"),
        ),
        date(ticket.expires),
        usage,
        actions,
      ]);
    }),
  );
  $("keys").replaceChildren(
    ...keys.map((key) => {
      const actions = node("div");
      actions.append(
        action("Thử lại", async () => {
          await api("keys/" + key.id + "/enable", "POST");
          await refresh();
        }),
        action(
          "Xóa",
          async () => {
            if (confirm("Xóa khóa dịch vụ này?")) {
              await api("keys/" + key.id, "DELETE");
              await refresh();
            }
          },
          true,
        ),
      );
      return row([
        key.provider,
        key.label,
        node(
          "span",
          key.state,
          "badge" + (key.state === "available" ? "" : " bad"),
        ),
        key.balance ?? "Chưa xác minh",
        key.calls,
        actions,
      ]);
    }),
  );
  $("jobs").replaceChildren(
    ...jobs.map((job) =>
      row([
        job.title || job.kind,
        job.state,
        job.stage,
        date(job.created),
        job.error || "—",
      ]),
    ),
  );
}
$("login-form").addEventListener("submit", (event) => {
  event.preventDefault();
  guarded(async () => {
    token = $("admin-token").value;
    await refresh();
    $("admin-token").value = "";
    $("login").hidden = true;
    $("workspace").hidden = false;
  });
});
$("logout").addEventListener("click", () => {
  token = "";
  $("workspace").hidden = true;
  $("login").hidden = false;
  $("new-ticket").textContent = "";
  $("key-form").reset();
  status("Bảng điều khiển đã khóa.");
});
$("refresh").addEventListener("click", () => guarded(refresh));
const balanceButton = action("Refresh balances", async () => {
  await api("balances", "POST");
  status("Balance refresh started; use refresh to read the results.");
});
$("tab-keys").insertBefore(balanceButton, $("key-form"));
document.querySelectorAll("[data-tab]").forEach((button) =>
  button.addEventListener("click", () => {
    document
      .querySelectorAll("[data-tab]")
      .forEach((item) =>
        item.setAttribute("aria-selected", String(item === button)),
      );
    document
      .querySelectorAll(".tab-panel")
      .forEach(
        (panel) => (panel.hidden = panel.id !== "tab-" + button.dataset.tab),
      );
  }),
);
$("ticket-form").addEventListener("submit", (event) => {
  event.preventDefault();
  guarded(async () => {
    const data = new FormData(event.target);
    const result = await api("tickets", "POST", {
      label: data.get("label"),
      duration: Number(data.get("days")) * 86400,
    });
    $("new-ticket").hidden = false;
    $("new-ticket").textContent = "Chỉ hiển thị một lần: " + result.code;
    await refresh();
  });
});
$("key-form").addEventListener("submit", (event) => {
  event.preventDefault();
  guarded(async () => {
    const data = new FormData(event.target);
    await api("keys", "POST", {
      provider: data.get("provider"),
      label: data.get("label"),
      values: String(data.get("values"))
        .split(/\r?\n/)
        .map((x) => x.trim())
        .filter(Boolean),
    });
    event.target.elements.values.value = "";
    await refresh();
  });
});
$("load-models").addEventListener("click", () =>
  guarded(async () => {
    const models = await api("models");
    for (const selection of ["basic", "advanced", "deepseek"]) {
      const select = $("model-form").elements[selection];
      const options = models[selection === "deepseek" ? "deepseek" : "gemini"];
      select.replaceChildren(
        ...options.map((model) => {
          const option = node("option", model);
          option.value = model;
          return option;
        }),
      );
      select.value =
        selection === "basic"
          ? "gemini-3.5-flash-lite"
          : selection === "advanced"
            ? "gemini-3.8-flash"
            : "deepseek-flash";
    }
    $("model-form").hidden = false;
  }),
);
$("model-form").addEventListener("submit", (event) => {
  event.preventDefault();
  guarded(async () => {
    await api("models", "POST", Object.fromEntries(new FormData(event.target)));
  });
});

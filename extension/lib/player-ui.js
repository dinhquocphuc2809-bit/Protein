(() => {
  "use strict";
  const A = globalThis.Auvirel,
    api = globalThis.browser || chrome;
  class PlayerUI {
    constructor(shadow, { start, stop, ready, configure, source, show, fail }) {
      Object.assign(this, {
        shadow,
        start,
        stop,
        ready,
        configure,
        source,
        show,
        fail,
      });
      this.stage = "";
      this.adUntil = 0;
      this.wasAd = false;
      const layer = document.createElement("div");
      layer.className = "auvirel-root";
      layer.innerHTML = `<section class="preparation" hidden role="dialog" aria-modal="true" aria-label="Chuẩn bị lồng tiếng">
        <div class="grove-card"><span class="grove-eyebrow">VOCALM · A LITTLE ROOM TO GROW</span>
        <svg class="grove" viewBox="0 0 240 150" aria-hidden="true">
          <ellipse cx="120" cy="134" rx="87" ry="9" fill="#dbe7d3"/>
          <g class="shoot shoot-one"><path d="M64 134Q49 101 67 65Q86 101 72 134" fill="#83a977"/><path d="m67 77 2 57m-16-27 15 8 13-9m-24-15 11 7 9-9" stroke="#f0f5dd" stroke-width="2" fill="none"/></g>
          <g class="shoot shoot-two"><path d="M112 134Q91 86 121 21Q146 82 128 134" fill="#4c7852"/><path d="m121 36-1 98m-20-44 20 10 20-12m-36-19 17 10 16-12m-29-18 13 8 9-10" stroke="#c9ddb2" stroke-width="2" fill="none"/><path class="leaf" d="M122 66Q151 28 177 40Q160 64 122 66" fill="#91b376"/></g>
          <g class="shoot shoot-three"><path d="M166 134Q150 104 171 78Q185 110 176 134" fill="#a1b983"/><path d="m171 91 0 43m-15-23 15 7 12-10" stroke="#f4f4d7" stroke-width="2" fill="none"/></g>
        </svg>
        <h2 class="grove-title" aria-live="polite">Đang tìm phụ đề</h2>
        <p class="grove-detail" role="status">Chuẩn bị đoạn bạn sắp xem.</p>
        <ol class="grove-steps" aria-label="Tiến trình"><li data-step="captions"><span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 6h14M5 12h14M5 18h9"/></svg></span>Phụ đề</li><li data-step="translation"><span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h12M9 3v3m-4 4 8 8M13 6c-1 7-5 10-9 12m11 3 4-11 4 11m-6-4h4"/></svg></span>Bản dịch</li><li data-step="voice"><span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10v4m5-8v12m5-15v18m5-13v8"/></svg></span>Giọng đọc</li></ol>
        <button class="grove-ready" hidden>Sẵn sàng · Phát video <span aria-hidden="true">▶</span></button>
        <button class="grove-cancel">Hủy chuẩn bị</button></div></section>
        <section class="quick-menu" hidden role="dialog" aria-label="Điều khiển Vocalm"><header><img src="${api.runtime.getURL("icons/icon-48.png")}" width="32" height="32" alt=""><strong>Vocalm</strong><button class="quick-close" aria-label="Đóng">×</button></header><div class="quick-fields"></div><div class="quick-actions"><button class="quick-start">Lồng tiếng</button><button class="quick-stop" aria-label="Dừng lồng tiếng">■ Dừng</button></div><div class="quick-study"><button data-show="transcript">Phụ đề</button><button data-show="summary">Tóm tắt</button><button data-show="chat">Hỏi AI</button></div></section>`;
      shadow.append(layer);
      this.gate = layer.querySelector(".preparation");
      this.menu = layer.querySelector(".quick-menu");
      this.gate.querySelector(".grove-cancel").onclick = () => stop();
      this.gate.querySelector(".grove-ready").onclick = () => ready();
      this.menu.querySelector(".quick-close").onclick = () =>
        this.toggle(false);
      this.menu.querySelector(".quick-start").onclick = () => {
        this.toggle(false);
        start();
      };
      this.menu.querySelector(".quick-stop").onclick = () => stop();
      for (const button of this.menu.querySelectorAll("[data-show]"))
        button.onclick = () => {
          this.toggle(false);
          show(button.dataset.show);
        };
      for (const area of [this.gate, this.menu]) {
        area.addEventListener("keydown", (event) => {
          event.stopPropagation();
          if (event.key === "Escape") {
            event.preventDefault();
            area === this.menu ? this.toggle(false) : stop();
          }
          if (event.key === "Tab") {
            const nodes = [
              ...area.querySelectorAll("button, select, input"),
            ].filter((n) => !n.disabled && n.getClientRects().length);
            const first = nodes[0],
              last = nodes.at(-1);
            if (event.shiftKey && shadow.activeElement === first) {
              event.preventDefault();
              last?.focus();
            } else if (!event.shiftKey && shadow.activeElement === last) {
              event.preventDefault();
              first?.focus();
            }
          }
        });
      }
      // Capturing prevents the mixer's play handler from starting behind the gate.
      document.addEventListener(
        "play",
        (event) => {
          if (event.target === this.video && this.stage && !this.adActive()) {
            event.stopImmediatePropagation();
            this.video.pause();
          }
        },
        true,
      );
      document.addEventListener(
        "pointerdown",
        (event) => {
          if (
            !this.menu.hidden &&
            !event.composedPath().includes(shadow.host) &&
            !event.composedPath().includes(this.button)
          )
            this.toggle(false);
        },
        true,
      );
    }
    adActive() {
      if (!globalThis.VeloaMedia.youtubeId(location.href)) return false;
      const active = Boolean(
        document.querySelector(
          "#movie_player.ad-showing, #movie_player.ad-interrupting",
        ),
      );
      if (active) {
        this.wasAd = true;
        return true;
      }
      // Allow YouTube to restore the content source/time after removing ad classes.
      if (this.wasAd) {
        this.wasAd = false;
        this.adUntil = performance.now() + 500;
      }
      return performance.now() < this.adUntil;
    }
    setStage(stage, detail = "") {
      this.stage = stage;
      this.gate.dataset.stage = stage;
      this.gate.querySelector(".grove-title").textContent =
        {
          captions: "Đang tìm phụ đề",
          translation: "Đang dịch theo ngữ cảnh",
          voice: "Đang chuẩn bị giọng đọc",
          ready: "Một nhịp thở. Sẵn sàng.",
        }[stage] || "";
      this.gate.querySelector(".grove-detail").textContent =
        detail ||
        (stage === "ready"
          ? "Các đoạn tiếp theo sẽ được chuẩn bị khi bạn xem."
          : "Chuẩn bị đoạn bạn sắp xem.");
      const index = ["captions", "translation", "voice", "ready"].indexOf(
        stage,
      );
      this.gate.querySelectorAll("[data-step]").forEach((node, i) => {
        node.dataset.state =
          i < index ? "done" : i === index ? "active" : "pending";
        node.setAttribute("aria-current", String(i === index));
      });
      const ready = this.gate.querySelector(".grove-ready");
      ready.hidden = stage !== "ready";
      this.gate.querySelector(".grove-cancel").textContent =
        stage === "ready" ? "Đóng lồng tiếng" : "Hủy chuẩn bị";
      if (stage && !this.adActive()) this.video?.pause();
      this.layout();
      if (stage === "ready" && !this.adActive())
        ready.focus({ preventScroll: true });
      if (stage === "captions")
        this.gate.querySelector(".grove-cancel").focus({ preventScroll: true });
    }
    detail(text) {
      if (this.stage && this.stage !== "ready")
        this.gate.querySelector(".grove-detail").textContent =
          {
            "Reading the available subtitles":
              "Đang lấy phụ đề có sẵn trên video.",
            "Waiting for the server": "Đã gửi yêu cầu, đang chờ xử lý.",
            "Finding the audio source": "Đang tìm nguồn âm thanh.",
            "Recognizing speech": "Đang nhận diện lời nói.",
            "Aligning words to the video":
              "Đang căn thời gian lời nói với video.",
            "Translating with context": "Đang dịch đoạn bạn sắp xem.",
            "Preparing the first complete sentence":
              "Đang tạo giọng cho câu đầu tiên.",
          }[text] || text;
    }
    mount(video) {
      this.video = video;
      const controls = document.querySelector(
        "#movie_player .ytp-right-controls",
      );
      if (controls && globalThis.VeloaMedia.youtubeId(location.href)) {
        if (!this.button) {
          this.button = document.createElement("button");
          this.button.className = "ytp-button vocalm-player-button";
          this.button.title = "Vocalm · Giọng đọc & phụ đề";
          this.button.setAttribute("aria-label", this.button.title);
          this.button.setAttribute("aria-haspopup", "dialog");
          this.button.style.cssText =
            "width:44px;height:100%;display:inline-grid;place-items:center;vertical-align:top";
          const img = document.createElement("img");
          img.src = api.runtime.getURL("icons/icon-48.png");
          img.alt = "";
          img.style.cssText =
            "width:30px;height:30px;object-fit:contain;pointer-events:none";
          this.button.append(img);
          this.button.onclick = (e) => {
            e.stopPropagation();
            this.toggle(this.menu.hidden);
          };
        }
        if (this.button.parentElement !== controls)
          controls.prepend(this.button);
      } else this.button?.remove();
      this.layout();
    }
    toggle(open) {
      this.menu.hidden = !open;
      this.button?.setAttribute("aria-expanded", String(open));
      if (!open) return;
      const fields = this.menu.querySelector(".quick-fields");
      fields.replaceChildren();
      for (const [key, title] of [
        ["voice", "Giọng đọc"],
        ["language", "Dịch sang"],
        ["mode", "Phụ đề"],
        ["original", "Video gốc"],
        ["dub", "Lồng tiếng"],
        ["music", "Nhạc nền"],
        ["bgm", "Bản nhạc"],
      ]) {
        const label = document.createElement("label"),
          text = document.createElement("span"),
          control = this.source(key).cloneNode(true);
        text.textContent = title;
        control.id = "quick-" + key;
        control.value = this.source(key).value;
        for (const option of control.options || []) {
          option.textContent =
            {
              Vietnamese: "Tiếng Việt",
              Bilingual: "Song ngữ",
              Translation: "Bản dịch",
              Original: "Bản gốc",
              "Hide overlay": "Ẩn phụ đề",
              Off: "Tắt",
            }[option.textContent] || option.textContent;
        }
        label.append(text, control);
        fields.append(label);
        control[control.type === "range" ? "oninput" : "onchange"] = () =>
          this.configure({ [key]: control.value }).catch(this.fail);
        if (key === "voice") new A.VoicePicker(control);
      }
      this.menu.querySelector(".quick-start").disabled = Boolean(
        this.stage && this.stage !== "ready",
      );
      this.layout();
      this.menu.querySelector(".quick-close").focus();
    }
    layout() {
      const ad = this.adActive(),
        rect = this.video?.getBoundingClientRect();
      this.gate.hidden = !this.stage || ad || !rect || rect.width <= 0;
      if (this.stage && !ad && this.video && !this.video.paused)
        this.video.pause();
      if (rect) {
        Object.assign(this.gate.style, {
          left: Math.max(0, rect.left) + "px",
          top: Math.max(0, rect.top) + "px",
          width: Math.min(innerWidth, rect.width) + "px",
          height: Math.min(innerHeight, rect.height) + "px",
        });
        const anchor = this.button?.isConnected
          ? this.button.getBoundingClientRect()
          : rect;
        this.menu.style.right = Math.max(8, innerWidth - anchor.right) + "px";
        const bottom = Math.min(
          Math.max(8, innerHeight - 160),
          Math.max(
            8,
            innerHeight -
              (this.button?.isConnected ? anchor.top : rect.bottom) +
              8,
          ),
        );
        this.menu.style.bottom = bottom + "px";
        this.menu.style.maxHeight =
          Math.max(120, innerHeight - bottom - 8) + "px";
      }
    }
  }
  A.PlayerUI = PlayerUI;
})();

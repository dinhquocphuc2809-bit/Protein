(() => {
  "use strict";
  const A = globalThis.Auvirel,
    api = globalThis.browser || chrome;
  class BilingualSidebar {
    constructor({ seek, prepare, download }) {
      this.seek = seek;
      this.rows = [];
      this.active = -1;
      this.manualUntil = 0;
      this.heights = [];
      this.prefix = [0];
      this.range = "";
      this.owns = false;
      this.host = document.createElement("section");
      this.host.id = "veloa-bilingual-panel";
      this.host.setAttribute("aria-label", "Bilingual transcript");
      this.shadow = this.host.attachShadow({ mode: "closed" });
      const css = document.createElement("link");
      css.rel = "stylesheet";
      css.href = api.runtime.getURL("sidebar.css");
      this.shadow.append(css);
      const shell = document.createElement("section");
      shell.className = "shell";
      shell.innerHTML = `<div class="topline"></div><header class="header"><div class="brand" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 6.5h14M5 11h9M5 15.5h6m4 .5 2 2 4-5"/></svg></div><div class="title">Phụ đề song ngữ</div><button class="icon-btn download" aria-label="Download bilingual subtitles" title="Download bilingual subtitles"><svg viewBox="0 0 24 24"><path d="M12 3v12m0 0 4-4m-4 4-4-4M5 19h14"/></svg></button><div class="live"><span class="dot"></span>SYNC</div></header><section class="state"><strong>Phụ đề của bạn</strong><p>Phụ đề gốc và bản dịch xuất hiện ở đây.</p><button class="prepare">Chuẩn bị phụ đề</button></section><main class="transcript" aria-label="Full bilingual transcript" tabindex="0" hidden><div class="top-space"></div><div class="rows"></div><div class="bottom-space"></div></main><button class="follow" hidden>Theo video ↓</button>`;
      this.shadow.append(shell);
      this.list = this.shadow.querySelector(".transcript");
      this.container = this.shadow.querySelector(".rows");
      this.shadow.querySelector(".prepare").onclick = prepare;
      this.shadow.querySelector(".download").onclick = download;
      this.shadow.querySelector(".follow").onclick = () => {
        this.manualUntil = 0;
        this.follow();
      };
      for (const event of ["wheel", "touchmove", "pointerdown", "keydown"])
        this.list.addEventListener(
          event,
          () => {
            this.manualUntil = Date.now() + 2600;
          },
          { passive: true },
        );
      this.list.addEventListener("scroll", () => this.render(), {
        passive: true,
      });
      this.observer = new ResizeObserver((entries) => {
        let changed = false;
        const anchor = this.indexAt(this.list.scrollTop);
        const offset = this.list.scrollTop - (this.prefix[anchor] || 0);
        for (const entry of entries) {
          const index = Number(entry.target.dataset.index);
          const height =
            entry.borderBoxSize?.[0]?.blockSize ||
            entry.target.getBoundingClientRect().height;
          if (height <= 0 || index >= this.rows.length) continue;
          if (Math.abs((this.heights[index] || 88) - height) > 0.5) {
            this.heights[index] = height;
            changed = true;
          }
        }
        if (changed) {
          this.measure();
          this.spaces();
          // Keep the visible sentence anchored when estimated heights become exact.
          this.list.scrollTop = (this.prefix[anchor] || 0) + offset;
        }
      });
      this.nativeStyle = document.createElement("link");
      this.nativeStyle.rel = "stylesheet";
      this.nativeStyle.href = api.runtime.getURL("sidebar-page.css");
      document.documentElement.append(this.nativeStyle);
    }
    mount(mode) {
      const flexy = document.querySelector("ytd-watch-flexy");
      const normal =
        /(^|\.)youtube\.com$/.test(location.hostname) &&
        location.pathname === "/watch" &&
        innerWidth >= 980 &&
        !document.fullscreenElement &&
        flexy &&
        !flexy.hasAttribute("theater") &&
        !flexy.hasAttribute("fullscreen") &&
        !(
          flexy.hasAttribute("fixed-default-panels") &&
          flexy.hasAttribute("fixed-panel-expanded")
        );
      const docked = Boolean(
        normal &&
          mode === "bilingual" &&
          flexy.hasAttribute("fixed-default-panels"),
      );
      if (this.flexy && this.flexy !== flexy)
        this.flexy.removeAttribute("data-veloa-docked");
      this.flexy = flexy;
      flexy?.toggleAttribute("data-veloa-docked", docked);
      this.host.toggleAttribute("data-docked", docked);
      const parent = docked
        ? flexy
        : normal &&
          [
            "ytd-watch-flexy #secondary-inner",
            "ytd-watch-flexy #secondary",
            "ytd-watch-flexy #related",
          ]
            .map((s) => document.querySelector(s))
            .find(Boolean);
      const visible = Boolean(parent && mode === "bilingual");
      if (visible && this.host.parentElement !== parent)
        parent.prepend(this.host);
      this.host.hidden = !visible;
      this.host.dataset.theme = document.documentElement.hasAttribute("dark")
        ? "dark"
        : "light";
      this.owns = visible && this.rows.length > 0;
      document.documentElement.classList.toggle(
        "veloa-sidebar-active",
        this.owns,
      );
      if (visible) this.render();
      return visible;
    }
    setCues(rows) {
      if (this.rows === rows) {
        this.refreshVisible();
        return;
      }
      this.observer.disconnect();
      this.container.replaceChildren();
      this.start = 0;
      this.end = 0;
      this.rows = rows;
      this.active = -1;
      this.manualUntil = 0;
      this.heights = Array(rows.length).fill(88);
      this.measure();
      this.range = "";
      this.list.scrollTop = 0;
      this.spaces();
      this.shadow.querySelector(".follow").hidden = true;
      this.shadow.querySelector(".state").hidden = Boolean(rows.length);
      this.list.hidden = !rows.length;
      this.shadow.querySelector(".download").disabled = !rows.length;
      this.render();
    }
    refreshVisible() {
      // WindowQueue patches cues in place. Keep DOM/scroll anchors, update only text.
      for (const button of this.container.children) {
        const cue = this.rows[Number(button.dataset.index)];
        if (!cue) continue;
        for (const [selector, text] of [
          [".source", cue.text],
          [".translation", cue.translated || "Đang chờ dịch…"],
        ]) {
          const node = button.querySelector(selector);
          if (node.textContent !== text) node.textContent = text;
        }
      }
    }
    measure() {
      this.prefix = [0];
      for (let i = 0; i < this.rows.length; i++)
        this.prefix.push(this.prefix[i] + this.heights[i]);
    }
    indexAt(position) {
      let lo = 0,
        hi = this.rows.length;
      while (lo < hi) {
        const mid = (lo + hi) >>> 1;
        if (this.prefix[mid + 1] < position) lo = mid + 1;
        else hi = mid;
      }
      return lo;
    }
    spaces() {
      if (this.start === undefined) return;
      this.shadow.querySelector(".top-space").style.height =
        this.prefix[this.start] + "px";
      this.shadow.querySelector(".bottom-space").style.height =
        this.prefix[this.rows.length] - this.prefix[this.end] + "px";
    }
    render() {
      if (this.host.hidden || !this.rows.length) return;
      const start = Math.max(0, this.indexAt(this.list.scrollTop) - 6),
        end = Math.min(
          this.rows.length,
          this.indexAt(
            this.list.scrollTop + Math.min(760, this.list.clientHeight || 600),
          ) + 8,
        );
      const range = start + ":" + end;
      if (range === this.range) return;
      this.range = range;
      this.start = start;
      this.end = end;
      this.observer.disconnect();
      const fragment = document.createDocumentFragment();
      for (let i = start; i < end; i++) {
        const cue = this.rows[i],
          button = document.createElement("button");
        button.className = "cue";
        button.dataset.index = i;
        button.setAttribute("aria-current", String(i === this.active));
        button.onclick = () => this.seek(cue.start, true);
        const time = document.createElement("time");
        time.className = "time";
        time.textContent = A.stamp(cue.start);
        const texts = document.createElement("span");
        texts.className = "texts";
        const source = document.createElement("span");
        source.className = "source";
        source.textContent = cue.text;
        const translated = document.createElement("span");
        translated.className = "translation";
        translated.textContent = cue.translated || "Đang chờ dịch…";
        texts.append(source, translated);
        button.append(time, texts);
        fragment.append(button);
      }
      this.container.replaceChildren(fragment);
      this.spaces();
      for (const row of this.container.children) this.observer.observe(row);
    }
    follow() {
      if (this.active < 0) return;
      const start = this.prefix[this.active],
        end = this.prefix[this.active + 1],
        top = this.list.scrollTop,
        height = this.list.clientHeight;
      if (start < top + 40 || end > top + height - 40) {
        this.list.scrollTo({
          top: Math.max(0, start - height * 0.35),
          behavior:
            Math.abs(start - top) > height * 2 ||
            matchMedia("(prefers-reduced-motion: reduce)").matches
              ? "instant"
              : "smooth",
        });
      }
      this.shadow.querySelector(".follow").hidden = true;
    }
    update(index) {
      if (!this.rows.length || this.host.hidden) return;
      if (index !== this.active) {
        this.active = index;
        this.container
          .querySelector('[aria-current="true"]')
          ?.setAttribute("aria-current", "false");
        this.container
          .querySelector(`[data-index="${index}"]`)
          ?.setAttribute("aria-current", "true");
        if (Date.now() > this.manualUntil) this.follow();
      }
      this.shadow.querySelector(".follow").hidden =
        Date.now() > this.manualUntil;
    }
    close() {
      this.flexy?.removeAttribute("data-veloa-docked");
      this.observer.disconnect();
      this.host.remove();
      this.nativeStyle.remove();
      document.documentElement.classList.remove("veloa-sidebar-active");
    }
  }
  A.BilingualSidebar = BilingualSidebar;
})();

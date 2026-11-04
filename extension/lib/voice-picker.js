(() => {
  "use strict";
  class VoicePicker {
    constructor(select) {
      this.select = select;
      this.root = document.createElement("div");
      this.root.className = "voice-picker";
      this.root.innerHTML = `<button type="button" class="voice-picker-toggle" aria-expanded="false"><span></span><svg viewBox="0 0 20 20" aria-hidden="true"><path d="m6 8 4 4 4-4"/></svg></button><div class="voice-picker-panel" hidden><div class="voice-columns"><section data-gender="M" aria-label="Giọng nam"><h4>Nam</h4><div></div></section><section data-gender="F" aria-label="Giọng nữ"><h4>Nữ</h4><div></div></section></div><div class="voice-other" hidden><h4>Giọng khác</h4><div></div></div><label class="voice-variant" hidden>Biến thể<select aria-label="Biến thể giọng đọc"></select></label><p class="voice-empty" hidden>Thêm giọng cá nhân trong Kết nối.</p></div>`;
      const parent = select.parentElement;
      if (parent.tagName === "LABEL") {
        parent.after(this.root);
        parent.hidden = true;
      } else select.after(this.root);
      select.hidden = true;
      this.toggle = this.root.querySelector(".voice-picker-toggle");
      this.panel = this.root.querySelector(".voice-picker-panel");
      this.variant = this.root.querySelector(".voice-variant select");
      this.toggle.onclick = () => this.open(this.panel.hidden);
      this.variant.onchange = () => this.choose(this.variant.value, false);
      select.addEventListener("change", () => this.refresh());
      this.root.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !this.panel.hidden) {
          event.preventDefault();
          event.stopPropagation();
          this.open(false);
          this.toggle.focus();
        }
      });
      this.refresh();
    }
    open(value) {
      this.panel.hidden = !value;
      this.toggle.setAttribute("aria-expanded", String(value));
      if (value) {
        this.refresh();
        this.root.scrollIntoView({ block: "nearest", inline: "nearest" });
      }
    }
    choose(id, close = true) {
      if (![...this.select.options].some((option) => option.value === id))
        return;
      this.select.value = id;
      this.select.dispatchEvent(new Event("change", { bubbles: true }));
      this.refresh();
      if (close) {
        this.open(false);
        this.toggle.focus({ preventScroll: true });
      }
    }
    refresh() {
      const options = [...this.select.options],
        selected = this.select.selectedOptions[0];
      this.toggle.querySelector("span").textContent =
        selected?.textContent || "Chọn giọng đọc";
      this.toggle.setAttribute(
        "aria-label",
        "Giọng đọc: " + (selected?.textContent || "Chưa chọn"),
      );
      const activeBase = selected?.dataset.baseId || selected?.value;
      for (const container of this.root.querySelectorAll(
        "[data-gender] > div, .voice-other > div",
      ))
        container.replaceChildren();
      let otherCount = 0;
      for (const option of options) {
        if (option.dataset.baseId && option.dataset.baseId !== option.value)
          continue;
        const column = ["M", "F"].includes(option.dataset.gender)
          ? this.root.querySelector(
              `[data-gender="${option.dataset.gender}"] > div`,
            )
          : this.root.querySelector(".voice-other > div");
        if (!["M", "F"].includes(option.dataset.gender)) otherCount++;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "voice-choice";
        button.dataset.voice = option.value;
        button.textContent = option.textContent;
        button.setAttribute(
          "aria-pressed",
          String(option.value === activeBase),
        );
        button.onclick = () => this.choose(option.value);
        column.append(button);
      }
      this.root.querySelector(".voice-other").hidden = !otherCount;
      this.root.querySelector(".voice-columns").hidden = !options.some((o) =>
        ["M", "F"].includes(o.dataset.gender),
      );
      this.root.querySelector(".voice-empty").hidden = Boolean(options.length);
      const variants = options.filter(
        (o) => (o.dataset.baseId || o.value) === activeBase,
      );
      this.variant.replaceChildren(
        ...variants.map((option) => {
          const node = document.createElement("option");
          node.value = option.value;
          const key =
            option.value === activeBase
              ? "default"
              : option.value.slice(activeBase.length + 1);
          node.textContent =
            {
              default: "Giọng gốc",
              neutral: "Trung tính",
              angry: "Giận dữ",
              bored: "Trầm lắng",
              excited: "Hào hứng",
              sad: "Buồn",
              playful: "Vui vẻ",
            }[key] || option.textContent;
          return node;
        }),
      );
      this.variant.value = this.select.value;
      this.root.querySelector(".voice-variant").hidden = variants.length <= 1;
    }
  }
  globalThis.Auvirel.VoicePicker = VoicePicker;
})();

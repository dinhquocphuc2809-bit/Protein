(function (root) {
  "use strict";
  const positive = (value) =>
    /^[1-9]\d{0,15}$/.test(String(value || "")) ? String(value) : null;
  const language = (value) => String(value || "auto").replace(/^ai-/i, "");
  function resolve(route, state) {
    if (!route || !state) return null;
    const info = route.episode
      ? state.epInfo
      : state.videoData || state.video?.viewInfo || state;
    if (!info) return null;
    if (route.episode && String(info.id || info.ep_id) !== route.episode)
      return null;
    const bvid = info.bvid || state.bvid;
    const aid = positive(info.aid || state.aid);
    if (
      !aid ||
      (route.bvid && route.bvid !== bvid) ||
      (route.aid && route.aid !== aid)
    )
      return null;
    const pages = info.pages || state.pages;
    const page = Array.isArray(pages)
      ? pages.find((p) => Number(p.page) === route.page)
      : null;
    const statePage = Number(state.p || state.video?.page || 1);
    const cid =
      route.cid ||
      positive(page?.cid) ||
      (statePage === route.page ? positive(info.cid || state.cid) : null);
    if (!cid) return null;
    return { aid, cid, bvid, state, info, page: route.page };
  }
  function owner(data, url) {
    const params = new URL(url).searchParams;
    return {
      aid: positive(data?.data?.aid || params.get("aid")),
      cid: positive(data?.data?.cid || params.get("cid")),
      bvid: data?.data?.bvid || params.get("bvid"),
    };
  }
  function matches(info, target) {
    return Boolean(
      info &&
        target &&
        info.cid === target.cid &&
        (!info.aid || info.aid === target.aid) &&
        (!info.bvid || info.bvid === target.bvid),
    );
  }
  function tracks(list, base) {
    const result = [];
    for (const track of (Array.isArray(list) ? list : []).slice(0, 100)) {
      try {
        if (
          typeof track?.subtitle_url !== "string" ||
          !track.subtitle_url.trim()
        )
          continue;
        const url = root.VeloaSubtitleFormats.safeUrl(track.subtitle_url, base);
        result.push({
          url,
          language: language(track.lan),
          default: track.type === 0,
        });
      } catch {
        /* Missing URL may be resolved by the player's subtitle menu. */
      }
    }
    return result;
  }
  async function discover({ read, observed, check }) {
    const route = root.VeloaMedia.biliRoute(location.href);
    if (!route) return { tracks: [], diagnostic: "bili_identity" };
    let target = resolve(route, window.__INITIAL_STATE__);
    if (!target && !route.episode) {
      const query = new URLSearchParams(
        route.bvid ? { bvid: route.bvid } : { aid: route.aid },
      );
      const data = JSON.parse(
        await read(
          `https://api.bilibili.com/x/web-interface/view?${query}`,
          true,
        ),
      );
      if (data.code !== 0) return { tracks: [], diagnostic: "bili_metadata" };
      target = resolve(route, { videoData: data.data });
    }
    check();
    if (!target) return { tracks: [], diagnostic: "bili_identity" };
    const result = [];
    for (const row of observed())
      if (matches(row.owner, target)) result.push(...row.tracks);
    // Page-level lists can belong to the previous part during a SPA transition.
    if (positive(target.info.cid || target.state.cid) === target.cid) {
      result.push(
        ...tracks(target.info.subtitle?.list, location.href),
        ...tracks(
          target.state.data?.subtitle?.subtitles ||
            target.state.subtitle?.subtitles,
          location.href,
        ),
      );
    }
    if (result.length) return { tracks: result };
    let diagnostic = "bili_empty";
    for (const endpoint of ["/x/player/wbi/v2", "/x/player/v2"]) {
      check();
      try {
        const url = `https://api.bilibili.com${endpoint}?${new URLSearchParams({ aid: target.aid, cid: target.cid })}`;
        const data = JSON.parse(await read(url, true));
        check();
        if (data.code !== undefined && data.code !== 0) {
          diagnostic = [-101, -403].includes(data.code)
            ? "bili_session"
            : "bili_metadata";
          continue;
        }
        if (!matches(owner(data, url), target)) continue;
        const found = tracks(data.data?.subtitle?.subtitles, url);
        if (found.length) return { tracks: found };
        if (data.data?.need_login_subtitle) diagnostic = "bili_session";
      } catch (error) {
        check();
        diagnostic = "bili_metadata";
      }
    }
    return { tracks: [], diagnostic };
  }
  async function menuTrack(video, { check, resources }) {
    const container = video.closest(
      ".bpx-player-container, #bilibili-player, .bilibili-player",
    );
    const button = container?.querySelector(".bpx-player-ctrl-subtitle");
    if (!button) return null;
    const itemSelector = ".bpx-player-ctrl-subtitle-language-item[data-lan]";
    const active = (element) => element?.classList.contains("bpx-state-active");
    const items = () => [...button.querySelectorAll(itemSelector)];
    const close = () =>
      button.querySelector(
        ".bpx-player-ctrl-subtitle-close-switch, .bpx-player-ctrl-subtitle-fake-switch",
      );
    const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const deadline = Date.now() + 5000;
    let previous,
      wasClosed,
      touched = false;
    try {
      check();
      button.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true }));
      button.dispatchEvent(new MouseEvent("mousemove", { bubbles: true }));
      while (!items().length && Date.now() < deadline) {
        await wait(100);
        check();
      }
      const list = items();
      previous = list.find(active);
      wasClosed = active(close()) || !previous;
      const selected = previous || list[0];
      if (!selected || !close()) return null;
      const before = new Set(resources().map((r) => r.url + "|" + r.at));
      touched = true;
      if (!wasClosed) close().click();
      selected.click();
      while (Date.now() < deadline) {
        check();
        const row = resources().find((r) => {
          const url = new URL(r.url);
          return (
            /(^|\.)hdslb\.com$/.test(url.hostname) &&
            /\/bfs\/subtitle\//.test(url.pathname) &&
            !before.has(r.url + "|" + r.at)
          );
        });
        if (row)
          return {
            url: row.url,
            language: language(selected.getAttribute("data-lan")),
          };
        await wait(100);
      }
      return null;
    } finally {
      // Never toggle the next video's CC while restoring an obsolete operation.
      try {
        check();
        if (touched && wasClosed) {
          if (!active(close())) close()?.click();
        } else if (touched && (!active(previous) || active(close())))
          previous?.click();
        button.dispatchEvent(new MouseEvent("mouseleave", { bubbles: true }));
      } catch {
        /* A navigation owns the new player's subtitle state. */
      }
    }
  }
  root.VocalmBilibili = {
    resolve,
    owner,
    matches,
    tracks,
    discover,
    menuTrack,
    language,
  };
  if (typeof module !== "undefined") module.exports = root.VocalmBilibili;
})(globalThis);

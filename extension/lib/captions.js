(function (root) {
  "use strict";
  function json3(data) {
    if (!Array.isArray(data?.events) || data.events.length > 60000)
      throw new Error("Invalid YouTube subtitle response");
    const rows = [];
    for (const event of data.events) {
      if (!Array.isArray(event.segs)) continue;
      const text = event.segs
        .map((segment) => segment.utf8 || "")
        .join("")
        .trim();
      if (!text) continue;
      const start = Number(event.tStartMs) / 1000;
      const duration = Number(event.dDurationMs) / 1000;
      if (
        !Number.isFinite(start) ||
        !Number.isFinite(duration) ||
        duration <= 0
      )
        throw new Error("YouTube subtitle timing is missing");
      // JSON3 append events extend the previous displayed caption window.
      const previous = rows[rows.length - 1];
      if (event.aAppend && previous) {
        previous.text += " " + text;
        previous.end = Math.max(previous.end, start + duration);
      } else rows.push({ start, end: start + duration, text });
    }
    return rows.sort((a, b) => a.start - b.start);
  }
  function selectTrack(tracks, current, language, defaultIndex) {
    const code = current?.languageCode || language;
    const matching = tracks.filter((track) => track.languageCode === code);
    return (
      matching.find((track) => track.kind === current?.kind) ||
      matching.find((track) => track.kind !== "asr") ||
      matching[0] ||
      tracks[defaultIndex] ||
      tracks.find((track) => track.kind !== "asr") ||
      tracks[0]
    );
  }
  function acquisition(result, videoId, validate) {
    if (!result || result.videoId !== videoId)
      throw new Error(
        "Video đã đổi hoặc YouTube chưa tải xong thông tin phụ đề. Hãy thử lại.",
      );
    if (
      result.state === "absent" &&
      result.confirmed === true &&
      result.trackCount === 0
    )
      return null;
    if (result.state !== "ready")
      throw new Error(
        result.trackCount > 0
          ? "Video có phụ đề nhưng YouTube chưa trả dữ liệu. Hãy bật CC hoặc mở Bản chép lời, rồi thử lại. Vocalm không tự chuyển sang ASR."
          : "Chưa xác minh được phụ đề YouTube. Hãy đợi trang tải xong rồi thử lại; Vocalm chưa gọi ASR.",
      );
    return { cues: validate(result.cues), language: result.language || "auto" };
  }
  const functions = { json3, selectTrack, acquisition };
  root.VeloaCaptions = functions;
  if (typeof module !== "undefined") module.exports = functions;
})(globalThis);

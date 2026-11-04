(function (root) {
  "use strict";
  const A = root.Auvirel;
  class WindowQueue {
    constructor(cues, jobId, send, updated, failed) {
      this.cues = cues;
      this.jobId = jobId;
      this.send = send;
      this.updated = updated;
      this.failed = failed;
      this.generation = 0;
      this.closed = false;
      this.current = null;
      this.errors = new Map();
    }
    request(position, ahead = true) {
      if (this.closed) return;
      const index = this.cues.findIndex((c) => c.end > position);
      if (index < 0) return;
      this.wanted = { position, index, ahead };
      if (
        this.current &&
        (this.current.index > index + 5 ||
          index > this.current.index + 2 ||
          (!this.cues[index].translated && index !== this.current.index))
      )
        this.cancel();
      this.pump().catch((e) => this.failed(e));
    }
    cancel() {
      this.generation++;
      const current = this.current;
      this.current = null;
      if (current?.id)
        this.send({ type: "cancelJob", id: current.id }).catch(() => {});
    }
    async pump() {
      if (this.closed || this.current || !this.wanted) return;
      const { position, index, ahead } = this.wanted;
      const end = ahead ? Math.min(this.cues.length, index + 6) : index + 1;
      let next = -1;
      for (let i = index; i < end; i++)
        if (
          !this.cues[i].translated &&
          (i === index || this.cues[i].start <= position + 35)
        ) {
          next = i;
          break;
        }
      if (next < 0) return;
      const previous = this.errors.get(next);
      if (previous && (previous.count >= 3 || previous.retry > Date.now()))
        return;
      const epoch = this.generation,
        task = { index: next, id: null };
      let completed = false;
      this.current = task;
      try {
        const job = await this.send({
          type: "windowJob",
          payload: {
            video_job_id: this.jobId,
            position: this.cues[next].start,
            count: 1,
          },
          idem: A.random(),
        });
        task.id = job.id;
        if (this.closed || epoch !== this.generation) {
          await this.send({ type: "cancelJob", id: job.id });
          return;
        }
        const deadline = Date.now() + 180000;
        while (!this.closed && epoch === this.generation) {
          const state = await this.send({ type: "pollJob", id: job.id });
          if (this.closed || epoch !== this.generation) return;
          if (state.state === "done") {
            const rows = state.result?.cues;
            if (!Array.isArray(rows) || !rows.length || rows.length > 3)
              throw new Error("Invalid translated window");
            for (const row of rows) {
              const original = this.cues[row.id];
              if (
                !original ||
                original.start !== row.start ||
                original.end !== row.end ||
                original.text !== row.text ||
                typeof row.translated !== "string" ||
                !row.translated.trim() ||
                row.translated.length > 800
              )
                throw new Error("Translated window does not match this video");
            }
            for (const row of rows) {
              this.cues[row.id].translated = row.translated;
              this.errors.delete(row.id);
            }
            completed = true;
            this.updated(rows);
            return;
          }
          if (["failed", "cancelled"].includes(state.state))
            throw new Error(state.error || "Window translation stopped");
          if (Date.now() > deadline)
            throw new Error("Window translation timed out");
          await new Promise((resolve) => setTimeout(resolve, 700));
        }
      } catch (error) {
        if (!this.closed && epoch === this.generation) {
          this.errors.set(next, {
            count: (previous?.count || 0) + 1,
            retry: Date.now() + 5000,
          });
          this.failed(error);
        }
      } finally {
        if (this.current === task) {
          this.current = null;
          this.pump().catch((e) => this.failed(e));
        }
        if ((!completed || this.closed || epoch !== this.generation) && task.id)
          this.send({ type: "cancelJob", id: task.id }).catch(() => {});
      }
    }
    pause() {
      this.wanted = null;
      this.cancel();
    }
    async ensure(position) {
      const index = this.cues.findIndex((c) => c.end > position);
      if (index < 0) return;
      this.request(position, false);
      const epoch = this.generation;
      const deadline = Date.now() + 180000;
      while (!this.cues[index].translated) {
        if (this.closed || epoch !== this.generation)
          throw new DOMException("Cancelled", "AbortError");
        this.request(position, false);
        if ((this.errors.get(index)?.count || 0) >= 3 || Date.now() > deadline)
          throw new Error(
            "Current sentence translation failed; press Prepare to retry",
          );
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
    }
    close() {
      this.closed = true;
      this.pause();
    }
  }
  A.WindowQueue = WindowQueue;
  if (typeof module !== "undefined") module.exports = { WindowQueue };
})(globalThis);

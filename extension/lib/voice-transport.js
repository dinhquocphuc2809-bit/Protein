(function (root) {
  "use strict";
  class VoiceTransport {
    constructor(send, identity, reference) {
      this.send = send;
      this.identity = identity;
      this.reference = reference;
      this.registrations = new Map();
      this.features = new Map();
      this.cancelled = new Map();
    }
    check(id) {
      const now = Date.now();
      for (const [key, expires] of this.cancelled)
        if (expires < now) this.cancelled.delete(key);
      if (this.cancelled.has(id))
        throw new DOMException("Synthesis cancelled", "AbortError");
    }
    async cancel(id) {
      this.cancelled.set(id, Date.now() + 240000);
      if (this.cancelled.size > 256)
        this.cancelled.delete(this.cancelled.keys().next().value);
      try {
        return await this.send("DELETE", "/v1/results/" + id);
      } catch (error) {
        if (![404, 410].includes(error.status)) throw error;
      }
      return { state: "cancelled" };
    }
    async submit(payload, id) {
      this.check(id);
      const value = await this.send("POST", "/v1/synthesize", payload, id);
      if (this.cancelled.has(id)) {
        await this.cancel(id);
        this.check(id);
      }
      return value;
    }
    async capabilities(scope) {
      let promise = this.features.get(scope);
      if (!promise) {
        promise = this.send("GET", "/v1/health").then(
          (v) => new Set(v.capabilities || []),
        );
        this.features.set(scope, promise);
        promise.catch(() => {
          if (this.features.get(scope) === promise) this.features.delete(scope);
        });
        if (this.features.size > 8)
          this.features.delete(this.features.keys().next().value);
      }
      return promise;
    }
    async registered(scope, voiceId, ref) {
      const key =
        scope + ":" + voiceId + ":" + ref.hash + ":" + ref.reference_text;
      let promise = this.registrations.get(key);
      if (!promise) {
        promise = this.send("POST", "/v1/voices", {
          reference: ref.reference,
          reference_text: ref.reference_text,
        }).then((value) => {
          if (!/^[a-f0-9]{64}$/.test(value.reference_id))
            throw new Error("Invalid registered voice identity");
          return value.reference_id;
        });
        this.registrations.set(key, promise);
        promise.catch(() => {
          if (this.registrations.get(key) === promise)
            this.registrations.delete(key);
        });
        if (this.registrations.size > 8)
          this.registrations.delete(this.registrations.keys().next().value);
      }
      return { key, id: await promise };
    }
    async synthesize(message) {
      this.check(message.idem);
      const scope = await this.identity(),
        capabilities = await this.capabilities(scope),
        ref = await this.reference(message.voiceId),
        payload = {
          text: message.text,
          duration: message.duration,
          language: message.language,
        };
      if (!capabilities.has("voice_registry_v1"))
        return this.submit(
          {
            ...payload,
            reference: ref.reference,
            reference_text: ref.reference_text,
          },
          message.idem,
        );
      for (let attempt = 0; attempt < 2; attempt++) {
        const registered = await this.registered(scope, message.voiceId, ref);
        this.check(message.idem);
        if (scope !== (await this.identity()))
          throw new DOMException("Voice connection changed", "AbortError");
        try {
          return await this.submit(
            { ...payload, reference_id: registered.id },
            message.idem,
          );
        } catch (error) {
          if (attempt || error.status !== 404) throw error;
          // CPU container replacement/eviction loses references, never paid-job identity.
          this.registrations.delete(registered.key);
        }
      }
    }
    async prepare(voiceId) {
      const scope = await this.identity();
      if ((await this.capabilities(scope)).has("voice_registry_v1"))
        await this.registered(scope, voiceId, await this.reference(voiceId));
      return true;
    }
    async poll(id) {
      this.check(id);
      const scope = await this.identity(),
        capabilities = await this.capabilities(scope);
      const value = await this.send(
        "GET",
        "/v1/results/" +
          id +
          (capabilities.has("long_poll_v1") ? "?wait=10" : ""),
      );
      this.check(id);
      return value;
    }
  }
  root.Auvirel.VoiceTransport = VoiceTransport;
  if (typeof module !== "undefined") module.exports = { VoiceTransport };
})(globalThis);

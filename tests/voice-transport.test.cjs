const test = require("node:test");
const assert = require("node:assert/strict");
require("../extension/lib/core.js");
const { VoiceTransport } = require("../extension/lib/voice-transport.js");
const reference = async () => ({
  hash: "voice",
  reference: "base64-fixture",
  reference_text: "Reference.",
});
const message = {
  voiceId: "voice",
  text: "Complete speech.",
  duration: null,
  language: "vi",
  idem: "a".repeat(64),
};

test("concurrent nearby clips share one registration and send only reference IDs", async () => {
  const sent = [];
  const transport = new VoiceTransport(
    async (method, path, payload) => {
      sent.push({ method, path, payload });
      if (path === "/v1/health")
        return { capabilities: ["voice_registry_v1", "long_poll_v1"] };
      if (path === "/v1/voices") return { reference_id: "b".repeat(64) };
      return {};
    },
    async () => "endpoint",
    reference,
  );
  await Promise.all([
    transport.synthesize(message),
    transport.synthesize({ ...message, idem: "c".repeat(64) }),
  ]);
  assert.equal(sent.filter((x) => x.path === "/v1/voices").length, 1);
  assert.ok(
    sent
      .filter((x) => x.path === "/v1/synthesize")
      .every((x) => !x.payload.reference && x.payload.reference_id),
  );
  await transport.poll("a".repeat(64));
  assert.ok(sent.at(-1).path.endsWith("?wait=10"));
});

test("container replacement registers again once and preserves idempotency", async () => {
  let registrations = 0,
    submissions = 0;
  const transport = new VoiceTransport(
    async (method, path, payload, idem) => {
      if (path === "/v1/health") return { capabilities: ["voice_registry_v1"] };
      if (path === "/v1/voices") {
        registrations++;
        return { reference_id: "b".repeat(64) };
      }
      assert.equal(idem, message.idem);
      if (++submissions === 1)
        throw Object.assign(new Error("Lost reference"), { status: 404 });
      return { id: idem };
    },
    async () => "endpoint",
    reference,
  );
  assert.equal((await transport.synthesize(message)).id, message.idem);
  assert.equal(registrations, 2);
  assert.equal(submissions, 2);
});

test("old workers retain inline protocol; separate account uses a new registration", async () => {
  let scope = "old",
    uploads = 0;
  const transport = new VoiceTransport(
    async (method, path, payload) => {
      if (path === "/v1/health")
        return { capabilities: scope === "old" ? [] : ["voice_registry_v1"] };
      if (path === "/v1/voices") {
        uploads++;
        return { reference_id: "b".repeat(64) };
      }
      if (scope === "old") assert.equal(payload.reference, "base64-fixture");
      return {};
    },
    async () => scope,
    reference,
  );
  await transport.synthesize(message);
  scope = "new";
  await transport.synthesize(message);
  scope = "other";
  await transport.synthesize(message);
  assert.equal(uploads, 2);
});

test("preparing the voice overlaps translation without starting GPU work", async () => {
  const sent = [];
  const transport = new VoiceTransport(
    async (method, path) => {
      sent.push(path);
      if (path === "/v1/health") return { capabilities: ["voice_registry_v1"] };
      return { reference_id: "b".repeat(64) };
    },
    async () => "endpoint",
    reference,
  );
  await Promise.all([transport.prepare("voice"), transport.prepare("voice")]);
  assert.deepEqual(sent, ["/v1/health", "/v1/voices"]);
  await transport.synthesize(message);
  assert.equal(sent.filter((p) => p === "/v1/voices").length, 1);
});

test("reference recovery is bounded and never retries an authorization failure", async () => {
  for (const status of [404, 401]) {
    let submits = 0,
      uploads = 0;
    const transport = new VoiceTransport(
      async (method, path) => {
        if (path === "/v1/health")
          return { capabilities: ["voice_registry_v1"] };
        if (path === "/v1/voices") {
          uploads++;
          return { reference_id: "b".repeat(64) };
        }
        submits++;
        throw Object.assign(new Error("Unsuccessful request"), { status });
      },
      async () => "endpoint",
      reference,
    );
    await assert.rejects(transport.synthesize(message));
    assert.equal(submits, status === 404 ? 2 : 1);
    assert.equal(uploads, submits);
  }
});

test("seek cancellation during reference upload never submits obsolete GPU work", async () => {
  let release,
    submitted = 0;
  const transport = new VoiceTransport(
    async (method, path) => {
      if (path === "/v1/health") return { capabilities: ["voice_registry_v1"] };
      if (path === "/v1/voices")
        return new Promise((r) => {
          release = r;
        });
      if (method === "DELETE")
        throw Object.assign(new Error("Not submitted"), { status: 404 });
      submitted++;
    },
    async () => "endpoint",
    reference,
  );
  const task = transport.synthesize(message);
  const rejected = assert.rejects(task, { name: "AbortError" });
  while (!release) await new Promise((r) => setTimeout(r, 1));
  await transport.cancel(message.idem);
  release({ reference_id: "b".repeat(64) });
  await rejected;
  assert.equal(submitted, 0);
});

test("seek cancellation racing an accepted submission is reissued after acknowledgement", async () => {
  let release,
    cancellations = 0;
  const transport = new VoiceTransport(
    async (method, path) => {
      if (path === "/v1/health") return {};
      if (method === "DELETE") {
        cancellations++;
        return {};
      }
      return new Promise((r) => {
        release = r;
      });
    },
    async () => "endpoint",
    reference,
  );
  const task = transport.synthesize(message);
  const rejected = assert.rejects(task, { name: "AbortError" });
  while (!release) await new Promise((r) => setTimeout(r, 1));
  await transport.cancel(message.idem);
  release({ id: message.idem });
  await rejected;
  assert.equal(cancellations, 2);
});

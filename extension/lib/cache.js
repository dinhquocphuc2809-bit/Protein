(function (root) {
  "use strict";
  let opening;
  function database() {
    if (!opening)
      opening = new Promise((resolve, reject) => {
        const req = indexedDB.open("auvirel-private-cache", 1);
        req.onupgradeneeded = () => {
          const store = req.result.createObjectStore("entries", {
            keyPath: "key",
          });
          store.createIndex("touched", "touched");
        };
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => {
          opening = null;
          reject(new Error("Local cache unavailable."));
        };
      });
    return opening;
  }
  async function transaction(mode, action) {
    const db = await database();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("entries", mode);
      const result = action(tx.objectStore("entries"));
      tx.oncomplete = () => resolve(result?.result);
      tx.onerror = tx.onabort = () =>
        reject(new Error("Local cache transaction failed."));
    });
  }
  async function get(key) {
    const row = await transaction("readonly", (store) => store.get(key));
    if (!row) return null;
    if (row.expires < Date.now()) {
      await transaction("readwrite", (store) => store.delete(key));
      return null;
    }
    await transaction("readwrite", (store) =>
      store.put({ ...row, touched: Date.now() }),
    );
    return row.value;
  }
  async function put(key, value, bytes, ttl = 48 * 3600 * 1000) {
    if (!Number.isFinite(bytes) || bytes <= 0 || bytes > 8 * 1024 ** 2) return;
    // All reads/deletes/insert share one transaction, so parallel synthesis cannot overshoot.
    const db = await database();
    await new Promise((resolve, reject) => {
      const tx = db.transaction("entries", "readwrite"),
        store = tx.objectStore("entries");
      const request = store.getAll();
      request.onsuccess = () => {
        const rows = request.result
          .filter((row) => {
            if (row.key === key || row.expires < Date.now()) {
              store.delete(row.key);
              return false;
            }
            return true;
          })
          .sort((a, b) => a.touched - b.touched);
        let total = rows.reduce((sum, row) => sum + row.bytes, 0) + bytes;
        while (total > 80 * 1024 ** 2 && rows.length) {
          const row = rows.shift();
          total -= row.bytes;
          store.delete(row.key);
        }
        store.put({
          key,
          value,
          bytes,
          touched: Date.now(),
          expires: Date.now() + ttl,
        });
      };
      tx.oncomplete = resolve;
      tx.onerror = tx.onabort = () =>
        reject(new Error("Local cache quota reached."));
    });
  }
  root.Auvirel = Object.assign(root.Auvirel || {}, {
    cache: {
      get,
      put,
      clear: () => transaction("readwrite", (store) => store.clear()),
    },
  });
})(globalThis);

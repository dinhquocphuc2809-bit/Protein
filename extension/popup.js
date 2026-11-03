document.getElementById("settings").onclick = () =>
  (globalThis.browser || chrome).runtime.openOptionsPage();

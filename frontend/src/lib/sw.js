export async function ensureSW() {
  if (!("serviceWorker" in navigator)) return null;
  const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  await navigator.serviceWorker.ready;
  return reg;
}

export function prefetchViaSW(urls) {
  return new Promise((resolve) => {
    if (!navigator.serviceWorker?.controller) {
      resolve({ ok: false, count: 0 });
      return;
    }
    const ch = new MessageChannel();
    ch.port1.onmessage = (e) => resolve(e.data || { ok: false, count: 0 });
    navigator.serviceWorker.controller.postMessage(
      { type: "PREFETCH_ASSETS", payload: { urls } },
      [ch.port2]
    );
  });
}

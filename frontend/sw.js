// そっとぎふと Service Worker。
// 役割：①インストール可能にする ②アプリの外枠(シェル)をキャッシュしてオフラインでも開く。
// 商品データ(/api/)は鮮度が命なので絶対にキャッシュせず、常にネットワークへ。
const CACHE = "okurimono-v25";
const SHELL = [
  "/", "/index.html", "/styles.css", "/app.js", "/icons.js", "/holidays.js",
  "/manifest.json", "/icons/icon-192.png", "/icons/icon-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(SHELL))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())   // 1つ欠けても登録は通す
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;          // POST(/api/suggest 等)は素通し
  if (url.pathname.startsWith("/api/")) return;     // API は常にネットワーク（キャッシュしない）

  // 静的シェル：キャッシュ優先＋裏でこっそり更新（stale-while-revalidate）
  e.respondWith(
    caches.match(e.request).then((cached) => {
      const fetched = fetch(e.request).then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }
        return res;
      }).catch(() => cached);
      return cached || fetched;
    })
  );
});

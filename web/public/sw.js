/* Vaari service worker.
 *
 * - Pages: network first, so a new deploy shows at once; offline, the cached
 *   app shell opens and screens show their own "no signal" states.
 * - /assets/* (hashed by Vite): cache first, they never change.
 * - /audio/*: voice clips are cached as they are played, so a booking can be
 *   heard again with a weak signal. Each manifest.json is network first.
 * - /api/*: never cached and never touched here. Requests, photos and records
 *   always go to the server.
 * - Push: staff alerts and driver job alerts arrive here (encrypted end to end;
 *   the push service cannot read them) and show as a phone/desktop notification.
 *   Tapping one opens the right screen. Open Vaari windows are told to refresh.
 */
const VERSION = 'vaari-v2';
const SHELL_CACHE = `${VERSION}-shell`;
const ASSET_CACHE = `${VERSION}-assets`;
const AUDIO_CACHE = `${VERSION}-audio`;
const SHELL = ['/', '/manifest.webmanifest', '/favicon.svg', '/icons/icon-192.png', '/icons/icon-512.png'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then(cache => Promise.all(SHELL.map(url => cache.add(url).catch(() => undefined))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches
      .keys()
      .then(keys => Promise.all(keys.filter(k => !k.startsWith(VERSION)).map(k => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

async function networkFirst(request, cacheName, fallbackUrl) {
  const cache = await caches.open(cacheName);
  try {
    const res = await fetch(request);
    if (res.ok) cache.put(fallbackUrl || request, res.clone());
    return res;
  } catch {
    const hit = (await cache.match(fallbackUrl || request)) || (await cache.match(request));
    if (hit) return hit;
    throw new Error('offline');
  }
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(request);
  if (hit) return hit;
  const res = await fetch(request);
  if (res.ok && res.status === 200) cache.put(request, res.clone());
  return res;
}

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname === '/api' || url.pathname.startsWith('/api/')) return; // always live

  if (req.mode === 'navigate') {
    // Every route serves the same index.html; keep one copy under '/'.
    event.respondWith(networkFirst(req, SHELL_CACHE, '/'));
    return;
  }
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(cacheFirst(req, ASSET_CACHE));
    return;
  }
  if (url.pathname.startsWith('/audio/')) {
    if (url.pathname.endsWith('/manifest.json')) event.respondWith(networkFirst(req, AUDIO_CACHE));
    else event.respondWith(cacheFirst(req, AUDIO_CACHE));
    return;
  }
  if (SHELL.includes(url.pathname) || url.pathname.startsWith('/icons/')) {
    event.respondWith(networkFirst(req, SHELL_CACHE));
  }
});

// ── Push alerts ─────────────────────────────────────────────────────────────
self.addEventListener('push', event => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : '' };
  }
  const title = data.title || 'Vaari';
  const options = {
    body: data.body || '',
    tag: data.tag || 'vaari',
    renotify: true,
    icon: '/icons/icon-192.png',
    badge: '/icons/badge-96.png',
    timestamp: Date.now(),
    requireInteraction: data.urgency === 'high',
    vibrate: data.urgency === 'high' ? [180, 80, 180] : [120],
    data: { url: data.url || '/', id: data.id || 0, kind: data.kind || '' },
  };
  event.waitUntil(
    (async () => {
      await self.registration.showNotification(title, options);
      const wins = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      for (const w of wins) w.postMessage({ type: 'vaari-push', payload: data });
    })(),
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || '/', self.location.origin);
  event.waitUntil(
    (async () => {
      const wins = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      // Prefer a Vaari window already open in this worker's part of the app.
      const scope = new URL(self.registration.scope).pathname;
      const same = wins.find(w => new URL(w.url).pathname.startsWith(scope)) || wins[0];
      if (same) {
        await same.focus();
        if ('navigate' in same && new URL(same.url).href !== target.href) {
          try {
            await same.navigate(target.href);
            return;
          } catch {
            /* not controlled by this worker: tell the page instead */
          }
        }
        same.postMessage({ type: 'vaari-open', url: target.pathname + target.search });
        return;
      }
      await self.clients.openWindow(target.href);
    })(),
  );
});

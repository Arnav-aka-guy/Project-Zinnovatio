/* Vaari service worker.
 *
 * - Pages: network first, so a new deploy shows at once; offline, the cached
 *   app shell opens and screens show their own "no signal" states.
 * - /assets/* (hashed by Vite): cache first, they never change.
 * - /audio/*: voice clips are cached as they are played, so a booking can be
 *   heard again with a weak signal. Each manifest.json is network first.
 * - /api/*: never cached and never touched here. Requests, photos and records
 *   always go to the server.
 */
const VERSION = 'vaari-v1';
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

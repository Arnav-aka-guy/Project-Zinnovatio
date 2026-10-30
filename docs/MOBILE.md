# Phones and the installable web app

Vaari runs on phones as a web app: open it in Chrome (Android) or Safari
(iPhone), and it can be added to the home screen, where it opens full screen
like an app. Nothing to download from a store.

## Layout

At **900 px wide or less** (phones, and tablets held upright) the touch layout
is used; wider screens keep the desktop layout.

| Part | On a phone |
| --- | --- |
| Menu | A tab bar at the bottom: **Desk · Voice · Register · Officer · More**. *More* opens a sheet with Driver links, Service records, Install Vaari and Sign out. |
| Top bar | Vaari mark and the name of the page you are on. |
| Desk | Counts in a 2 × 2 grid. The new-request form opens from one **+ New request** button (the keyboard does not pop up on its own). Tabs scroll in one row and stay pinned while you scroll. Each request is a compact card: farmer and status, village · acres · machine, deadline, slot. Tapping a card opens the request full screen. |
| Register photo | **Take photo** opens the camera; **Choose from gallery** picks a saved photo. Drafted rows show as cards with full-width fields; **Confirm rows** stays above the tab bar. |
| Voice booking | Step chips scroll in one row; the question, mic and answer fit one screen. |
| Officer | Tables show as one card per row with labelled fields. |
| Driver and record links | No staff menu: these links are for drivers and farmers. The job sheet slides up from the bottom; buttons are glove-sized. Records have a **Share** button (WhatsApp etc.) where the phone supports it. |
| Sign in | A simple card; works the same on all sizes. |

Rules kept everywhere on phones: nothing wider than the screen, tap targets at
least 44 px, text fields at 16 px so iPhones do not zoom in, safe areas for
notches and the home bar respected.

## Installable web app

- `web/public/manifest.webmanifest`: name, icons (192, 512, maskable), standalone display, start at `/desk`, shortcuts to Voice, Register and Officer.
- `web/public/sw.js`: service worker, registered only in the built app (`python tasks.py serve`), never in `npm run dev`.
  - Pages: network first; with no signal the saved app opens and a dark **No signal** bar shows.
  - `/assets/*`: cached for good (file names change on every build).
  - `/audio/*`: voice clips are kept once played, so read-backs still play on a weak signal.
  - `/api/*`: never cached. Requests, photos and records always go to the server.
- Icons: `web/public/icons/` (made from `web/public/favicon.svg`).
- Chrome reports no installability errors (checked with `Page.getInstallabilityErrors`).

To install: Android Chrome shows *Install app* (or use **More → Install Vaari**).
iPhone Safari: **Share → Add to Home Screen** (More shows the steps).

The camera, microphone and GPS need `https://` or `localhost`. For phones on
the same Wi-Fi, use `python tasks.py tunnel` for an https link.

## Tests

`web/e2e/mobile.spec.ts` runs in two Playwright projects, `mobile-android`
(Pixel 7) and `mobile-iphone` (iPhone 13 size), as part of `python tasks.py e2e`:
tab bar and More sheet, every page fits the screen, no iPhone zoom on inputs,
tap sizes, a new request from the phone, request detail, all Desk tabs, register
photo upload and confirm, a typed voice booking, Officer, a driver job started
and finished with photos and code, the record, and the installable app
(manifest, icons, service worker, offline start).

The desktop project blocks the service worker so `page.route()` mocks still work.

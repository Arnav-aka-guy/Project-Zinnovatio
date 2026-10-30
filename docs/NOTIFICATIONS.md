# Notifications

Every notification in Vaari is delivered **inside Vaari itself**: in the web app on a phone or a computer, and as a phone/desktop alert from the Vaari app. **Nothing is sent by SMS or WhatsApp**, and Vaari needs no SMS or WhatsApp account.

| Who | Where they see it | About what |
| --- | --- | --- |
| Farmer | Their own Vaari page (`/farmer/<link>`), plus a phone alert once they tap **Turn on** | Turn booked, turn changed, will miss, booking cancelled, work started (with the code for the driver), work done (opens the record), not served |
| Operator | The bell in the app, plus a phone/desktop alert | A request will miss its deadline, a job was not served, a machine was taken off, a changed turn that no farmer phone received |
| Officer | The bell, plus a phone/desktop alert | A job was flagged for review, a staff account was locked |
| Driver | A phone alert from the driver link | New job today or tomorrow, job removed, the day's job list each morning |

The alerts are web push: the same system that shows a notification from any website or installed web app. They work in Chrome, Edge and Firefox on Android, Windows, Mac and Linux, and in Safari 16.4+ on iPhone once Vaari is added to the Home Screen. They are encrypted end to end: Google, Mozilla or Apple carry them but cannot read them.

## How a farmer gets their messages

1. The operator opens the request on the Desk. The **Farmer app** card shows a QR code. **Show QR to farmer** makes it big. The same QR appears at the end of a voice booking.
2. The farmer scans it with their phone camera. Their page opens, in Punjabi (English on a tap), with their bookings, the date, the machine, the code to tell the driver, and every message.
3. The farmer taps **ਚਾਲੂ ਕਰੋ / Turn on** and allows notifications. From then on their phone shows Vaari alerts like any app.
4. On iPhone the farmer first adds the page to the Home Screen (Share → Add to Home Screen); the page installs as its own app that opens straight to their bookings.

The card shows whether the farmer's alerts are on ("Alerts are on for 1 phone"). The message is always on the farmer's page, even when no phone has alerts on. If a turn **changes** and no farmer phone received the alert, the operators get "Tell the farmer: turn changed. Please call."

Each farmer has one link. **New link…** turns the old link off, and every phone that used it stops getting alerts. Links last one season (`VAARI_FARMER_LINK_DAYS`, 180 days).

## How it works

```
any change  ->  log_event()  ->  rules.py queues Notification rows (same transaction)
                                    | inapp rows: on the farmer page / in the staff bell at once
                                    | webpush rows: phone alerts
                     background sender (dispatch.py, every 5 s, woken at commit)
                         |                     |                      |
                  farmer phones          staff devices           driver phones
              (via their farmer link)   (by role)            (via the driver link)
```

- **Outbox.** A message exists only if the change that caused it was saved. If the sender stops, nothing is lost: it sends when it comes back.
- **Once only.** Every message has a unique key, so running the planner again does not alert the farmer again. Each row is claimed with a conditional update, so two server processes never send it twice.
- **Never in the way.** A bug in a rule is logged and skipped; the booking, start or finish still goes through.

## Rules for a farmer's phone alert

1. Only farmers who agreed to service messages.
2. **Out of date** messages are not sent (the turn was cancelled or changed, or the request is no longer at risk).
3. **Quiet hours**: phones are not woken 21:00 to 07:00 local time. The message is already on the farmer's page; the alert waits for the morning.
4. **No phone with alerts on**: nothing to send. For a changed turn, the operators are asked to call.
5. **Retries**: a busy push service (429, 5xx, network) is tried again after 30 s, 2 min, 10 min, 1 h and 6 h. A phone that has turned alerts off (404/410) is removed at once; one that refuses five times is removed.

Staff and driver alerts carry village, acres and machine, never a farmer's name or phone number. The farmer's page shows no phone number or name either.

## Settings

| Setting | Default | Meaning |
| --- | --- | --- |
| `VAARI_FARMER_QUIET_HOURS` | `21-7` | Local hours when farmers' phones are not woken; empty turns it off |
| `VAARI_FARMER_LINK_DAYS` | `180` | How long a farmer's page link lasts |
| `VAARI_VAPID_PUBLIC_KEY`, `VAARI_VAPID_PRIVATE_KEY` | made on first start into `data/vapid.json` | Push keys. Make them with `python tasks.py vapid-keys`. Changing them means every device turns alerts on again. |
| `VAARI_VAPID_SUBJECT` | `VAARI_PUBLIC_BASE_URL` if https | `mailto:` or https contact for the push services |
| `VAARI_DRIVER_DIGEST_HOUR` | `6` | Local hour for the drivers' morning job list; `-1` turns it off |
| `VAARI_NOTIFY_WORKER` | `true` | Run the sender inside the web server |
| `VAARI_NOTIFY_INTERVAL_S` | `5` | How often the sender looks for due alerts |
| `VAARI_PUSH_HOSTS` | (empty) | Extra push service hosts to accept (Google, Mozilla, Microsoft and Apple are built in) |
| `VAARI_PUBLIC_BASE_URL` | (empty) | The https address people open; used in the farmer QR code. Without it, the QR uses the address the operator's browser is on. |

Alerts need **https** (or `localhost`). For a demo on phones, use `python tasks.py tunnel`.

## Where to see it

- **Bell** (top right, every staff screen): unread count, the alert list, and **Turn on** for alerts on this device, plus **Send test**. Tapping an alert opens the request.
- **Request details → Farmer app**: the QR code, the link, and whether the farmer's alerts are on.
- **Request details → Messages sent**: every phone alert for that request (farmer and driver), its state (Sent, Waiting, Not sent, Failed) and why, with **Send again** for failed ones.
- **Officer → Message delivery**: counts for the last 7 days, devices with alerts on, and whether the sender is running.
- **Driver link → Job alerts → Turn on**.
- `python tasks.py notify` (status) and `python tasks.py notify --run` (send what is due now).
- `GET /api/health` → `notifications`.

## API (additive)

| Route | Who |
| --- | --- |
| `GET /api/requests/{id}/farmer-link`, `POST /api/requests/{id}/farmer-link/rotate` | Operator: the farmer's link and QR |
| `GET /api/farmer/{token}`, `POST /api/farmer/{token}/read` | The farmer link: bookings and messages |
| `POST /api/farmer/{token}/push`, `DELETE …/push`, `POST …/push/test`, `GET …/manifest.webmanifest` | The farmer link: phone alerts, install |
| `POST /api/notify/subscriptions`, `DELETE /api/notify/subscriptions`, `POST /api/notify/test` | Staff devices |
| `GET /api/notify/inbox`, `POST /api/notify/inbox/read` | Staff: alerts for their role (a shared team inbox) |
| `GET /api/notify/summary` | Staff: counts only |
| `GET /api/notify/outbox`, `POST /api/notify/outbox/{id}/retry` | Operator: every phone alert |
| `POST /api/driver/{machine_token}/push`, `DELETE …/push`, `POST …/push/test` | The driver link |

Tables: `notification`, `push_subscription` (migration `0003`) and `farmer_link` (migration `0004`).

The contract's older `GET /api/slots/{id}/message` still returns `wa_link` (contract changes are additive only), but the app no longer shows a WhatsApp button; the message is shown with **Copy text** and **Call**.

## What was not verified

- **Real push services.** The encryption is checked with the reference decryptor, the QR codes are checked with a QR reader, and the service workers are checked with real push events in Chromium. No alert went through Google, Mozilla or Apple from the test machine. Before the demo: turn on alerts on a real Android phone and a real iPhone, and press **Test**.
- **Punjabi wording** of the farmer page and alerts should be read by a native speaker.

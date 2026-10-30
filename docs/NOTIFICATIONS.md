# Notifications

Vaari tells people when something changes, without anyone having to open a screen.

| Who | How | About what |
| --- | --- | --- |
| Farmer | SMS or WhatsApp (Punjabi, or English if the farmer chose English) | Turn booked, turn changed, will miss, booking cancelled, work started, work done (with the record link), not served |
| Operator | Bell in the app + phone/desktop alert | A request will miss its deadline, a job was not served, a machine was taken off, a farmer message failed |
| Officer | Bell in the app + phone/desktop alert | A job was flagged for review, a staff account was locked |
| Driver | Phone alert from the driver link | New job today or tomorrow, job removed, the day's job list each morning |

Before this, the backend had no sender at all: the slot message was only shown on screen, with a `wa.me` link and a Call button for the operator to tap.

## How it works

```
any change  ->  log_event()  ->  rules.py: queue Notification rows (same transaction)
                                         |
                       background sender (dispatch.py, every 5 s, woken at commit)
                         |                 |                    |
                  farmer SMS/WhatsApp   staff web push     driver web push
                  (Twilio, MSG91,       (all devices of    (phones on that
                   WhatsApp Cloud)       that role)         machine's link)
```

- **Outbox.** A message row exists only if the change that caused it was saved. If the sender is down, nothing is lost: it sends when it comes back.
- **Once only.** Every message has a unique key (for example `farmer:will_miss:request:12:NO_CAPACITY:sms`), so running the planner again does not text the farmer again. Each row is claimed with a conditional update, so two server processes never send it twice.
- **Never in the way.** A bug in a rule is logged and skipped; the booking, start or finish that caused it still goes through.
- **Web push is done in-house** (RFC 8291 encryption and RFC 8292 VAPID, with `cryptography` and `httpx`). It works with Chrome, Edge, Firefox, Android and Safari 16.4+ (iPhone: after "Add to Home Screen"). Messages are encrypted end to end: Google, Mozilla or Apple carry them but cannot read them. The test suite decrypts them with the reference `http_ece` library.

## Safety rules for farmer messages

Applied in this order before anything leaves the server:

1. `VAARI_NOTIFY_MODE=off`: no farmer messages.
2. **Consent**: only farmers who agreed to service messages.
3. **Out of date**: if the turn was cancelled or changed, or the request is no longer at risk, the old message is not sent.
4. **Simulated**: in `simulate` mode (the default), with provider `log`, or for demo (seeded) requests, the message is recorded as *simulated* and nothing is sent.
5. **Test numbers**: outside production, live mode only messages numbers in `VAARI_NOTIFY_TEST_NUMBERS`.
6. **Quiet hours**: no farmer messages 21:00 to 07:00 local time; they wait for the morning.
7. **Retries**: a temporary error (network, 429, 5xx) tries again after 30 s, 2 min, 10 min, 1 h and 6 h.
8. **Fallback**: a permanent error tries the next channel in `VAARI_FARMER_CHANNELS` (for example WhatsApp, then SMS). If none is left, the operators get "Message to farmer failed. Please call the farmer."

Staff and driver alerts carry village, acres and machine, never a farmer's name or phone.

## Settings

| Setting | Default | Meaning |
| --- | --- | --- |
| `VAARI_NOTIFY_MODE` | `simulate` | `simulate`, `live` or `off` (farmer messages only; staff alerts always work) |
| `VAARI_FARMER_CHANNELS` | `sms` | Order to try, e.g. `whatsapp,sms` |
| `VAARI_FARMER_QUIET_HOURS` | `21-7` | Local hours with no farmer messages; empty turns it off |
| `VAARI_NOTIFY_TEST_NUMBERS` | (empty) | Outside production, the only numbers live mode will message |
| `VAARI_SMS_PROVIDER` | `log` | `log`, `twilio` or `msg91` |
| `VAARI_WHATSAPP_PROVIDER` | `log` | `log` or `cloud` (WhatsApp Business Cloud API) |
| `VAARI_VAPID_PUBLIC_KEY`, `VAARI_VAPID_PRIVATE_KEY` | made on first start into `data/vapid.json` | Web push keys. Make them with `python tasks.py vapid-keys`. Changing them means every device turns alerts on again. |
| `VAARI_VAPID_SUBJECT` | `VAARI_PUBLIC_BASE_URL` if https | `mailto:` or https contact for the push services |
| `VAARI_DRIVER_DIGEST_HOUR` | `6` | Local hour for the drivers' morning job list; `-1` turns it off |
| `VAARI_NOTIFY_WORKER` | `true` | Run the sender inside the web server |
| `VAARI_NOTIFY_INTERVAL_S` | `5` | How often the sender looks for due messages |
| `VAARI_PUSH_HOSTS` | (empty) | Extra push service hosts to accept (the big four are built in) |

Provider settings:

- **Twilio SMS**: `VAARI_TWILIO_ACCOUNT_SID`, `VAARI_TWILIO_AUTH_TOKEN`, and `VAARI_TWILIO_FROM` or `VAARI_TWILIO_MESSAGING_SERVICE_SID`.
- **MSG91 SMS (India)**: `VAARI_MSG91_AUTH_KEY` and `VAARI_MSG91_TEMPLATES`, a JSON map from message kind to the DLT-approved flow template id, e.g. `{"slot_scheduled": "64ab…", "will_miss": "64ac…"}`. Template variables `var1`..`var7` are village, acres, machine, date, code, centre phone, link.
- **WhatsApp Cloud API**: `VAARI_WHATSAPP_TOKEN`, `VAARI_WHATSAPP_PHONE_NUMBER_ID`, and `VAARI_WHATSAPP_TEMPLATES` (JSON map from kind to approved template name; body parameters in the same order as above). Without a template, the text is sent as a normal message, which WhatsApp only allows within 24 hours of the farmer's last message.

## Going live, step by step

1. `python tasks.py vapid-keys` and put the three lines in `.env`.
2. Set up one SMS provider and its templates (in India, register each farmer text with DLT first; the texts are in `app/notify/messages.py` and `app/messaging/templates.json`).
3. Try it on your own phone: `VAARI_NOTIFY_MODE=live`, `VAARI_NOTIFY_TEST_NUMBERS=<your number>`, book a request with your number, then `python tasks.py notify` to see what happened.
4. In production, live mode messages every farmer who agreed. Watch **Officer → Message delivery** for failures.

## Where to see it

- **Bell** (top right, every staff screen): unread count, the alert list, and **Turn on** for phone/desktop alerts on this device, plus **Send test**. Tapping an alert opens the request.
- **Request details → Messages sent**: every SMS/WhatsApp and driver alert for that request, with its state (Sent, Simulated, Waiting, Not sent, Failed) and why, and **Send again** for failed ones.
- **Officer → Message delivery**: counts for the last 7 days, devices with alerts on, and whether the sender is running.
- **Driver link → Job alerts → Turn on**.
- `python tasks.py notify` (status) and `python tasks.py notify --run` (send what is due now).
- `GET /api/health` → `notifications`.

## API (additive)

| Route | Who |
| --- | --- |
| `POST /api/notify/subscriptions`, `DELETE /api/notify/subscriptions` | Staff: this device gets alerts for the signed-in role |
| `POST /api/notify/test` | Staff: a test alert to this device |
| `GET /api/notify/inbox`, `POST /api/notify/inbox/read` | Staff: alerts for their role (a shared team inbox) |
| `GET /api/notify/summary` | Staff: counts only |
| `GET /api/notify/outbox`, `POST /api/notify/outbox/{id}/retry` | Operator: farmer messages and driver alerts |
| `POST /api/driver/{machine_token}/push`, `DELETE …/push`, `POST …/push/test` | The driver link |

Tables: `notification` and `push_subscription` (migration `0003`).

## What was not verified

- **Real SMS and WhatsApp delivery.** Twilio, MSG91 and WhatsApp Cloud calls are tested against recorded request shapes, not live accounts. Try one real message per provider before the pilot.
- **Real push services.** The encryption is checked with the reference decryptor, and the service worker is checked with a real push event in Chromium, but no message went through Google, Mozilla or Apple from the test machine. Turn alerts on with a real phone and press **Send test**.
- **Punjabi wording** of the new farmer texts should be read by a native speaker.

# IFINMAIL Client

A client-side mail application — no backend required.

## Features

- Desktop web client (`index.html`) with a 3-pane Material 3 interface: folders, email list, and reading pane
- Light and dark themes, adjustable density, compact mode
- Compose with To/Cc/Bcc, attachments (stored locally), drafts, auto-save
- Search with filters (from, to, subject, labels, dates, attachments, size)
- Starring, snoozing, archiving, labels, bulk select actions
- Contacts, notifications, settings (signature, auto-reply, forwarding, security)
- Accounts: sign in, create account, forgot/reset password, two-factor login
- Mobile web app in `mobile/` (signin, create account, inbox, viewer, compose)
- Data persists in `localStorage` (keys `ifinmail.*`) with a seeded demo mailbox

## Quick start

Open `index.html` in a browser.

Demo accounts:

| Email | Password |
| --- | --- |
| `alex@example.com` | `password` |
| `alex@ifinmail.com` | `blaise7128` |
| `admin@example.com` | `admin123` |

The mobile app can be served with a static file server, e.g. `python3 -m http.server` inside `mobile/`.

## Structure

```
index.html        Desktop mail client
auth.html         Sign in / create account / reset password / 2FA
css/              app.css (client), auth.css (auth)
js/               app.js (client logic), auth.js (auth logic), mail-data.js (seed data)
mobile/           Mobile web app (signin, create, inbox, viewer, compose)
assets/           Icons
```
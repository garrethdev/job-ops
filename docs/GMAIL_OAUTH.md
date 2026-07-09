# Gmail OAuth setup (Module A — email-scanner)

Goal: read-only Gmail access for the headless cron on the **gmail.com** account
(`garreth.dottin@gmail.com`), producing three values:
`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`.

Do steps 1–5 in the browser (signed in as the gmail.com account). Then run the
helper (step 6). Hand me the three values, or drop them in `.env` yourself.

## 1. Create a project
console.cloud.google.com → project picker (top bar) → **New Project** →
name it `job-ops` → Create, then select it.

## 2. Enable the Gmail API
APIs & Services → **Library** → search **Gmail API** → **Enable**.

## 3. Configure the OAuth consent screen
APIs & Services → **OAuth consent screen**
- User type: **External** → Create
- App name `job-ops`, your gmail address as support + developer contact → Save
- **Scopes** → Add or Remove Scopes → filter for **Gmail API** → tick
  `.../auth/gmail.readonly` → Update → Save and Continue
- **Publishing status → PUBLISH APP → Confirm** (move to *Production*).
  > Why: in "Testing" the refresh token expires every **7 days** and the cron
  > dies weekly. Production tokens don't expire. You'll see an "unverified app"
  > warning at consent — that's expected for a personal app; click through
  > **Advanced → Go to job-ops (unsafe)**. It's your own app and your own inbox.

## 4. Create the OAuth client
APIs & Services → **Credentials** → **Create Credentials** → **OAuth client ID**
- Application type: **Desktop app**
- Name: `job-ops-desktop` → Create
- Copy the **Client ID** and **Client secret**.

## 5. Put the client id/secret in .env
```
GMAIL_CLIENT_ID=xxxx.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=xxxx
```

## 6. Mint the refresh token (the helper does the hard part)
```
python scripts/gmail_oauth.py
```
It opens the consent screen, you approve (click through the unverified-app
warning), and it prints:
```
GMAIL_REFRESH_TOKEN=1//0g....
```
Add that line to `.env` too.

## 7. Hand off
Give me the three values (or confirm they're in `.env`). I'll:
- store them (gitignored `.env` locally; you add them to **GitHub → Settings →
  Secrets and variables → Actions** for CI),
- build the scanner against `modules/email_scanner/allowlist.yaml`
  (senders, the `Claude-Jobs` label, the `jobs-noreply@linkedin.com`
  status-update routing rule),
- test it live, then uncomment the `schedule:` in `.github/workflows/email-scan.yml`.

## Notes
- Scope is `gmail.readonly` — the scanner can read and search mail, nothing else.
- To revoke access anytime: myaccount.google.com/permissions.
- Dots in Gmail addresses are ignored, so `garreth.dottin@` and `garrethdottin@`
  are the same inbox.

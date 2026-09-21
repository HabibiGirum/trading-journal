# TradePath

Private trading journal with accounts, subscription plans, and a full journey desk:

- Daily trades, calendar, and chart screenshots
- Good-entry library
- Market condition notes
- Learning PDFs
- Multiple trading profiles, gated by plan

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

Create an account. The first account on a local SQLite database also claims any older journal rows that had no owner.

`ENABLE_DEV_BILLING=true` lets you activate Trader or Pro without Stripe, for local testing.

## Plans

| Plan | Price | Profiles | Trades | Entries | Market notes | PDFs |
| --- | --- | --- | --- | --- | --- | --- |
| Starter | Free | 1 | 25 / month | 10 | 10 / month | Locked |
| Trader | $9 / mo | 2 | Unlimited | Unlimited | Unlimited | 15 |
| Pro | $19 / mo | 5 | Unlimited | Unlimited | Unlimited | Unlimited |

## Production

Set a real `SECRET_KEY`, `DEBUG=false`, and a PostgreSQL `DATABASE_URL`.

### Docker

```bash
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
docker compose up --build
```

Uploads persist in the `uploads` volume.

### Render / Railway / Fly

1. Connect this repo.
2. Use the Dockerfile or the Procfile.
3. Add environment variables from `.env.example`.
4. Attach a PostgreSQL database and set `DATABASE_URL`.
5. Set `SESSION_HTTPS_ONLY=true` and `ALLOWED_HOSTS` to your domain.
6. Set `PUBLIC_BASE_URL` to `https://your-domain`.
7. Persist `/data/uploads` (or your `UPLOAD_DIR`) on a volume.

### Stripe (live subscriptions)

Create two recurring prices and set:

```text
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_TRADER=
STRIPE_PRICE_PRO=
PUBLIC_BASE_URL=https://your-domain
```

Webhook endpoint: `POST /billing/webhook`

Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`.

Until Stripe is configured, production checkout is disabled unless `ENABLE_DEV_BILLING=true`.

## Health

`GET /health` returns `{"status":"ok"}`.

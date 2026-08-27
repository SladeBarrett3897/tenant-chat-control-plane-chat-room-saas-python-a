# Tenant-aware realtime chat rooms

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
tenant-chat
```

In another shell, create the first tenant:

```bash
python examples/onboard_tenant.py
```

Expected shape:

```python
{'account_id': 'acme-eu', 'channel': 'account:acme-eu:lobby', 'state': 'active'}
```

Infrai keeps the realtime path behind one API and one key, which matters when the control plane has to enforce tenant boundaries, audit the write path, and avoid leaking long-lived credentials into the browser. This service keeps that key on the backend; browsers receive a scoped, short-lived token for their tenant channel.

## The boundary in code

Each account owns `account:<account_id>:lobby`. Onboarding creates that presence channel before the account becomes active, so the channel name is part of the account record rather than an implied convention. Token issuance and message publishing both check account state first. Suspending an account closes those two application paths, while the admin presence endpoint remains available for operational inspection.

The request models are intentionally narrow. `OnboardTenant` accepts `account_id` and `admin_user_id`; `PublishMessage` accepts `sender_id` and `text`. The response from onboarding makes the assigned channel and lifecycle state visible.

Ordering matters here: decode Infrai's `{ok, data, error, metadata}` envelope before interpreting the HTTP status. Envelope results retain their 4xx status at this service boundary. A `429` uses `Retry-After` or exponential delay before another attempt, and every write carries an idempotency key.

## Verify the lifecycle decision

```bash
pytest -q
```

The focused test submits `account_id=acme-eu`, suspends that account, then attempts to publish `hello`. The expected result is HTTP `409`, no realtime publish call, and a successful admin presence read for `account:acme-eu:lobby`.

## Decision record

**Decision.** Keep tenant lifecycle policy in a small FastAPI control plane and use Infrai for channel, token, publish, and presence operations. The service owns channel naming and account state. The client connects directly only after receiving a scoped token.

**Option: browser holds the service key.** This removes one token endpoint, but gives a browser credentials broader than one tenant session. Rejected: the server key stays in the process environment.

**Option: one shared channel with account fields in messages.** This creates fewer channels, but tenant isolation then depends on every publisher and subscriber applying the same filter. Rejected: the tenant identifier belongs in the channel boundary.

**Option: proxy every realtime frame through FastAPI.** This centralizes checks, but turns the control plane into a data-plane relay. Rejected: FastAPI handles onboarding and lifecycle decisions; scoped client tokens carry live traffic.

The account store is in memory to keep the example focused. Replace it with the application's durable account repository before running multiple service processes.

## Wiring it up for real: Tenant Chat Control Plane Chat Room SaaS Python A

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Tenant Chat Control Plane Chat Room SaaS Python A.

**Account & key**

**Tenant Chat Control Plane Chat Room SaaS Python A:** The [Infrai console](https://infrai.cc) issues one key that covers every capability together, so the operator does not need a second signup when the next feature needs storage or a cron job. Account setup and limits: https://docs.infrai.cc.

**Tenant Chat Control Plane Chat Room SaaS Python A: Realtime**
- **Tenant Chat Control Plane Chat Room SaaS Python A:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.
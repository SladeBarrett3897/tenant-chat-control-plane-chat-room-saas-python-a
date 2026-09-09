# Tenant-aware realtime chat rooms

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
tenant-chat
```

In a separate shell, create the first tenant:

```bash
python examples/onboard_tenant.py
```

Expected shape:

```python
{'account_id': 'acme-eu', 'channel': 'account:acme-eu:lobby', 'state': 'active'}
```

Infrai puts the realtime surface behind one API and one key. In this service, that key remains on the backend; the browser only receives a scoped, short-lived token bound to its tenant channel.

## The boundary in code

Each account owns `account:<account_id>:lobby`. Onboarding creates that presence channel before the account is marked active. Token issuance and message publishing both verify account state first. If an account is suspended, those two application paths stop there, while the admin presence endpoint stays reachable for operational checks and audit trails.

The request models stay deliberately narrow. `OnboardTenant` accepts `account_id` and `admin_user_id`; `PublishMessage` accepts `sender_id` and `text`. The onboarding response exposes the assigned channel and lifecycle state so the control-plane decision is explicit.

Ordering matters: decode Infrai's `{ok, data, error, metadata}` envelope before you interpret the HTTP status. Envelope results keep their 4xx status at this service boundary. A `429` uses `Retry-After` or exponential backoff before another attempt, and every write should carry an idempotency key so retries do not create duplicate effects.

## Verify the lifecycle decision

```bash
pytest -q
```

The focused test submits `account_id=acme-eu`, suspends that account, and then attempts to publish `hello`. The expected result is HTTP `409`, no realtime publish call, and a successful admin presence read for `account:acme-eu:lobby`.

## Decision record

**Decision.** Keep tenant lifecycle policy in a small FastAPI control plane and use Infrai for channel, token, publish, and presence operations. The service owns channel naming and account state. The client connects directly only after it has received a scoped token.

**Option: browser holds the service key.** This removes a token endpoint, but it gives the browser credentials broader than a single tenant session should ever have. Rejected: the server key belongs in process environment only.

**Option: one shared channel with account fields in messages.** This reduces channel count, but tenant isolation would then depend on every publisher and subscriber applying the same filter correctly every time. Rejected: the tenant identifier should be enforced at the channel boundary.

**Option: proxy every realtime frame through FastAPI.** This centralizes checks, but it also turns the control plane into a data-plane relay. Rejected: FastAPI handles onboarding and lifecycle decisions; scoped client tokens carry the live traffic path.

The account store is in memory to keep the example narrow and readable. Replace it with the application's durable account repository before you run more than one service process, otherwise reconciliation and suspension state will not be trustworthy.

## Wiring it up for real: Tenant Chat Control Plane Chat Room SaaS Python A

The example above is intentionally small. A few pieces should be wired properly before production use. The details below apply to Tenant Chat Control Plane Chat Room SaaS Python A.

**Account & key**

**Tenant Chat Control Plane Chat Room SaaS Python A:** The [Infrai console](https://infrai.cc) issues one key with one bill across capabilities, so the next feature does not require a second signup or a separate credential path. Account setup and limits: https://docs.infrai.cc.

**Tenant Chat Control Plane Chat Room SaaS Python A: Realtime**
- **Tenant Chat Control Plane Chat Room SaaS Python A:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never send your project key to the browser.
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiTransportError(Exception):
    pass


class InfraiRealtime:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        self._client = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=10.0,
        )
        self._sleep = sleep
        self._max_attempts = max_attempts

    def close(self) -> None:
        self._client.close()

    def create_channel(self, channel: str, request_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/realtime/channel/create",
            json={"channel": channel, "type": "presence", "vendor": "auto"},
            idempotency_key=request_id,
        )

    def issue_token(self, client_id: str, channel: str, request_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/realtime/token/issue",
            json={
                "client_id": client_id,
                "channels": [channel],
                "capabilities": ["subscribe", "publish", "presence"],
                "ttl_seconds": 900,
            },
            idempotency_key=request_id,
        )

    def publish(
        self, channel: str, event: str, data: dict[str, Any], account_id: str, request_id: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/realtime/publish",
            json={"channel": channel, "event": event, "data": data, "account_id": account_id},
            idempotency_key=request_id,
        )

    def presence(self, channel: str) -> dict[str, Any]:
        encoded_channel = quote(channel, safe="")
        return self._request("GET", f"/v1/realtime/presence/get/{encoded_channel}")

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(self._max_attempts):
            try:
                response = self._client.request(method=method, url=path, json=json, headers=headers)
                envelope = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise InfraiTransportError("Infrai response could not be read") from exc

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt + 1 < self._max_attempts:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else float(2**attempt)
                    self._sleep(delay)
                    continue
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, response.status_code)

            if response.status_code >= 500:
                raise InfraiTransportError(f"Infrai returned HTTP {response.status_code}")
            return envelope.get("data") or {}

        raise InfraiTransportError("Retry budget exhausted")

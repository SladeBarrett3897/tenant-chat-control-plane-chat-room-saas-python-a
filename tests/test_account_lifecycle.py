from typing import Any

from fastapi.testclient import TestClient

from tenant_chat.chat_service import create_app


class RecordingRealtime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def create_channel(self, channel: str, request_id: str) -> dict[str, Any]:
        self.calls.append(("create", channel))
        return {"channel": channel}

    def issue_token(self, client_id: str, channel: str, request_id: str) -> dict[str, Any]:
        self.calls.append(("token", channel))
        return {"token": "client-token", "client_id": client_id}

    def publish(
        self, channel: str, event: str, data: dict[str, Any], account_id: str, request_id: str
    ) -> dict[str, Any]:
        self.calls.append(("publish", channel))
        return {"accepted": True}

    def presence(self, channel: str) -> dict[str, Any]:
        self.calls.append(("presence", channel))
        return {"members": []}


def test_suspended_account_cannot_publish_but_admin_can_read_presence() -> None:
    realtime = RecordingRealtime()
    client = TestClient(create_app(realtime))

    onboard = client.post(
        "/accounts", json={"account_id": "acme-eu", "admin_user_id": "user-1"}
    )
    assert onboard.status_code == 201
    assert onboard.json() == {
        "account_id": "acme-eu",
        "channel": "account:acme-eu:lobby",
        "state": "active",
    }

    suspended = client.post("/admin/accounts/acme-eu/suspend")
    rejected = client.post(
        "/accounts/acme-eu/messages", json={"sender_id": "user-1", "text": "hello"}
    )
    presence = client.get("/admin/accounts/acme-eu/presence")

    assert suspended.json()["state"] == "suspended"
    assert rejected.status_code == 409
    assert presence.status_code == 200
    assert realtime.calls[:2] == [
        ("token", "account:acme-eu:lobby"),
        ("create", "account:acme-eu:lobby"),
    ]
    assert ("publish", "account:acme-eu:lobby") not in realtime.calls
    assert realtime.calls[-1] == ("presence", "account:acme-eu:lobby")

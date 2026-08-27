from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .infrai_realtime import InfraiError, InfraiRealtime, InfraiTransportError


class AccountState(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class RealtimePort(Protocol):
    def create_channel(self, channel: str, request_id: str) -> dict[str, Any]:
        pass

    def issue_token(self, client_id: str, channel: str, request_id: str) -> dict[str, Any]:
        pass

    def publish(
        self, channel: str, event: str, data: dict[str, Any], account_id: str, request_id: str
    ) -> dict[str, Any]:
        pass

    def presence(self, channel: str) -> dict[str, Any]:
        pass


@dataclass
class Account:
    account_id: str
    channel: str
    state: AccountState


class AccountStore:
    def __init__(self) -> None:
        self._accounts: dict[str, Account] = {}

    def add(self, account: Account) -> None:
        self._accounts[account.account_id] = account

    def require(self, account_id: str) -> Account:
        account = self._accounts.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        return account


class OnboardTenant(BaseModel):
    account_id: str = Field(min_length=1, pattern=r"^[a-z0-9-]+$")
    admin_user_id: str = Field(min_length=1)


class IssueChatToken(BaseModel):
    user_id: str = Field(min_length=1)


class PublishMessage(BaseModel):
    sender_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=4000)


class AccountView(BaseModel):
    account_id: str
    channel: str
    state: AccountState


def create_app(realtime: RealtimePort | None = None) -> FastAPI:
    app = FastAPI(title="Tenant chat control plane")
    store = AccountStore()

    def get_realtime() -> RealtimePort:
        if realtime is not None:
            return realtime
        api_key = os.environ.get("INFRAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="INFRAI_API_KEY is required")
        return InfraiRealtime(api_key)

    def active_account(account_id: str) -> Account:
        account = store.require(account_id)
        if account.state is not AccountState.ACTIVE:
            raise HTTPException(status_code=409, detail="Account is suspended")
        return account

    @app.exception_handler(InfraiError)
    async def infrai_rejection(_: Request, exc: InfraiError):
        from fastapi.responses import JSONResponse

        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        return JSONResponse(status_code=status, content={"detail": exc.detail, "code": exc.code})

    @app.exception_handler(InfraiTransportError)
    async def infrai_transport(_: Request, exc: InfraiTransportError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.post("/accounts", response_model=AccountView, status_code=201)
    def onboard(body: OnboardTenant, client: RealtimePort = Depends(get_realtime)) -> Account:
        channel = f"account:{body.account_id}:lobby"
        request_id = str(uuid4())
        client.issue_token(body.admin_user_id, channel, request_id + ":admin")
        client.create_channel(channel, request_id)
        account = Account(body.account_id, channel, AccountState.ACTIVE)
        store.add(account)
        return account

    @app.post("/accounts/{account_id}/tokens")
    def token(account_id: str, body: IssueChatToken, client: RealtimePort = Depends(get_realtime)):
        account = active_account(account_id)
        return client.issue_token(body.user_id, account.channel, str(uuid4()))

    @app.post("/accounts/{account_id}/messages")
    def message(account_id: str, body: PublishMessage, client: RealtimePort = Depends(get_realtime)):
        account = active_account(account_id)
        return client.publish(
            account.channel,
            "chat.message",
            {"sender_id": body.sender_id, "text": body.text},
            account_id,
            str(uuid4()),
        )

    @app.post("/admin/accounts/{account_id}/suspend", response_model=AccountView)
    def suspend(account_id: str) -> Account:
        account = store.require(account_id)
        account.state = AccountState.SUSPENDED
        return account

    @app.get("/admin/accounts/{account_id}/presence")
    def presence(account_id: str, client: RealtimePort = Depends(get_realtime)):
        return client.presence(store.require(account_id).channel)

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("tenant_chat.chat_service:app", host="127.0.0.1", port=8000)

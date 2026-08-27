import os

import httpx


def main() -> None:
    service_url = os.environ.get("CHAT_SERVICE_URL", "http://127.0.0.1:8000")
    response = httpx.request(
        method="POST",
        url=f"{service_url}/accounts",
        json={"account_id": "acme-eu", "admin_user_id": "user-1"},
        timeout=10.0,
    )
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()

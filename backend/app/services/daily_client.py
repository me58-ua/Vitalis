import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID


class DailyUnavailableError(Exception):
    pass


class DailyClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_or_create_room(self, name: str) -> str:
        path = f"/rooms/{name}"
        room = self._request(path, missing_ok=True)
        if room is None:
            try:
                room = self._request("/rooms", {
                    "name": name,
                    "privacy": "private",
                    "properties": {
                        "max_participants": 2,
                        "enable_prejoin_ui": True,
                        "enable_knocking": False,
                        "enable_chat": False,
                        "lang": "es",
                    },
                })
            except DailyUnavailableError:
                # Another join request may have created the room in the meantime.
                room = self._request(path)
        if room.get("privacy") != "private" or not isinstance(room.get("url"), str):
            raise DailyUnavailableError("Daily did not return a private room")
        return room["url"]

    def create_token(self, room_name: str, user_id: UUID, is_owner: bool, expires_at: datetime) -> str:
        response = self._request("/meeting-tokens", {"properties": {
            "room_name": room_name,
            "user_id": str(user_id),
            "is_owner": is_owner,
            "exp": int(expires_at.timestamp()),
            "enable_recording_ui": False,
            "enable_live_captions_ui": False,
        }})
        token = response.get("token")
        if not isinstance(token, str) or not token:
            raise DailyUnavailableError("Daily did not issue a meeting token")
        return token

    def _request(self, path: str, payload: dict | None = None, *, missing_ok: bool = False):
        request = Request(
            f"https://api.daily.co/v1{path}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=5) as response:
                result = json.load(response)
        except HTTPError as error:
            if missing_ok and error.code == 404:
                return None
            raise DailyUnavailableError(f"Daily API request failed (HTTP {error.code})") from error
        except (URLError, OSError, ValueError) as error:
            raise DailyUnavailableError("Daily API is unavailable") from error
        if not isinstance(result, dict):
            raise DailyUnavailableError("Daily returned an invalid response")
        return result

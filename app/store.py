from __future__ import annotations

import asyncio
import base64
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.env import load_env_file


load_env_file()

JsonMap = dict[str, Any]
state_store_backend = "memory"
state_store_error: str | None = None
REWARD_ECONOMY_VERSION = 2


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def safe_doc_id(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


class StateStore:
    async def get_device_session(self, device_id: str) -> JsonMap | None:
        raise NotImplementedError

    async def save_device_session(self, device_id: str, session: JsonMap) -> None:
        raise NotImplementedError

    async def get_token_device(self, token: str) -> str | None:
        raise NotImplementedError

    async def save_token_device(self, token: str, device_id: str) -> None:
        raise NotImplementedError

    async def get_engagement(self, device_id: str) -> JsonMap:
        raise NotImplementedError

    async def save_engagement(self, device_id: str, state: JsonMap) -> None:
        raise NotImplementedError

    async def save_watch_progress(self, device_id: str, film_id: int, episode_ref: int, progress: JsonMap) -> None:
        raise NotImplementedError

    async def list_watch_progress(self, device_id: str) -> list[JsonMap]:
        raise NotImplementedError

    async def save_event(self, device_id: str, event_type: str, payload: JsonMap) -> None:
        raise NotImplementedError

    async def save_feedback(self, device_id: str, payload: JsonMap) -> None:
        raise NotImplementedError

    async def list_planner_items(self, device_id: str) -> list[JsonMap]:
        raise NotImplementedError

    async def save_planner_item(self, device_id: str, item: JsonMap) -> JsonMap:
        raise NotImplementedError

    async def delete_planner_item(self, device_id: str, item_id: str) -> None:
        raise NotImplementedError

    async def list_notifications(self, device_id: str) -> list[JsonMap]:
        raise NotImplementedError

    async def save_notification(self, device_id: str, payload: JsonMap) -> JsonMap:
        raise NotImplementedError

    async def mark_notification_read(self, device_id: str, notification_id: str) -> None:
        raise NotImplementedError

    async def get_rewards(self, device_id: str) -> JsonMap:
        raise NotImplementedError

    async def save_rewards(self, device_id: str, rewards: JsonMap) -> None:
        raise NotImplementedError


def empty_engagement_state() -> JsonMap:
    return {
        "followed_films": [],
        "unfollowed_films": [],
        "liked_episodes": [],
        "unliked_episodes": [],
        "reminded_films": [],
        "unreminded_films": [],
    }


class MemoryStateStore(StateStore):
    def __init__(self) -> None:
        self._sessions: dict[str, JsonMap] = {}
        self._tokens: dict[str, str] = {}
        self._engagement: dict[str, JsonMap] = {}
        self._watch_progress: dict[str, JsonMap] = {}
        self._planner: dict[str, JsonMap] = {}
        self._notifications: dict[str, JsonMap] = {}
        self._rewards: dict[str, JsonMap] = {}
        self._events: list[JsonMap] = []
        self._lock = asyncio.Lock()

    async def get_device_session(self, device_id: str) -> JsonMap | None:
        async with self._lock:
            session = self._sessions.get(device_id)
            return dict(session) if session else None

    async def save_device_session(self, device_id: str, session: JsonMap) -> None:
        async with self._lock:
            self._sessions[device_id] = {**session, "updated_at": utc_now_iso()}

    async def get_token_device(self, token: str) -> str | None:
        async with self._lock:
            return self._tokens.get(token)

    async def save_token_device(self, token: str, device_id: str) -> None:
        async with self._lock:
            self._tokens[token] = device_id

    async def get_engagement(self, device_id: str) -> JsonMap:
        async with self._lock:
            state = self._engagement.setdefault(device_id, empty_engagement_state())
            return {key: list(value) for key, value in state.items()}

    async def save_engagement(self, device_id: str, state: JsonMap) -> None:
        async with self._lock:
            self._engagement[device_id] = {**state, "updated_at": utc_now_iso()}

    async def save_watch_progress(self, device_id: str, film_id: int, episode_ref: int, progress: JsonMap) -> None:
        key = f"{device_id}:{film_id}:{episode_ref}"
        async with self._lock:
            self._watch_progress[key] = {
                **progress,
                "device_id": device_id,
                "film_id": film_id,
                "episode": episode_ref,
                "updated_at": utc_now_iso(),
            }

    async def list_watch_progress(self, device_id: str) -> list[JsonMap]:
        async with self._lock:
            rows = [
                dict(progress)
                for progress in self._watch_progress.values()
                if progress.get("device_id") == device_id
            ]
        return sorted(rows, key=lambda progress: str(progress.get("updated_at", "")), reverse=True)

    async def save_event(self, device_id: str, event_type: str, payload: JsonMap) -> None:
        async with self._lock:
            self._events.append(
                {
                    "device_id": device_id,
                    "event_type": event_type,
                    "payload": payload,
                    "created_at": utc_now_iso(),
                }
            )

    async def save_feedback(self, device_id: str, payload: JsonMap) -> None:
        async with self._lock:
            self._events.append(
                {
                    "device_id": device_id,
                    "event_type": "feedback",
                    "payload": payload,
                    "created_at": utc_now_iso(),
                }
            )

    async def list_planner_items(self, device_id: str) -> list[JsonMap]:
        async with self._lock:
            rows = [dict(item) for item in self._planner.values() if item.get("device_id") == device_id]
        return sorted(rows, key=lambda item: str(item.get("scheduled_at", "")))

    async def save_planner_item(self, device_id: str, item: JsonMap) -> JsonMap:
        item_id = str(item.get("id") or safe_doc_id(f"{device_id}:{item.get('film_id')}:{item.get('scheduled_at')}"))
        row = {**item, "id": item_id, "device_id": device_id, "updated_at": utc_now_iso()}
        async with self._lock:
            self._planner[f"{device_id}:{item_id}"] = row
        return dict(row)

    async def delete_planner_item(self, device_id: str, item_id: str) -> None:
        async with self._lock:
            self._planner.pop(f"{device_id}:{item_id}", None)

    async def list_notifications(self, device_id: str) -> list[JsonMap]:
        async with self._lock:
            rows = [dict(item) for item in self._notifications.values() if item.get("device_id") == device_id]
        return sorted(rows, key=lambda item: str(item.get("created_at", "")), reverse=True)

    async def save_notification(self, device_id: str, payload: JsonMap) -> JsonMap:
        notification_id = str(payload.get("id") or safe_doc_id(f"{device_id}:{utc_now_iso()}:{payload.get('title')}"))
        row = {
            **payload,
            "id": notification_id,
            "device_id": device_id,
            "read": bool(payload.get("read", False)),
            "created_at": payload.get("created_at") or utc_now_iso(),
        }
        async with self._lock:
            self._notifications[f"{device_id}:{notification_id}"] = row
        return dict(row)

    async def mark_notification_read(self, device_id: str, notification_id: str) -> None:
        async with self._lock:
            key = f"{device_id}:{notification_id}"
            if key in self._notifications:
                self._notifications[key] = {**self._notifications[key], "read": True}

    async def get_rewards(self, device_id: str) -> JsonMap:
        async with self._lock:
            rewards = self._rewards.setdefault(device_id, default_rewards_state(device_id))
            return dict(rewards)

    async def save_rewards(self, device_id: str, rewards: JsonMap) -> None:
        async with self._lock:
            self._rewards[device_id] = {**rewards, "device_id": device_id, "updated_at": utc_now_iso()}


@dataclass
class FirestoreStateStore(StateStore):
    db: Any
    prefix: str = "dramaverse"

    def _collection(self, name: str) -> Any:
        return self.db.collection(f"{self.prefix}_{name}")

    async def _to_thread(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(func, *args, **kwargs)

    async def get_device_session(self, device_id: str) -> JsonMap | None:
        snapshot = await self._to_thread(self._collection("device_sessions").document(safe_doc_id(device_id)).get)
        data = snapshot.to_dict() if snapshot.exists else None
        return data if isinstance(data, dict) else None

    async def save_device_session(self, device_id: str, session: JsonMap) -> None:
        await self._to_thread(
            self._collection("device_sessions").document(safe_doc_id(device_id)).set,
            {**session, "updated_at": utc_now_iso()},
            merge=True,
        )

    async def get_token_device(self, token: str) -> str | None:
        snapshot = await self._to_thread(self._collection("wrapper_tokens").document(safe_doc_id(token)).get)
        data = snapshot.to_dict() if snapshot.exists else None
        device_id = data.get("device_id") if isinstance(data, dict) else None
        return device_id if isinstance(device_id, str) else None

    async def save_token_device(self, token: str, device_id: str) -> None:
        await self._to_thread(
            self._collection("wrapper_tokens").document(safe_doc_id(token)).set,
            {"device_id": device_id, "updated_at": utc_now_iso()},
            merge=True,
        )

    async def get_engagement(self, device_id: str) -> JsonMap:
        snapshot = await self._to_thread(self._collection("engagement").document(safe_doc_id(device_id)).get)
        data = snapshot.to_dict() if snapshot.exists else None
        return data if isinstance(data, dict) else empty_engagement_state()

    async def save_engagement(self, device_id: str, state: JsonMap) -> None:
        await self._to_thread(
            self._collection("engagement").document(safe_doc_id(device_id)).set,
            {**state, "updated_at": utc_now_iso()},
            merge=True,
        )

    async def save_watch_progress(self, device_id: str, film_id: int, episode_ref: int, progress: JsonMap) -> None:
        doc_id = safe_doc_id(f"{device_id}:{film_id}:{episode_ref}")
        await self._to_thread(
            self._collection("watch_progress").document(doc_id).set,
            {
                **progress,
                "device_id": device_id,
                "film_id": film_id,
                "episode": episode_ref,
                "updated_at": utc_now_iso(),
            },
            merge=True,
        )

    async def list_watch_progress(self, device_id: str) -> list[JsonMap]:
        query = self._collection("watch_progress").where("device_id", "==", device_id)
        snapshots = await self._to_thread(lambda: list(query.stream()))
        rows = [snapshot.to_dict() for snapshot in snapshots]
        return sorted(
            [row for row in rows if isinstance(row, dict)],
            key=lambda progress: str(progress.get("updated_at", "")),
            reverse=True,
        )

    async def save_event(self, device_id: str, event_type: str, payload: JsonMap) -> None:
        await self._to_thread(
            self._collection("events").document().set,
            {
                "device_id": device_id,
                "event_type": event_type,
                "payload": payload,
                "created_at": utc_now_iso(),
            },
        )

    async def save_feedback(self, device_id: str, payload: JsonMap) -> None:
        await self._to_thread(
            self._collection("feedback").document().set,
            {
                "device_id": device_id,
                **payload,
                "created_at": utc_now_iso(),
            },
        )

    async def list_planner_items(self, device_id: str) -> list[JsonMap]:
        query = self._collection("planner").where("device_id", "==", device_id)
        snapshots = await self._to_thread(lambda: list(query.stream()))
        rows = [snapshot.to_dict() for snapshot in snapshots]
        return sorted([row for row in rows if isinstance(row, dict)], key=lambda item: str(item.get("scheduled_at", "")))

    async def save_planner_item(self, device_id: str, item: JsonMap) -> JsonMap:
        item_id = str(item.get("id") or safe_doc_id(f"{device_id}:{item.get('film_id')}:{item.get('scheduled_at')}"))
        row = {**item, "id": item_id, "device_id": device_id, "updated_at": utc_now_iso()}
        await self._to_thread(self._collection("planner").document(item_id).set, row, merge=True)
        return row

    async def delete_planner_item(self, device_id: str, item_id: str) -> None:
        await self._to_thread(self._collection("planner").document(item_id).delete)

    async def list_notifications(self, device_id: str) -> list[JsonMap]:
        query = self._collection("notifications").where("device_id", "==", device_id)
        snapshots = await self._to_thread(lambda: list(query.stream()))
        rows = [snapshot.to_dict() for snapshot in snapshots]
        return sorted([row for row in rows if isinstance(row, dict)], key=lambda item: str(item.get("created_at", "")), reverse=True)

    async def save_notification(self, device_id: str, payload: JsonMap) -> JsonMap:
        notification_id = str(payload.get("id") or safe_doc_id(f"{device_id}:{utc_now_iso()}:{payload.get('title')}"))
        row = {
            **payload,
            "id": notification_id,
            "device_id": device_id,
            "read": bool(payload.get("read", False)),
            "created_at": payload.get("created_at") or utc_now_iso(),
        }
        await self._to_thread(self._collection("notifications").document(notification_id).set, row, merge=True)
        return row

    async def mark_notification_read(self, device_id: str, notification_id: str) -> None:
        await self._to_thread(
            self._collection("notifications").document(notification_id).set,
            {"read": True, "updated_at": utc_now_iso()},
            merge=True,
        )

    async def get_rewards(self, device_id: str) -> JsonMap:
        snapshot = await self._to_thread(self._collection("rewards").document(safe_doc_id(device_id)).get)
        data = snapshot.to_dict() if snapshot.exists else None
        return data if isinstance(data, dict) else default_rewards_state(device_id)

    async def save_rewards(self, device_id: str, rewards: JsonMap) -> None:
        await self._to_thread(
            self._collection("rewards").document(safe_doc_id(device_id)).set,
            {**rewards, "device_id": device_id, "updated_at": utc_now_iso()},
            merge=True,
        )


def default_rewards_state(device_id: str) -> JsonMap:
    return {
        "device_id": device_id,
        "economy_version": REWARD_ECONOMY_VERSION,
        "coins": 0,
        "vip": False,
        "check_in_day": 1,
        "last_check_in": None,
        "last_spin_week": None,
        "claimed_task_day": None,
        "claimed_tasks": [],
        "spin_available": 1,
        "watch_minutes_today": 0,
        "achievements": [],
        "actions": [],
    }


def build_state_store() -> StateStore:
    global state_store_backend, state_store_error
    use_firestore = os.getenv("FIRESTORE_ENABLED", "").lower() in {"1", "true", "yes"} or bool(
        os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("FIREBASE_PROJECT_ID")
    )
    if not use_firestore:
        state_store_backend = "memory"
        state_store_error = None
        return MemoryStateStore()

    try:
        from google.cloud import firestore
    except ImportError:
        state_store_backend = "memory"
        state_store_error = "google-cloud-firestore is not installed"
        return MemoryStateStore()

    project = os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or None
    database = os.getenv("FIRESTORE_DATABASE")
    client_kwargs = {"project": project} if project else {}
    if database:
        client_kwargs["database"] = database
    try:
        client = firestore.Client(**client_kwargs)
    except Exception as exc:
        state_store_backend = "memory"
        state_store_error = f"{type(exc).__name__}: {exc}"
        return MemoryStateStore()
    state_store_backend = "firestore"
    state_store_error = None
    return FirestoreStateStore(client, os.getenv("FIRESTORE_COLLECTION_PREFIX", "dramaverse"))


state_store = build_state_store()

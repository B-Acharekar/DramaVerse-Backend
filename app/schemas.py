from __future__ import annotations

from pydantic import BaseModel, Field


class DeviceAuthRequest(BaseModel):
    device_id: str = Field(..., examples=["android-install-id-123"])
    language: str = Field("hi", examples=["hi"])


class WatchProgressRequest(BaseModel):
    progress_seconds: int = Field(..., ge=0, examples=[42])
    duration_seconds: int | None = Field(None, ge=0, examples=[180])
    completed: bool = Field(False, examples=[False])


class PlannerItemRequest(BaseModel):
    film_id: int = Field(..., ge=1, examples=[167])
    title: str = Field(..., min_length=1, max_length=160, examples=["The Secret Vow"])
    episode: int | None = Field(None, ge=1, examples=[4])
    scheduled_at: str = Field(..., examples=["2026-07-11T20:30:00+05:30"])
    note: str | None = Field(None, max_length=280, examples=["Watch before the finale drops"])
    image_url: str | None = Field(None, max_length=1000)
    remind_before_minutes: int = Field(15, ge=0, le=10080)


class RewardActionRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=80, examples=["daily_check_in"])
    amount: int = Field(0, ge=0, examples=[10])
    metadata: dict[str, object] = Field(default_factory=dict)


class NotificationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120, examples=["Episode reminder"])
    body: str = Field(..., min_length=1, max_length=280, examples=["The Secret Vow starts soon."])
    type: str = Field("general", max_length=40, examples=["planner"])
    metadata: dict[str, object] = Field(default_factory=dict)

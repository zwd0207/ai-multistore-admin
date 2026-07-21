from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceEnvironmentCreate(BaseModel):
    store_id: int
    environment_name: str = Field(..., min_length=1, max_length=200)
    device_type: str = Field(..., min_length=1, max_length=50)
    os_name: str | None = Field(default=None, max_length=100)
    browser_name: str | None = Field(default=None, max_length=100)
    ip_label: str | None = Field(default=None, max_length=120)
    proxy_label: str | None = Field(default=None, max_length=120)
    status: str = Field(default="active", min_length=1, max_length=30)
    last_used_at: datetime | None = None
    remark: str | None = None


class DeviceEnvironmentUpdate(BaseModel):
    store_id: int | None = None
    environment_name: str | None = Field(default=None, min_length=1, max_length=200)
    device_type: str | None = Field(default=None, min_length=1, max_length=50)
    os_name: str | None = Field(default=None, max_length=100)
    browser_name: str | None = Field(default=None, max_length=100)
    ip_label: str | None = Field(default=None, max_length=120)
    proxy_label: str | None = Field(default=None, max_length=120)
    status: str | None = Field(default=None, min_length=1, max_length=30)
    last_used_at: datetime | None = None
    remark: str | None = None


class DeviceEnvironmentRead(DeviceEnvironmentCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

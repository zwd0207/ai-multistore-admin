"""Verify the PXG cleanup scheduler lifecycle without waiting in real time."""

import asyncio
import os
import sys
import tempfile
from contextlib import suppress
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEMP_DB = Path(tempfile.gettempdir()) / "verify-pxg-naver-readonly-scheduler.db"
os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEMP_DB.as_posix()}",
    "APP_ENV": "test",
    "ALLOW_DEV_AUTH": "true",
})

from app.config import Settings
from app.main import run_pxg_naver_cleanup_scheduler


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


async def verify_enabled_scheduler() -> None:
    cleanup_calls: list[int] = []
    intervals: list[float] = []

    def cleanup_runner(_db, *, settings) -> None:
        assert settings.pxg_naver_local_read_retention_cleanup_enabled is True
        cleanup_calls.append(1)

    async def sleep_fn(delay: float) -> None:
        intervals.append(delay)
        if len(intervals) >= 2:
            raise asyncio.CancelledError

    with suppress(asyncio.CancelledError):
        await run_pxg_naver_cleanup_scheduler(
            runtime_settings=Settings(pxg_naver_local_read_retention_cleanup_enabled=True),
            session_factory=FakeSession,
            cleanup_runner=cleanup_runner,
            sleep_fn=sleep_fn,
        )
    assert len(cleanup_calls) == 2, cleanup_calls
    assert intervals == [24 * 60 * 60, 24 * 60 * 60], intervals


async def verify_disabled_scheduler() -> None:
    cleanup_calls: list[int] = []
    session_calls: list[int] = []

    def session_factory():
        session_calls.append(1)
        return FakeSession()

    async def sleep_fn(delay: float) -> None:
        assert delay == 24 * 60 * 60
        raise asyncio.CancelledError

    with suppress(asyncio.CancelledError):
        await run_pxg_naver_cleanup_scheduler(
            runtime_settings=Settings(pxg_naver_local_read_retention_cleanup_enabled=False),
            session_factory=session_factory,
            cleanup_runner=lambda *_args, **_kwargs: cleanup_calls.append(1),
            sleep_fn=sleep_fn,
        )
    assert cleanup_calls == [] and session_calls == []


async def verify_cancellation() -> None:
    sleeping = asyncio.Event()

    async def sleep_fn(_delay: float) -> None:
        sleeping.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(run_pxg_naver_cleanup_scheduler(
        runtime_settings=Settings(pxg_naver_local_read_retention_cleanup_enabled=False),
        session_factory=FakeSession,
        cleanup_runner=lambda *_args, **_kwargs: None,
        sleep_fn=sleep_fn,
    ))
    await sleeping.wait()
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    assert task.cancelled()


def main() -> None:
    asyncio.run(verify_enabled_scheduler())
    asyncio.run(verify_disabled_scheduler())
    asyncio.run(verify_cancellation())
    print("verify_pxg_naver_readonly_scheduler: ok")


if __name__ == "__main__":
    main()

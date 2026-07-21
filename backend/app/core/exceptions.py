from typing import Any


class ApiError(Exception):
    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 400,
        detail: Any | None = None,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.detail = detail

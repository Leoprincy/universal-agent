class ApplicationError(Exception):
    """Base class for errors that are safe to map to an API response."""

    code = "application_error"
    status_code = 400

    def __init__(self, message: str, code: str | None = None, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(ApplicationError):
    code = "not_found"
    status_code = 404


class ConflictError(ApplicationError):
    code = "conflict"
    status_code = 409


class UnauthorizedError(ApplicationError):
    code = "unauthorized"
    status_code = 401


class ForbiddenError(ApplicationError):
    code = "forbidden"
    status_code = 403


class UnprocessableEntityError(ApplicationError):
    code = "unprocessable_entity"
    status_code = 422


class RateLimitError(ApplicationError):
    code = "rate_limited"
    status_code = 429

class ApplicationError(Exception):
    """Base class for errors that are safe to map to an API response."""

    code = "application_error"
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


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

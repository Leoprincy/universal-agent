class ApplicationError(Exception):
    """Base class for errors that are safe to map to an API response."""

    code = "application_error"
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

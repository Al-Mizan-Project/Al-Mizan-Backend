class ApplicationException(Exception):
    """
    Base exception for application-level errors.
    """
    def __init__(self, message: str = "Application error"):
        self.message = message
        super().__init__(self.message)


# ---------------------------
# GENERIC ERRORS
# ---------------------------

class NotFoundException(ApplicationException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message)


class ConflictException(ApplicationException):
    def __init__(self, message: str = "Conflict occurred"):
        super().__init__(message)


class ValidationException(ApplicationException):
    def __init__(self, message: str = "Validation error"):
        super().__init__(message)


class UnauthorizedException(ApplicationException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message)


# ---------------------------
# INFRASTRUCTURE / EXTERNAL
# ---------------------------

class ExternalServiceException(ApplicationException):
    def __init__(self, message: str = "External service error"):
        super().__init__(message)


class ServiceUnavailableException(ApplicationException):
    def __init__(self, message: str = "Service unavailable"):
        super().__init__(message)


class TimeoutException(ApplicationException):
    def __init__(self, message: str = "Request timeout"):
        super().__init__(message)
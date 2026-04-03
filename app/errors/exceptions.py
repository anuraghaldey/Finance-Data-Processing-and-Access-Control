class AppException(Exception):
    """Base exception for the application."""
    def __init__(self, message, status_code=400, payload=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload


class ValidationException(AppException):
    def __init__(self, message='Validation error', errors=None):
        super().__init__(message, status_code=422, payload={'errors': errors})


class AuthenticationException(AppException):
    def __init__(self, message='Authentication failed'):
        super().__init__(message, status_code=401)


class AuthorizationException(AppException):
    def __init__(self, message='Insufficient permissions'):
        super().__init__(message, status_code=403)


class NotFoundException(AppException):
    def __init__(self, resource='Resource'):
        super().__init__(f'{resource} not found', status_code=404)


class ConflictException(AppException):
    def __init__(self, message='Resource already exists'):
        super().__init__(message, status_code=409)


class RateLimitException(AppException):
    def __init__(self, message='Rate limit exceeded'):
        super().__init__(message, status_code=429)


class ServiceUnavailableException(AppException):
    def __init__(self, message='Service temporarily unavailable'):
        super().__init__(message, status_code=503)

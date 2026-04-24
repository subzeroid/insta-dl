class InstaDlError(Exception):
    pass


class BackendError(InstaDlError):
    pass


class AuthError(BackendError):
    pass


class NotFoundError(BackendError):
    pass


class UnsupportedByBackendError(BackendError):
    pass


class RateLimitedError(BackendError):
    pass

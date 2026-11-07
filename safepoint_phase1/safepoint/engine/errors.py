class SafeFileError(Exception):
    """Base class for expected, user-reportable errors."""


class StoreError(SafeFileError):
    """A backup destination is unreachable, unwritable or rejected a request."""


class HashMismatch(SafeFileError):
    """Data did not match its expected SHA-256."""


class SourceChanged(SafeFileError):
    """A source file changed or became unreadable while it was being backed up."""


class Cancelled(SafeFileError):
    """The user cancelled the running task."""

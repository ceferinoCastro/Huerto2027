class DomainConflictError(ValueError):
    """Raised when a domain uniqueness or state rule would be violated."""


class DomainNotFoundError(ValueError):
    """Raised when a requested domain entity does not exist."""


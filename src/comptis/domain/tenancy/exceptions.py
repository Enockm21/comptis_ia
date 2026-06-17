class MissingTenantContextError(Exception):
    """Raised when a scoped DB query is attempted without tenant context set in the session."""

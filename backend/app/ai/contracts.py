class AIProviderError(RuntimeError):
    """Raised when the configured model provider cannot complete a request."""


class AIInvalidOutputError(RuntimeError):
    """Raised when a model response is missing or fails schema parsing."""


class AINotConfiguredError(AIProviderError):
    """Raised when an AI workflow has no configured backend credential."""

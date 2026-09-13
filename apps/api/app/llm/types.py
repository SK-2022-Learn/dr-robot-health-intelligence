"""Safe provider-level failures."""


class LLMError(Exception):
    """Base failure that never contains submitted document content."""


class LLMUnavailableError(LLMError):
    """The configured provider or model cannot be reached."""


class LLMResponseError(LLMError):
    """The provider response is missing or malformed."""

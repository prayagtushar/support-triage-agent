from __future__ import annotations


class TriageError(Exception):
    """Base for errors this project raises deliberately."""


class ModelOutputInvalid(TriageError):
    """A model returned output that failed schema validation twice."""

    def __init__(self, model: str, attempts: list[str], detail: str) -> None:
        self.model = model
        self.attempts = attempts
        self.detail = detail
        super().__init__(
            f"{model} produced invalid output after {len(attempts)} attempts: {detail}"
        )


class ModelOutputTruncated(TriageError):
    """The model hit its token budget before producing any content."""


class ProviderUnavailable(TriageError):
    """A provider could not be reached, or refused the request after retries."""


class EmbeddingFailed(TriageError):
    """The embedding endpoint returned an unusable response."""

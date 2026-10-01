"""Custom exception classes for Paperless Intelligence.

This module defines domain-specific exceptions for better error handling
and debugging throughout the application.
"""

from __future__ import annotations


class PaperlessIntelligenceError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "GENERAL_ERROR"


# Processing Errors
class ProcessingError(PaperlessIntelligenceError):
    """Base class for document processing errors."""

    pass


class DocumentNotFoundError(ProcessingError):
    """Requested document does not exist."""

    def __init__(self, doc_id: int) -> None:
        super().__init__(f"Document {doc_id} not found", "DOCUMENT_NOT_FOUND")
        self.doc_id = doc_id


# Queue and Worker Errors
class QueueError(PaperlessIntelligenceError):
    """Base class for queue-related errors."""

    pass


class WorkerError(QueueError):
    """Error during worker task execution."""

    def __init__(
        self,
        message: str,
        task: str | None = None,
        attempt: int | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        super().__init__(message, "WORKER_ERROR")
        self.task = task
        self.attempt = attempt
        self.original_exception = original_exception
        self.original_type = type(original_exception).__name__ if original_exception else None


# Validation Errors
class ValidationError(PaperlessIntelligenceError):
    """Input validation error."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message, "VALIDATION_ERROR")
        self.field = field

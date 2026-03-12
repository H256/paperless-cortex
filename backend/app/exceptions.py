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


# Integration Errors
class IntegrationError(PaperlessIntelligenceError):
    """Base class for external integration errors."""

    pass


class PaperlessAPIError(IntegrationError):
    """Error communicating with Paperless-NGX API."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message, "PAPERLESS_API_ERROR")
        self.status_code = status_code


class QdrantError(IntegrationError):
    """Error communicating with Qdrant vector database."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "QDRANT_ERROR")


class LLMError(IntegrationError):
    """Error communicating with LLM provider."""

    def __init__(
        self, message: str, model: str | None = None, retry_after: float | None = None
    ) -> None:
        super().__init__(message, "LLM_ERROR")
        self.model = model
        self.retry_after = retry_after


# Processing Errors
class ProcessingError(PaperlessIntelligenceError):
    """Base class for document processing errors."""

    pass


class DocumentNotFoundError(ProcessingError):
    """Requested document does not exist."""

    def __init__(self, doc_id: int) -> None:
        super().__init__(f"Document {doc_id} not found", "DOCUMENT_NOT_FOUND")
        self.doc_id = doc_id


class InvalidDocumentError(ProcessingError):
    """Document is in an invalid state for the requested operation."""

    def __init__(self, message: str, doc_id: int | None = None) -> None:
        super().__init__(message, "INVALID_DOCUMENT")
        self.doc_id = doc_id


class OCRProcessingError(ProcessingError):
    """Error during OCR processing."""

    def __init__(self, message: str, doc_id: int | None = None, page: int | None = None) -> None:
        super().__init__(message, "OCR_PROCESSING_ERROR")
        self.doc_id = doc_id
        self.page = page


class EmbeddingError(ProcessingError):
    """Error generating or storing embeddings."""

    def __init__(self, message: str, doc_id: int | None = None) -> None:
        super().__init__(message, "EMBEDDING_ERROR")
        self.doc_id = doc_id


class SuggestionGenerationError(ProcessingError):
    """Error generating metadata suggestions."""

    def __init__(self, message: str, doc_id: int | None = None, source: str | None = None) -> None:
        super().__init__(message, "SUGGESTION_GENERATION_ERROR")
        self.doc_id = doc_id
        self.source = source


# Configuration Errors
class ConfigurationError(PaperlessIntelligenceError):
    """Application configuration is invalid or incomplete."""

    def __init__(self, message: str, config_key: str | None = None) -> None:
        super().__init__(message, "CONFIGURATION_ERROR")
        self.config_key = config_key


# Queue and Worker Errors
class QueueError(PaperlessIntelligenceError):
    """Base class for queue-related errors."""

    pass


class QueueDisabledError(QueueError):
    """Operation requires queue mode but it is not enabled."""

    def __init__(self) -> None:
        super().__init__("Queue mode is not enabled", "QUEUE_DISABLED")


class TaskNotFoundError(QueueError):
    """Requested task does not exist in the queue."""

    def __init__(self, task_id: str) -> None:
        super().__init__(f"Task {task_id} not found", "TASK_NOT_FOUND")
        self.task_id = task_id


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


# Writeback Errors
class WritebackError(PaperlessIntelligenceError):
    """Base class for writeback operation errors."""

    pass


class WritebackDisabledError(WritebackError):
    """Writeback execution is not enabled."""

    def __init__(self) -> None:
        super().__init__("Writeback execution is not enabled", "WRITEBACK_DISABLED")


class WritebackValidationError(WritebackError):
    """Writeback payload validation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "WRITEBACK_VALIDATION_ERROR")


class WritebackConflictError(WritebackError):
    """Writeback conflict with remote state."""

    def __init__(self, message: str, doc_id: int | None = None) -> None:
        super().__init__(message, "WRITEBACK_CONFLICT")
        self.doc_id = doc_id


# Validation Errors
class ValidationError(PaperlessIntelligenceError):
    """Input validation error."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message, "VALIDATION_ERROR")
        self.field = field

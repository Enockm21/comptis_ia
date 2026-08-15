from enum import StrEnum


class CategorizationSource(StrEnum):
    PATTERN = "pattern"
    RAG = "rag"


class CategorizationStatut(StrEnum):
    AUTO_VALIDATED = "auto_validated"
    PENDING_REVIEW = "pending_review"
    HUMAN_VALIDATED = "human_validated"

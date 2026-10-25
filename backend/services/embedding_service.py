"""
VIDYORA AI - Dedicated Embedding Service (Step 17)

Provides a clean, modular abstraction for generating dense vector embeddings from
text chunks and search queries using Google GenAI (text-embedding-004) or mock providers.

Architectural Decisions:
- BaseEmbeddingProvider abstraction enables hot-swapping embedding models (e.g.
  Google text-embedding-004, OpenAI, or local HuggingFace models) without touching
  repositories or API endpoints.
- Strict vector dimensionality validation (expected: 768) ensures database vector
  compatibility before executing SQL inserts.
- Zero key leakage: API keys are encapsulated in the provider and never included
  in log statements, exception traces, or error payloads.
- Batch embedding support minimizes network round-trips when indexing multiple chunks.
"""

from abc import ABC, abstractmethod
import hashlib
import logging
import math
from typing import List, Optional, Union

from config import settings

logger = logging.getLogger(__name__)


# ===========================================================================
# 1. Custom Exceptions
# ===========================================================================
class EmbeddingServiceError(Exception):
    """Base exception for all embedding generation and validation errors."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class EmbeddingConfigurationError(EmbeddingServiceError):
    """Raised when the embedding provider is misconfigured (e.g. missing API key)."""
    def __init__(self, message: str):
        super().__init__(message, status_code=500)


class EmbeddingDimensionMismatchError(EmbeddingServiceError):
    """Raised when the returned vector dimensionality does not match the configured schema."""
    def __init__(self, expected: int, received: int):
        super().__init__(
            f"Embedding vector dimension mismatch: expected {expected}, received {received}",
            status_code=500
        )


class EmbeddingRateLimitError(EmbeddingServiceError):
    """Raised when the external embedding API rate limit or quota is exhausted."""
    def __init__(self, message: str = "Embedding API rate limit or quota exceeded."):
        super().__init__(message, status_code=429)


# ===========================================================================
# 2. Base Provider Abstraction
# ===========================================================================
class BaseEmbeddingProvider(ABC):
    """Abstract interface defining the contract for embedding providers."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the canonical model identifier."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns the vector dimensionality."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generates a dense vector embedding for a single text string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates dense vector embeddings for a batch of text strings."""
        pass


# ===========================================================================
# 3. Google GenAI Provider (text-embedding-004)
# ===========================================================================
class GoogleGenAIEmbeddingProvider(BaseEmbeddingProvider):
    """
    Production embedding provider utilizing the Google GenAI SDK and text-embedding-004.
    
    Why text-embedding-004:
    - Native to the Google Gemini ecosystem used across VIDYORA AI.
    - 768-dimensional dense vectors with state-of-the-art MTEB retrieval performance.
    - Highly cost-effective and low-latency for educational video transcripts.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        expected_dimension: Optional[int] = None,
    ):
        self._api_key = api_key if api_key is not None else settings.gemini_api_key
        self._model_name = model_name or settings.embedding_model
        self._dimension = expected_dimension or settings.embedding_dimension
        self._client = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def _get_client(self):
        if not self._api_key:
            raise EmbeddingConfigurationError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in the environment."
            )
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except Exception as exc:
                raise EmbeddingConfigurationError(
                    f"Failed to initialize Google GenAI client: {str(exc)}"
                )
        return self._client

    def _validate_vector(self, vector: List[float]) -> List[float]:
        """Validates that vector is non-empty, contains floats, and matches expected dimension."""
        if not vector or not isinstance(vector, list):
            raise EmbeddingServiceError("Embedding provider returned empty or invalid vector payload.")
        if len(vector) != self._dimension:
            raise EmbeddingDimensionMismatchError(expected=self._dimension, received=len(vector))
        return vector

    def embed_text(self, text: str) -> List[float]:
        """Embeds a single piece of text."""
        cleaned_text = (text or "").strip()
        if not cleaned_text:
            raise EmbeddingServiceError("Cannot generate embedding for empty or whitespace-only text.")

        batch_result = self.embed_batch([cleaned_text])
        return batch_result[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a batch of texts using client.models.embed_content.
        Supports up to 100 texts per batch (Google GenAI max batch).
        """
        if not texts:
            return []

        cleaned_texts = [(t or "").strip() for t in texts]
        for idx, t in enumerate(cleaned_texts):
            if not t:
                raise EmbeddingServiceError(f"Text at index {idx} in batch is empty.")

        client = self._get_client()

        try:
            from google.genai import types
            embed_config = types.EmbedContentConfig(output_dimensionality=self._dimension)

            # Google GenAI embed_content accepts list of strings in contents
            response = client.models.embed_content(
                model=self._model_name,
                contents=cleaned_texts,
                config=embed_config,
            )

            if not response or not hasattr(response, "embeddings") or not response.embeddings:
                raise EmbeddingServiceError("Empty response returned from Google GenAI embed_content.")

            results: List[List[float]] = []
            for emb_obj in response.embeddings:
                vec = list(emb_obj.values)
                results.append(self._validate_vector(vec))

            if len(results) != len(cleaned_texts):
                raise EmbeddingServiceError(
                    f"Expected {len(cleaned_texts)} embeddings, received {len(results)} from API."
                )

            return results

        except Exception as exc:
            err_msg = str(exc)
            logger.error("Embedding API error: %s", err_msg)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
                raise EmbeddingRateLimitError(
                    "Gemini Embedding API quota or rate limit exceeded. Please retry in a few moments."
                )
            if "API_KEY_INVALID" in err_msg or "401" in err_msg:
                raise EmbeddingConfigurationError("Invalid Gemini API key provided for embeddings.")
            raise EmbeddingServiceError(f"Google GenAI embedding failed: {err_msg}")


# ===========================================================================
# 4. Mock Provider (Deterministic Testing / Offline Support)
# ===========================================================================
class MockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic pseudo-embedding provider for unit and regression testing.
    Produces unit-normalized 768-dimensional vectors derived from SHA-256 hash
    of the input text, ensuring identical texts yield cosine similarity = 1.0.
    """

    def __init__(self, dimension: Optional[int] = None, model_name: str = "mock-embedding-768"):
        self._dimension = dimension or settings.embedding_dimension
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def _hash_to_vector(self, text: str) -> List[float]:
        # Generate reproducible float values based on text hash
        raw_vals: List[float] = []
        salt = 0
        while len(raw_vals) < self._dimension:
            h = hashlib.sha256(f"{text}_{salt}".encode("utf-8")).digest()
            for b in h:
                # Map byte 0..255 to -1.0..1.0
                raw_vals.append((float(b) - 128.0) / 128.0)
                if len(raw_vals) == self._dimension:
                    break
            salt += 1

        # L2-normalize vector so cosine similarity is straightforward dot-product
        norm = math.sqrt(sum(x * x for x in raw_vals)) or 1.0
        return [round(x / norm, 6) for x in raw_vals]

    def embed_text(self, text: str) -> List[float]:
        cleaned = (text or "").strip()
        if not cleaned:
            raise EmbeddingServiceError("Cannot generate embedding for empty text.")
        return self._hash_to_vector(cleaned)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


# ===========================================================================
# 5. Embedding Service Orchestrator
# ===========================================================================
class EmbeddingService:
    """
    High-level singleton service orchestrating embedding generation.
    Delegates to the active BaseEmbeddingProvider.
    """

    def __init__(self, provider: Optional[BaseEmbeddingProvider] = None):
        if provider is not None:
            self._provider = provider
        elif settings.is_gemini_configured:
            self._provider = GoogleGenAIEmbeddingProvider()
        else:
            self._provider = MockEmbeddingProvider()

    @property
    def provider(self) -> BaseEmbeddingProvider:
        return self._provider

    def set_provider(self, provider: BaseEmbeddingProvider) -> None:
        """Dynamically switches the active embedding provider (useful for tests)."""
        self._provider = provider

    def get_model_name(self) -> str:
        return self._provider.model_name

    def get_dimension(self) -> int:
        return self._provider.dimension

    def generate_embedding(self, text: str) -> List[float]:
        """Generates a single validated vector embedding."""
        return self._provider.embed_text(text)

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates batch vector embeddings."""
        return self._provider.embed_batch(texts)


# Shared global instance
embedding_service = EmbeddingService()

"""Text and image embeddings through an OpenAI-compatible gateway.

CBORG and AMSC i2 are LiteLLM proxies that serve embedding models next to their
chat models, on the standard ``POST <base>/embeddings`` route (``base`` is the
``…/v1`` URL the provider catalog names). :class:`GatewayEmbeddingMixin` gives a
gateway adapter the three embedding methods of :class:`~.base.BaseProvider`.

Text is sent in one batched request. An image is sent as a ``data:`` URL string
in ``input``, the form a LiteLLM proxy hands to its multimodal embedding
backends (Bedrock Titan image, Cohere v4, Nova multimodal, Vertex); images and
texts of an image-embedding call go one request per input, so a backend that
refuses a mixed batch never sees one.

Every returned vector is checked, and truncated to ``dimensions`` and
L2-renormalised when given, client-side: the gateways front models whose
native ``dimensions`` parameter differs or is absent, so it is never forwarded.
"""

from __future__ import annotations

import base64
import time

from .base import BaseProvider, ImageInput, TextInput, fit_vector
from .health import HealthResult, failure_reason

_EMBEDDINGS_PATH = "/embeddings"


def _wire_input(item: ImageInput | TextInput) -> str:
    """The ``input`` string that carries *item*: the text, or the image as a data URL."""
    if isinstance(item, str):
        return item
    data, mime = item
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


class GatewayEmbeddingMixin(BaseProvider):
    """Embedding endpoints for an OpenAI-compatible gateway adapter.

    Listed ahead of the adapter's chat base (``class X(GatewayEmbeddingMixin,
    LiteLLMDelegatingProvider)``); the adapter sets the embedding model defaults.
    """

    # Declared behaviour (see BaseProvider)
    truncates_to_dimensions = True

    def _post_embeddings(
        self,
        inputs: list[str],
        model_id: str | None,
        api_key: str | None,
        base_url: str | None,
        timeout: float,
    ) -> list[list[float]]:
        """One ``POST <base>/embeddings``; the vectors, in input order.

        Raises:
            ValueError: When no API key, model id or base URL is given, or the response
                carries no vector for some input.
            requests.RequestException: When the request fails or times out.
        """
        import requests

        if not api_key:
            raise ValueError(f"{self.name} API key is required")
        if not model_id:
            raise ValueError(f"{self.name} embedding model id is required")
        base = self.require_effective_base_url(base_url)
        response = requests.post(
            base.rstrip("/") + _EMBEDDINGS_PATH,
            json={"model": model_id, "input": inputs},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        response.raise_for_status()
        try:
            data = sorted(response.json()["data"], key=lambda item: item.get("index", 0))
            vectors = [item["embedding"] for item in data]
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            raise ValueError(f"{self.name} returned no embedding in its response: {e}") from e
        if len(vectors) != len(inputs):
            raise ValueError(
                f"{self.name} returned {len(vectors)} embeddings for {len(inputs)} inputs"
            )
        return vectors

    def execute_embedding(
        self,
        texts: list[str],
        model_id: str | None,
        api_key: str | None = None,
        base_url: str | None = None,
        dimensions: int | None = None,
        timeout: float = 600.0,
    ) -> list[list[float]]:
        """Embed *texts* in one request, one vector per text, in input order.

        Args:
            texts: Texts to embed.
            model_id: Embedding model id (``default_embedding_model_id`` when None).
            api_key: Gateway API key.
            base_url: The gateway's ``…/v1`` URL.
            dimensions: Truncate each vector to this length and L2-renormalise.
            timeout: Request timeout in seconds.

        Returns:
            One vector per text.

        Raises:
            ValueError: When the key or base URL is missing, or the response is malformed.
            EmbeddingDimensionError: When *dimensions* exceeds a returned vector.
            DegenerateVectorError: When a vector has zero norm or a non-finite value.
            requests.RequestException: When the request fails or times out.
        """
        if not texts:
            return []
        model = model_id or self.default_embedding_model_id
        vectors = self._post_embeddings(list(texts), model, api_key, base_url, timeout)
        return [fit_vector(vector, dimensions) for vector in vectors]

    def execute_image_embedding(
        self,
        inputs: list[ImageInput | TextInput],
        model_id: str,
        api_key: str | None = None,
        base_url: str | None = None,
        dimensions: int | None = None,
        timeout: float = 600.0,
    ) -> list[list[float]]:
        """Embed images and texts into one vector space, one request per input.

        The model must be a multimodal embedding model that embeds both images
        and texts (e.g. ``cohere-embed-v4``); each request is bounded by its
        share of the time left of *timeout*.

        Args:
            inputs: Each an ``(bytes, mime)`` image or a text.
            model_id: Multimodal embedding model id.
            api_key: Gateway API key.
            base_url: The gateway's ``…/v1`` URL.
            dimensions: Truncate each vector to this length and L2-renormalise.
            timeout: Seconds for the whole call, shared across the requests.

        Returns:
            One vector per input, in input order.

        Raises:
            ValueError: When the key or base URL is missing, or a response is malformed.
            EmbeddingDimensionError: When *dimensions* exceeds a returned vector.
            DegenerateVectorError: When a vector has zero norm or a non-finite value.
            requests.RequestException: When a request fails or times out.
        """
        import requests

        items = list(inputs)
        deadline = time.monotonic() + timeout
        vectors: list[list[float]] = []
        for index, item in enumerate(items):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise requests.Timeout(
                    f"{self.name} image embedding timed out after {timeout}s "
                    f"({index} of {len(items)} inputs embedded)"
                )
            (vector,) = self._post_embeddings(
                [_wire_input(item)],
                model_id,
                api_key,
                base_url,
                remaining / (len(items) - index),
            )
            vectors.append(fit_vector(vector, dimensions))
        return vectors

    def check_embedding_health(
        self,
        api_key: str | None,
        base_url: str | None,
        model_id: str | None = None,
        timeout: float = 10.0,
    ) -> HealthResult:
        """Embed one one-token text against the configured model.

        Never raises for a provider failure: a missing key or URL answers
        ``config``, an HTTP or connection failure is classified by
        :func:`~osprey.models.providers.health.failure_reason`, and anything it
        does not know is reported ``unreachable``.
        """
        name = self.name
        if not api_key:
            return HealthResult(False, f"{name} API key is required", "config")
        try:
            self.resolve_base_url(base_url)
        except ValueError as e:
            return HealthResult(False, str(e), "config")

        model = model_id or self.health_check_embedding_model_id
        try:
            self._post_embeddings(["ping"], model, api_key, base_url, timeout)
        except Exception as e:
            return HealthResult(
                False,
                f"{name} embedding health check failed: {type(e).__name__}: {e}",
                failure_reason(e) or "unreachable",
            )
        return HealthResult(True, f"{name} embedding API healthy (model: {model})", None)

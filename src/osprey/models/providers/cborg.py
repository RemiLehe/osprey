"""CBORG Provider Adapter Implementation.

This provider uses LiteLLM as the backend for unified API access.
CBORG is LBNL's OpenAI-compatible proxy service.
"""

import base64

from .base import ImageInput, TextInput, fit_vector
from .health import HealthResult, failure_reason
from .litellm_adapter import check_litellm_health, execute_litellm_completion
from .litellm_delegating import LiteLLMDelegatingProvider

__all__ = ["CBorgProviderAdapter", "check_litellm_health", "execute_litellm_completion"]


class CBorgProviderAdapter(LiteLLMDelegatingProvider):
    """CBORG (LBNL) provider implementation using LiteLLM."""

    # Metadata (single source of truth)
    name = "cborg"
    description = "LBNL CBorg proxy (supports multiple models)"
    requires_api_key = True
    requires_base_url = True
    requires_model_id = True
    supports_proxy = True
    default_base_url = None
    models_probe = "bearer"
    default_model_id = "anthropic/claude-haiku"  # Claude Haiku via CBORG for general use
    health_check_model_id = "anthropic/claude-haiku"  # Fast and cost-effective for health checks

    # Embedding defaults: LBL-hosted Nomic text model (free). For image
    # embeddings name a multimodal model such as cohere-embed-v4.
    default_embedding_model_id = "lbl/nomic-embed-text"
    health_check_embedding_model_id = "lbl/nomic-embed-text"

    # API key acquisition information
    api_key_url = "https://cborg.lbl.gov"
    api_key_instructions = [
        "As a Berkeley Lab employee, go to 'API' -> 'Request API Key'",
        "Create an API key ($50/month per user allocation)",
        "Copy the key provided",
    ]
    api_key_note = "Must have affiliation with Berkeley Lab to request an API key."

    # Provider facts (see BaseProvider)
    api_key_env_var = "CBORG_API_KEY"
    api_protocol = "anthropic"
    supports_interactive_login = False
    # The gateway's OpenAI route translates image parts for the models it fronts.
    supports_images = True
    supports_thinking = False
    self_hosted = False

    # LiteLLM integration - CBORG is an OpenAI-compatible proxy
    is_openai_compatible = True
    gateway = "litellm"  # a LiteLLM proxy — requests carry the acting identity
    supports_native_structured_output = True  # proxies to models with native json_schema support

    truncates_to_dimensions = True  # embeddings are truncated client-side

    # execute_completion / check_health inherited from LiteLLMDelegatingProvider.

    def execute_embedding(
        self,
        texts: list[str],
        model_id: str | None,
        api_key: str | None = None,
        base_url: str | None = None,
        dimensions: int | None = None,
        timeout: float = 600.0,
    ) -> list[list[float]]:
        """Embed *texts* through the gateway's OpenAI-compatible ``/embeddings`` route.

        *dimensions* is applied client-side (truncate and L2-renormalise).
        """
        import requests

        if not texts:
            return []
        response = requests.post(
            self.require_effective_base_url(base_url).rstrip("/") + "/embeddings",
            json={"model": model_id or self.default_embedding_model_id, "input": texts},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        response.raise_for_status()
        return [fit_vector(d["embedding"], dimensions) for d in response.json()["data"]]

    def execute_image_embedding(
        self,
        inputs: list[ImageInput | TextInput],
        model_id: str,
        api_key: str | None = None,
        base_url: str | None = None,
        dimensions: int | None = None,
        timeout: float = 600.0,
    ) -> list[list[float]]:
        """Embed images (sent as ``data:`` URLs) and texts, one request per input."""
        return [
            self.execute_embedding(
                [
                    item
                    if isinstance(item, str)
                    else f"data:{item[1]};base64,{base64.b64encode(item[0]).decode()}"
                ],
                model_id,
                api_key,
                base_url,
                dimensions,
                timeout,
            )[0]
            for item in inputs
        ]

    def check_embedding_health(
        self,
        api_key: str | None,
        base_url: str | None,
        model_id: str | None = None,
        timeout: float = 10.0,
    ) -> HealthResult:
        """Embed one short text with the configured model; never raises."""
        model = model_id or self.health_check_embedding_model_id
        try:
            self.execute_embedding(["ping"], model, api_key, base_url, timeout=timeout)
        except Exception as e:
            reason = failure_reason(e) or ("config" if isinstance(e, ValueError) else "unreachable")
            return HealthResult(False, f"{self.name} embedding health check failed: {e}", reason)
        return HealthResult(True, f"{self.name} embedding API healthy (model: {model})", None)

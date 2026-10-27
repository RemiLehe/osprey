"""American Science Cloud Intelligent Interfaces (AMSC i2) Provider Adapter Implementation.

This provider uses LiteLLM as the backend for unified API access.
AMSC i2 is an OpenAI-compatible proxy service for scientific computing.
"""

import base64

from .base import ImageInput, TextInput, fit_vector
from .health import HealthResult, failure_reason
from .litellm_adapter import check_litellm_health, execute_litellm_completion
from .litellm_delegating import LiteLLMDelegatingProvider

__all__ = ["AMSCI2ProviderAdapter", "check_litellm_health", "execute_litellm_completion"]


class AMSCI2ProviderAdapter(LiteLLMDelegatingProvider):
    """American Science Cloud Intelligent Interfaces (AMSC i2) provider implementation using LiteLLM."""

    # Metadata (single source of truth)
    name = "amsc-i2"
    description = "American Science Cloud proxy (supports multiple models)"
    requires_api_key = True
    requires_base_url = True
    requires_model_id = True
    supports_proxy = True
    default_base_url = None
    default_model_id = "claude-haiku"  # Claude Haiku via AMSC i2 for general use
    health_check_model_id = "claude-haiku"  # Fast and cost-effective for health checks

    # Embedding defaults. For image embeddings name a multimodal model such as
    # cohere-embed-v4, titan-embed-image-v1 or nova-2-embed-multimodal.
    default_embedding_model_id = "titan-embed-text-v2"
    health_check_embedding_model_id = "titan-embed-text-v2"

    # API key acquisition information
    api_key_url = "https://api.i2-core.american-science-cloud.org/"
    api_key_instructions = [
        "If you have an americansciencecloud.org Google account, log in and go to 'API Key Manager.",
        "Otherwise, request access at https://docs.google.com/forms/d/1xcuOTxzvwu6sEmQfNu5zxLsjaS_hMvAfr99XQzdc_nY/viewform",
    ]
    api_key_note = (
        "Requires an americansciencecloud.org Google account or lab ID via GlobusAuth whitelist."
    )

    # Provider facts (see BaseProvider)
    api_key_env_var = "AMSC_I2_API_KEY"
    api_protocol = "openai"
    supports_interactive_login = False
    # The OpenAI route documents no image input, so none is assumed.
    supports_images = False
    supports_thinking = False
    self_hosted = False

    # LiteLLM integration - AMSC i2 is an OpenAI-compatible proxy
    is_openai_compatible = True
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

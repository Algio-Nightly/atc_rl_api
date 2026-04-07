"""LLM Client wrapper for HuggingFace Inference API (Nemotron)."""

import os
import time
from typing import Optional

import httpx
from openai import OpenAI
from openai._exceptions import APIConnectionError, RateLimitError


class LLMClient:
    """OpenAI client wrapper for HuggingFace Inference API.

    Supports HF Inference API format with token-based authentication.
    Implements retry logic with exponential backoff for resilience.

    Environment variables:
        HF_TOKEN: HuggingFace token for API authentication (optional)
        API_BASE_URL: Base URL for the API (default: HF router)
        MODEL_NAME: Model identifier (default: meta-llama/Llama-3.3-70B-Instruct)
    """

    DEFAULT_TIMEOUT_SECONDS = 60.0
    DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"
    DEFAULT_API_BASE = "https://router.huggingface.co/v1"

    RETRY_DELAYS = (1.0, 2.0, 4.0)  # Exponential backoff base
    RATE_LIMIT_MULTIPLIER = 2.0  # Extra wait on rate limit

    def __init__(
        self,
        api_base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        hf_token: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        """Initialize LLM client.

        Args:
            api_base_url: Base URL for API. Defaults to API_BASE_URL env var or HF router.
            model_name: Model name/id. Defaults to MODEL_NAME env var or default model.
            hf_token: HuggingFace token. Defaults to HF_TOKEN env var. Optional for testing.
            timeout: Request timeout in seconds. Default 60s.
        """
        self.api_base_url = api_base_url or os.environ.get(
            "API_BASE_URL", self.DEFAULT_API_BASE
        )
        self.model_name = model_name or os.environ.get("MODEL_NAME", self.DEFAULT_MODEL)
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")
        self.timeout = timeout

        # Initialize OpenAI client with httpx transport
        self._client = OpenAI(
            base_url=self.api_base_url,
            api_key=self.hf_token,
            http_client=httpx.Client(timeout=httpx.Timeout(timeout)),
        )

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Send prompt to LLM and return text response.

        Args:
            prompt: User prompt to send to the model.
            system_prompt: Optional system prompt for instruction/context.

        Returns:
            Generated text response from the model.

        Raises:
            APIConnectionError: If connection fails after retries.
            RateLimitError: If rate limited after retries.
            Exception: For other API errors.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )

        return response.choices[0].message.content or ""

    def generate_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        """Send prompt to LLM with automatic retry on failure.

        Implements exponential backoff: 1s, 2s, 4s between retries.
        RateLimitError gets longer wait (2x multiplier).

        Args:
            prompt: User prompt to send to the model.
            system_prompt: Optional system prompt for instruction/context.
            max_retries: Maximum number of retry attempts (default: 3).

        Returns:
            Generated text response from the model.

        Raises:
            APIConnectionError: If connection fails after all retries exhausted.
            RateLimitError: If rate limited after all retries exhausted.
            Exception: For other API errors that don't retry.
        """
        delays = self.RETRY_DELAYS[:max_retries]

        for attempt, delay in enumerate(delays):
            try:
                return self.generate(prompt, system_prompt)
            except RateLimitError as e:
                # Rate limit gets extra wait time
                wait_time = delay * self.RATE_LIMIT_MULTIPLIER
                if attempt < len(delays) - 1:
                    time.sleep(wait_time)
                else:
                    raise  # Re-raise on last attempt
            except APIConnectionError as e:
                if attempt < len(delays) - 1:
                    time.sleep(delay)
                else:
                    raise  # Re-raise on last attempt
            except Exception:
                # Don't retry other errors - fail fast
                raise

        # Fallback (shouldn't reach here)
        return self.generate(prompt, system_prompt)

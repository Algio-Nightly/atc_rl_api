"""Pytest configuration and fixtures for ATC RL environment tests."""

import os
import pytest
from typing import Optional


# Environment variable names
HF_TOKEN_ENV = "HF_TOKEN"
API_BASE_URL_ENV = "API_BASE_URL"
MODEL_NAME_ENV = "MODEL_NAME"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "llm: marks tests that require LLM API access")
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (fast, no external dependencies)"
    )


@pytest.fixture(scope="session")
def hf_token() -> Optional[str]:
    """Get HuggingFace token from environment.

    Returns:
        HF_TOKEN value or None if not set (for local development without API).
    """
    token = os.environ.get(HF_TOKEN_ENV)
    if not token:
        pytest.skip(
            f"{HF_TOKEN_ENV} not set - skipping LLM-dependent tests",
            allow_module_level=True,
        )
    return token


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """Get API base URL from environment.

    Returns:
        API_BASE_URL value or default if not set.
    """
    return os.environ.get(API_BASE_URL_ENV, "https://router.huggingface.co/v1")


@pytest.fixture(scope="session")
def model_name() -> str:
    """Get model name from environment.

    Returns:
        MODEL_NAME value or default if not set.
    """
    return os.environ.get(MODEL_NAME_ENV, "meta-llama/Llama-3.3-70B-Instruct")


@pytest.fixture(scope="session")
def llm_client(hf_token: str, api_base_url: str, model_name: str):
    """Create an LLM client for testing.

    This fixture is skipped if HF_TOKEN is not set, allowing local development
    without API access.

    Args:
        hf_token: HuggingFace token from fixture.
        api_base_url: API base URL from fixture.
        model_name: Model name from fixture.

    Returns:
        A client object for making LLM API calls, or None if skipped.
    """
    try:
        from openai import OpenAI
    except ImportError:
        pytest.skip("openai package not installed", allow_module_level=True)

    client = OpenAI(
        base_url=api_base_url,
        api_key=hf_token,
    )
    return client


@pytest.fixture
def sample_callsigns():
    """Provide sample aircraft callsigns for testing."""
    return ["AAL123", "UAL456", "DAL789", "NWA321", "AWE109"]


@pytest.fixture
def sample_commands():
    """Provide sample ATC commands for testing."""
    return {
        "vector": "ATC VECTOR AAL123 270",
        "altitude": "ATC ALTITUDE AAL123 3000",
        "speed": "ATC SPEED AAL123 250",
        "direct": "ATC DIRECT AAL123 POM",
        "hold": "ATC HOLD AAL123 POM 5000",
        "approach": "ATC APPROACH AAL123",
        "land": "ATC LAND AAL123 27L",
        "resume": "ATC RESUME AAL123",
    }

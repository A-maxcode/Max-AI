import pytest
from pydantic import ValidationError

from app.config import Settings


def test_model_server_url_must_be_local_or_private():
    with pytest.raises(ValidationError):
        Settings(model_server_url="https://api.example.com")
    with pytest.raises(ValidationError):
        Settings(model_server_url="http://127.0.0.1:8080/v1")
    assert Settings(model_server_url="http://127.0.0.1:8080").model_server_url == (
        "http://127.0.0.1:8080"
    )
    assert Settings(model_server_url="http://model-server:8080").model_server_url == (
        "http://model-server:8080"
    )


def test_cors_and_model_generation_configuration_is_validated():
    with pytest.raises(ValidationError):
        Settings(frontend_origins="*")
    with pytest.raises(ValidationError):
        Settings(model_context_length=512, model_max_tokens=512)
    with pytest.raises(ValidationError):
        Settings(frontend_origins="https://example.com/path")

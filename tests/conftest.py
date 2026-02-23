"""Shared fixtures for agent tests."""

import pytest

from core.config import AgentConfig, AppConfig, EmbeddingsConfig, ProjectConfig, QDBConfig


@pytest.fixture
def agent_config() -> AgentConfig:
    """Fixture for agent configuration."""
    return AgentConfig(
        model_name="test-model",
        base_url="http://test-url",
        temperature=0.0,
        top_p=0.95,
        max_output_tokens=100,
    )


@pytest.fixture
def app_config(agent_config: AgentConfig) -> AppConfig:  # pylint: disable=redefined-outer-name
    """Fixture for app configuration."""
    return AppConfig(
        project=ProjectConfig(
            id="test-project", location="test-loc", country_name="US", num_queries=2
        ),
        qdrant=QDBConfig(),
        embeddings=EmbeddingsConfig(
            articles_table="test_project.test_dataset.test_articles_table",
            features_table="test_project.test_dataset.test_features_table",
        ),
        agents={
            "query_moderator": agent_config,
            "query_expander": agent_config,
            "query_router": agent_config,
        },
    )

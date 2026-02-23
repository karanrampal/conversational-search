"""Unit tests for config file manager module."""

import os
from unittest.mock import MagicMock, mock_open, patch

import pytest
from pydantic import SecretStr

from core.config import (
    AgentConfig,
    AppConfig,
    EmbeddingsConfig,
    ProjectConfig,
    QDBConfig,
    load_config,
)


class TestProjectConfig:
    """Unit tests for ProjectConfig."""

    def test_defaults(self) -> None:
        """Test default values are set correctly for ProjectConfig."""
        config = ProjectConfig(id="test-project", location="us-central1")
        assert config.id == "test-project"
        assert config.location == "us-central1"
        assert config.country_name == "United Kingdom"
        assert config.num_queries == 6

    def test_custom_values(self) -> None:
        """Test custom values are set correctly for ProjectConfig."""
        config = ProjectConfig(
            id="test-project", location="us-central1", country_name="France", num_queries=10
        )
        assert config.country_name == "France"
        assert config.num_queries == 10


class TestAgentConfig:  # pylint: disable=too-few-public-methods
    """Unit tests for AgentConfig."""

    def test_defaults(self) -> None:
        """Test default values are set correctly for AgentConfig."""
        config = AgentConfig(model_name="gemini-pro")
        assert config.model_name == "gemini-pro"
        assert config.base_url is None
        assert config.temperature == 0.0
        assert config.top_p == 0.95
        assert config.thinking_budget == 0
        assert config.max_output_tokens == 250


class TestQDBConfig:
    """Unit tests for QDBConfig."""

    def test_defaults(self) -> None:
        """Test default values are set correctly for QDBConfig."""
        config = QDBConfig()
        assert config.host == os.getenv("QDRANT_HOST", "localhost")
        assert config.port == int(os.getenv("QDRANT_PORT", "6333"))
        assert config.collection_name == "articles_collection"
        assert config.replication_factor == 1
        assert config.https is False
        assert config.verify is None

    def test_custom_init(self) -> None:
        """Test custom initialization for QDBConfig."""
        config = QDBConfig(
            host="custom-host", port=1234, api_key=SecretStr("my-key"), collection_name="my-coll"
        )
        assert config.host == "custom-host"
        assert config.port == 1234
        assert config.api_key.get_secret_value() == "my-key"  # pylint: disable=no-member
        assert config.collection_name == "my-coll"
        assert config.replication_factor == 1
        assert config.https is False
        assert config.verify is None


class TestEmbeddingsConfig:
    """Unit tests for EmbeddingsConfig."""

    def test_defaults(self) -> None:
        """Test default values are set correctly for EmbeddingsConfig."""
        config = EmbeddingsConfig(
            articles_table="project.dataset.articles", features_table="project.dataset.features"
        )
        assert config.articles_table == "project.dataset.articles"
        assert config.features_table == "project.dataset.features"
        assert config.feature_vector_size == 1408

    def test_custom_vector_size(self) -> None:
        """Test custom vector size is set correctly for EmbeddingsConfig."""
        config = EmbeddingsConfig(
            articles_table="project.dataset.articles",
            features_table="project.dataset.features",
            feature_vector_size=1024,
        )
        assert config.feature_vector_size == 1024


class TestLoadConfig:
    """Unit tests for load_config function."""

    @patch("core.config.Path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="""
project:
  id: test-proj
  location: us-west1
qdrant:
  host: qdrant-host
embeddings:
  articles_table: "project.dataset.articles"
  features_table: "project.dataset.features"
agents:
  default:
    model_name: test-model
""",
    )
    def test_load_config_success(  # pylint: disable=unused-argument
        self, mocking_open: MagicMock, mock_exists: MagicMock
    ) -> None:
        """Test successful loading of configuration."""
        mock_exists.return_value = True

        config = load_config("config.yaml")

        assert isinstance(config, AppConfig)
        assert config.project.id == "test-proj"
        assert config.qdrant.host == "qdrant-host"
        assert config.agents["default"].model_name == "test-model"
        assert config.embeddings.articles_table == "project.dataset.articles"
        assert config.embeddings.features_table == "project.dataset.features"
        assert config.embeddings.feature_vector_size == 1408

    @patch("core.config.Path.exists")
    def test_load_config_file_not_found(self, mock_exists: MagicMock) -> None:
        """Test loading configuration when file is not found."""
        mock_exists.side_effect = [False, False]

        with pytest.raises(FileNotFoundError):
            load_config("missing.yaml")

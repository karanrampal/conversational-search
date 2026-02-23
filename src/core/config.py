"""Module for loading configuration files."""

import logging
import os
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, Field, SecretStr, model_validator

logger = logging.getLogger(__name__)


class ProjectConfig(BaseModel):
    """Configuration for the project.

    Args:
        id (str): GCP Project ID.
        location (str): GCP Project location.
        country_name (str): Default country name for queries.
        num_queries (int): Default number of queries to generate.
    """

    id: str
    location: str
    country_name: str = "United Kingdom"
    num_queries: int = 6


class AgentConfig(BaseModel):
    """Configuration for an individual agent.

    Args:
        model_name (str): Name of the LLM model to use.
        base_url (Optional[str]): Base URL for the model API.
        temperature (float): Sampling temperature for the model.
        top_p (float): Nucleus sampling parameter.
        thinking_budget (int): Number of tokens allocated for agent's internal thoughts.
        max_output_tokens (int): Maximum number of tokens to generate in the output.
    """

    model_name: str
    base_url: str | None = None
    temperature: float = 0.0
    top_p: float = 0.95
    thinking_budget: int = 0
    max_output_tokens: int = 250


class QDBConfig(BaseModel):
    """Configuration for Qdrant Database Connection.

    Args:
        host (str): Database host address.
        port (int): Database port number.
        api_key (SecretStr): API key for database authentication.
        collection_name (str): Name of the collection to use.
        replication_factor (int): Number of replicas for dataset.
        https (bool): Whether to use HTTPS for connection.
        verify (str | bool | None): Verify SSL certificates. Can be a path to a cert file, a
            boolean, or None.
    """

    host: str = Field(default_factory=lambda: os.getenv("QDRANT_HOST", "localhost"))
    port: int = Field(default_factory=lambda: int(os.getenv("QDRANT_PORT", "6333")))
    api_key: SecretStr = Field(default_factory=lambda: SecretStr(os.getenv("QDRANT_API_KEY", "")))
    collection_name: str = "articles_collection"
    replication_factor: int = Field(default=1, description="Number of replicas of dataset.")
    https: bool = Field(
        default_factory=lambda: os.getenv("QDRANT_HTTPS", "False").lower() == "true",
        description="Whether to use HTTPS for connection.",
    )
    # None means verify=True in httpx
    verify: str | bool | None = Field(
        default=None, description="Verify SSL certificates or provide path to cert file."
    )

    @model_validator(mode="after")
    def override_verify_from_env(self) -> Self:
        """Override verify setting from environment variable if present."""
        verify_env = os.getenv("QDRANT_VERIFY")
        if verify_env is not None:
            if verify_env.lower() == "true":
                self.verify = True
            elif verify_env.lower() == "false":
                self.verify = False
            else:
                self.verify = verify_env
        return self


class EmbeddingsConfig(BaseModel):
    """Configuration for embeddings.

    Args:
        articles_table (str): Fully qualified name of the articles table.
        features_table (str): Fully qualified name of the features table.
        feature_vector_size (int): Size of the feature vectors. Default is 1408.
    """

    articles_table: str
    features_table: str
    feature_vector_size: int = 1408


class AppConfig(BaseModel):
    """Configuration for the entire application.

    Args:
        project (ProjectConfig): Project configuration.
        qdrant (QDBConfig): Database configuration.
        agents (dict[str, AgentConfig]): Dictionary of agent configurations.
        embeddings (EmbeddingsConfig): Embeddings configuration.
    """

    project: ProjectConfig
    qdrant: QDBConfig
    agents: dict[str, AgentConfig]
    embeddings: EmbeddingsConfig


def load_config(config_path: str = "configs/config.yaml") -> AppConfig:
    """Loads configuration from a YAML file and validates it.
    Args:
        config_path (str): Path to the YAML configuration file.
    Returns:
        AppConfig: Configuration object.
    Raises:
        FileNotFoundError: If the configuration file does not exist.
    """
    path = Path(config_path)
    if not path.exists():
        # This handles running from src/ vs root
        root_path = Path(__file__).parent.parent.parent / config_path
        if root_path.exists():
            path = root_path
        else:
            raise FileNotFoundError(f"Config file not found at {config_path}")

    with open(path) as f:  # pylint: disable=unspecified-encoding
        raw_config = yaml.safe_load(f)
        logger.info("Loaded configuration from %s", path)
        return AppConfig(**raw_config)

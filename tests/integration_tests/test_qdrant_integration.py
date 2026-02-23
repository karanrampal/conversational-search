"""Integration tests for Qdrant."""

import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any, Literal

import pytest
import pytest_asyncio
from qdrant_client.models import PointStruct

from database.qdrant_manager import QdrantManager


class TestQdrantIntegration:
    """Integration tests for QdrantManager."""

    @pytest.fixture
    def qdrant_config(self) -> dict[str, Any]:
        """Get Qdrant configuration from environment variables."""
        return {
            "host": os.getenv("QDRANT_HOST", "localhost"),
            "port": int(os.getenv("QDRANT_PORT", "6333")),
            "api_key": os.getenv("QDRANT_API_KEY", ""),
        }

    @pytest.fixture
    def qdrant_manager(self, qdrant_config: dict[str, Any]) -> QdrantManager:
        """Initialize QdrantManager."""
        return QdrantManager(
            host=qdrant_config["host"],
            port=qdrant_config["port"],
            api_key=qdrant_config["api_key"],
        )

    @pytest_asyncio.fixture
    async def test_collection_name(
        self, qdrant_manager: QdrantManager
    ) -> AsyncGenerator[str, None]:
        """Generate a temporary collection name and ensure cleanup."""
        collection_name = f"test_collection_{uuid.uuid4().hex}"

        yield collection_name

        await qdrant_manager.delete_collection(collection_name)

    @pytest.mark.asyncio
    async def test_qdrant_lifecycle(
        self, qdrant_manager: QdrantManager, test_collection_name: str
    ) -> None:
        """Integration test for QdrantManager"""

        exists = await qdrant_manager.collection_exists(test_collection_name)
        assert not exists, "Collection should not exist yet"

        vector_size = 4
        vector_name = "image_vector"
        vector_configs: dict[str, tuple[int, Literal["Cosine", "Euclid", "Dot", "Manhattan"]]] = {
            vector_name: (vector_size, "Dot")
        }

        await qdrant_manager.create_collection(
            collection_name=test_collection_name,
            vector_configs=vector_configs,
            use_quantization=False,
        )

        exists_after_create = await qdrant_manager.collection_exists(test_collection_name)
        assert exists_after_create, "Collection should exist after creation"

        entities = [
            {"id": 1, "vector": [0.1, 0.1, 0.1, 0.1], "city": "London"},
            {"id": 2, "vector": [0.9, 0.9, 0.9, 0.9], "city": "Berlin"},
        ]

        def mapper(entity: dict[str, Any]) -> PointStruct:
            return PointStruct(
                id=entity["id"],
                vector={vector_name: entity["vector"]},
                payload={"city": entity["city"]},
            )

        qdrant_manager.upload(
            collection_name=test_collection_name,
            entities=entities,
            mapper=mapper,
            wait_timeout=10,
        )

        count = await qdrant_manager.count_points(collection_name=test_collection_name)
        assert count == 2, f"Expected 2 points, got {count}"

        query_vector = [0.9, 0.9, 0.9, 0.9]

        results = await qdrant_manager.search_points(
            collection_name=test_collection_name,
            query=query_vector,
            vector_name=vector_name,
            limit=1,
        )

        assert len(results) > 0, "Should return search results"
        top_result = results[0]

        assert top_result.id == 2, f"Expected point 2, got {top_result.id}"
        assert top_result.payload and top_result.payload["city"] == "Berlin", "Payload should match"

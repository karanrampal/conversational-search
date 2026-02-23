"""Unit tests for the qdrant manager module."""

from collections.abc import Generator
from typing import Any, Literal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qdrant_client.models import (
    CollectionDescription,
    CollectionsResponse,
    CollectionStatus,
    Distance,
    PointStruct,
    ScalarQuantization,
    ScoredPoint,
)

from database.qdrant_manager import QdrantManager


class TestQdrantManager:
    """Test suite for the QdrantManager class."""

    @pytest.fixture
    def mock_async_client(self) -> Generator[AsyncMock, None, None]:
        """Fixture that mocks AsyncQdrantClient."""
        with patch("database.qdrant_manager.AsyncQdrantClient") as mock:
            client_instance = AsyncMock()
            mock.return_value = client_instance
            yield client_instance

    @pytest.fixture
    def mock_sync_client(self) -> Generator[MagicMock, None, None]:
        """Fixture that mocks QdrantClient."""
        with patch("database.qdrant_manager.QdrantClient") as mock:
            client_instance = MagicMock()
            mock.return_value = client_instance
            yield client_instance

    @pytest.fixture
    def qdrant_manager(self, mock_async_client: AsyncMock) -> QdrantManager:
        """Fixture that returns a QdrantManager instance."""
        assert mock_async_client
        manager = QdrantManager(host="localhost", port=6333, api_key="test_key")
        return manager

    @pytest.mark.asyncio
    async def test_collection_exists(
        self, qdrant_manager: QdrantManager, mock_async_client: AsyncMock
    ) -> None:
        """Test checking if a collection exists."""
        mock_async_client.collection_exists.return_value = True
        exists = await qdrant_manager.collection_exists("test_collection")
        assert exists is True
        mock_async_client.collection_exists.assert_called_once_with("test_collection")

    @pytest.mark.asyncio
    async def test_create_collection(
        self, qdrant_manager: QdrantManager, mock_async_client: AsyncMock
    ) -> None:
        """Test creating a new collection."""
        vector_configs: dict[str, tuple[int, Literal["Cosine", "Euclid", "Dot", "Manhattan"]]] = {
            "image": (1408, "Cosine")
        }
        await qdrant_manager.create_collection(
            collection_name="test_collection", vector_configs=vector_configs
        )

        mock_async_client.create_collection.assert_called_once()
        call_kwargs = mock_async_client.create_collection.call_args.kwargs
        assert call_kwargs["collection_name"] == "test_collection"
        assert "image" in call_kwargs["vectors_config"]
        assert call_kwargs["vectors_config"]["image"].size == 1408
        assert call_kwargs["vectors_config"]["image"].distance == Distance.COSINE
        assert isinstance(call_kwargs["quantization_config"], ScalarQuantization)

    @pytest.mark.asyncio
    async def test_list_collections(
        self, qdrant_manager: QdrantManager, mock_async_client: AsyncMock
    ) -> None:
        """Test listing collections."""
        mock_collections_response = CollectionsResponse(
            collections=[CollectionDescription(name="col1"), CollectionDescription(name="col2")]
        )
        mock_async_client.get_collections.return_value = mock_collections_response

        collections = await qdrant_manager.list_collections()
        assert collections == ["col1", "col2"]
        mock_async_client.get_collections.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_collection(
        self, qdrant_manager: QdrantManager, mock_async_client: AsyncMock
    ) -> None:
        """Test deleting a collection."""
        mock_async_client.delete_collection.return_value = True
        await qdrant_manager.delete_collection("test_collection")
        mock_async_client.delete_collection.assert_called_once_with("test_collection")

    @pytest.mark.asyncio
    async def test_search_points(
        self, qdrant_manager: QdrantManager, mock_async_client: AsyncMock
    ) -> None:
        """Test searching points in a collection."""
        mock_points = [
            ScoredPoint(id=1, version=1, score=0.9, payload={}, vector=None),
            ScoredPoint(id=2, version=1, score=0.8, payload={}, vector=None),
        ]
        mock_response = MagicMock()
        mock_response.points = mock_points
        mock_async_client.query_points.return_value = mock_response

        results = await qdrant_manager.search_points(
            collection_name="test_collection", query=[0.1, 0.2], vector_name="image"
        )

        assert results == mock_points
        mock_async_client.query_points.assert_called_once()
        kwargs = mock_async_client.query_points.call_args.kwargs
        assert kwargs["collection_name"] == "test_collection"
        assert kwargs["query"] == [0.1, 0.2]
        assert kwargs["using"] == "image"

    def test_upload_basic(self, qdrant_manager: QdrantManager, mock_sync_client: MagicMock) -> None:
        """Test basic upload functionality."""
        mock_collection_info = MagicMock()
        mock_vector_params = MagicMock()
        mock_vector_params.size = 2
        mock_collection_info.config.params.vectors = {"default": mock_vector_params}
        mock_collection_info.status = CollectionStatus.GREEN

        mock_sync_client.get_collection.return_value = mock_collection_info

        entities = [{"id": 1, "vec": [0.1, 0.2]}]

        def mapper(x: Any) -> PointStruct:
            return PointStruct(id=x["id"], vector={"default": x["vec"]}, payload={})

        qdrant_manager.upload(
            collection_name="test_collection",
            entities=entities,
            mapper=mapper,
            check_existing=False,
        )

        mock_sync_client.upload_points.assert_called_once()
        assert mock_sync_client.get_collection.call_count >= 1

    def test_validate_vector_compatibility_fail(self, qdrant_manager: QdrantManager) -> None:
        """Test failure cases for vector compatibility validation."""
        point = PointStruct(id=1, vector={"wrong_name": [0.1]}, payload={})

        mock_config = MagicMock()
        mock_config.config.name = "test"
        mock_vec_config = MagicMock()
        mock_vec_config.size = 1
        mock_config.config.params.vectors = {"correct_name": mock_vec_config}

        # Should not raise exception (warnings are logged)
        qdrant_manager._validate_vector_compatibility(  # pylint: disable=protected-access
            point, mock_config
        )

        point_dim_mismatch = PointStruct(id=1, vector={"correct_name": [0.1, 0.2]}, payload={})
        with pytest.raises(ValueError, match="Dimension mismatch"):
            qdrant_manager._validate_vector_compatibility(  # pylint: disable=protected-access
                point_dim_mismatch, mock_config
            )

    def test_wait_for_collection_index(
        self, qdrant_manager: QdrantManager, mock_sync_client: MagicMock
    ) -> None:
        """Test waiting for collection index to be ready."""
        mock_info = MagicMock()

        mock_info.status = CollectionStatus.GREEN
        mock_sync_client.get_collection.return_value = mock_info

        qdrant_manager.wait_for_collection_index("test_collection", sync_client=mock_sync_client)

        mock_sync_client.get_collection.assert_called_with("test_collection")

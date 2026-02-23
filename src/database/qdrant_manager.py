"""Module for managing Qdrant database connections and operations."""

import itertools
import json
import logging
import os
from collections.abc import Callable, Iterable
from time import perf_counter, sleep, time
from typing import Any, Literal

from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.models import (
    CollectionInfo,
    CollectionStatus,
    Distance,
    Filter,
    HnswConfigDiff,
    OptimizersConfigDiff,
    PointStruct,
    Record,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    ScoredPoint,
    VectorParams,
)

logger = logging.getLogger(__name__)


class QdrantManager:
    """Manager for Qdrant database operations.

    Args:
        host (str): The Qdrant host address
        port (int): The Qdrant port number
        api_key (str): The API key for authentication
        https (bool): Whether to use HTTPS for the connection (default: False)

    Kwargs:
        Additional keyword arguments to pass to the Qdrant client
        verify (str | bool | None): Verify SSL certificates. Can be a path to a cert file, a
            boolean, or None.
    """

    def __init__(
        self, host: str, port: int, api_key: str, https: bool = False, **kwargs: Any
    ) -> None:
        self.host = host
        self.port = port
        self.api_key = api_key
        self.https = https

        if https:
            ca_cert = os.getenv("QDRANT_CA_CERT")
            if ca_cert and "verify" not in kwargs:
                kwargs["verify"] = ca_cert

        self.kwargs = kwargs
        self.client = AsyncQdrantClient(
            host=host,
            port=port,
            api_key=api_key,
            https=https,
            **kwargs,
        )
        logger.info("Initialized QdrantManager for %s:%d", host, port)

    async def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists in the Qdrant database.

        Args:
            collection_name (str): The name of the collection to check

        Returns:
            bool: True if the collection exists, False otherwise
        """
        return await self.client.collection_exists(collection_name)

    async def create_collection(  # pylint: disable=too-many-arguments
        self,
        *,
        collection_name: str,
        vector_configs: dict[str, tuple[int, Literal["Cosine", "Euclid", "Dot", "Manhattan"]]],
        use_quantization: bool = True,
        hnsw_m: int = 16,
        replication_factor: int = 2,
        shard_number: int | None = None,
    ) -> None:
        """Create a new collection in the Qdrant database.

        Args:
            collection_name (str): The name of the collection to create
            vector_configs (dict[str, tuple[int, Literal["Cosine", "Euclid", "Dot", "Manhattan"]]]):
                Mapping of vector config name to their size and distance metric
            use_quantization (bool): Whether to use scalar quantization (default: True)
            hnsw_m (int): The HNSW M parameter (default: 16)
            replication_factor (int): Number of replicas for each shard (default: 2)
            shard_number (int | None): Number of shards. If None, Qdrant default (usually CPU count)
                is used.

        Example:
            qm = QdrantManager(host, port, api_key)
            vector_configs = {"image": (128, "Cosine"), "text": (768, "Euclid")}
            await qm.create_collection("my_collection", vector_configs, replication_factor=3)
        """
        # We don't need original vectors in RAM if quantization is used
        on_disk = use_quantization

        vec_configs = {
            vec_name: VectorParams(size=vector_size, distance=Distance(distance), on_disk=on_disk)
            for vec_name, (vector_size, distance) in vector_configs.items()
        }

        quantization_config = None
        if use_quantization:
            logger.info("Using scalar quantization for collection '%s'", collection_name)
            quantization_config = ScalarQuantization(
                scalar=ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                )
            )

        await self.client.create_collection(
            collection_name=collection_name,
            vectors_config=vec_configs,
            quantization_config=quantization_config,
            # Bigger size of segments are desired for faster search but indexing might be slower
            optimizers_config=OptimizersConfigDiff(max_segment_size=5_000_000),
            hnsw_config=HnswConfigDiff(
                # Lower m makes the graph sparser, reducing memory and speeding up insertion
                # However, search may be less accurate since fewer paths are available for traversal
                m=hnsw_m,
                on_disk=False,
            ),  # Keep the HNSW index graph in RAM
            replication_factor=replication_factor,
            shard_number=shard_number,
        )
        logger.info(
            "Created collection '%s' with vectors: %s, replication_factor: %d, shards: %s",
            collection_name,
            json.dumps(vector_configs, indent=2),
            replication_factor,
            shard_number,
        )

    async def get_collection_info(self, collection_name: str) -> CollectionInfo:
        """Get information about a specific collection.

        Args:
            collection_name (str): The name of the collection

        Returns:
            CollectionInfo: Collection information
        """
        return await self.client.get_collection(collection_name)

    async def list_collections(self) -> list[str]:
        """List all collections in the Qdrant database.

        Returns:
            list[str]: List of collection names
        """
        tmp = await self.client.get_collections()
        return [coll.name for coll in tmp.collections]

    async def delete_collection(self, collection_name: str) -> None:
        """Delete a collection from the Qdrant database.

        Args:
            collection_name (str): The name of the collection to delete
        """
        status = await self.client.delete_collection(collection_name)
        if status:
            logger.info("Deleted collection '%s'", collection_name)
        else:
            logger.warning("Collection '%s' could not be deleted", collection_name)

    def _prepare_upload(
        self,
        collection_name: str,
        entities: Iterable[Any],
        mapper: Callable[[Any], PointStruct],
        sync_client: QdrantClient,
    ) -> Iterable[Any]:
        """Prepares upload by validating the first entity against collection config."""
        logger.info("Starting upload to collection '%s'...", collection_name)
        try:
            iterator = iter(entities)
            try:
                first_entity = next(iterator)
            except StopIteration:
                logger.warning("No entities to upload to collection '%s'.", collection_name)
                return []

            first_point = mapper(first_entity)
            coll_info = sync_client.get_collection(collection_name)
            self._validate_vector_compatibility(first_point, coll_info)

            return itertools.chain([first_entity], iterator)

        except Exception as pre_check_err:
            logger.error(
                "Pre-upload validation failed for collection '%s': %s",
                collection_name,
                pre_check_err,
            )
            # Re-raise to stop upload
            raise pre_check_err

    def upload(  # pylint: disable=too-many-arguments
        self,
        *,
        collection_name: str,
        entities: Iterable[Any],
        mapper: Callable[[Any], PointStruct],
        batch_size: int = 64,
        parallel: int = 1,
        wait_timeout: int = 6000,
        check_existing: bool = True,
    ) -> None:
        """Upload points to a collection.

        Args:
            collection_name (str): The name of the collection to upload points to
            entities (Iterable[Any]): An iterator of entities (e.g. from BigQuery)
            mapper (Callable[[Any], PointStruct]): Function that converts an entity to a PointStruct
            batch_size (int): The number of points to upload in each batch (default: 64)
            parallel (int): The number of parallel upload tasks (default: 1)
            wait_timeout (int): Seconds to wait for the collection to become GREEN (default: 6000)
            check_existing (bool): Whether to check if points exist before uploading (default: True)

        Raises:
            Exception: If the upload operation fails
        """
        sync_client = QdrantClient(
            host=self.host,
            port=self.port,
            api_key=self.api_key,
            https=self.https,
            **self.kwargs,
        )

        entities = self._prepare_upload(collection_name, entities, mapper, sync_client)

        def safe_points_generator() -> Iterable[PointStruct]:
            """Generator that safely maps entities to points and optionally checks existence."""
            batch_buffer: list[PointStruct] = []

            for entity in entities:
                try:
                    point = mapper(entity)
                    if not check_existing:
                        yield point
                    else:
                        batch_buffer.append(point)
                        if len(batch_buffer) >= batch_size:
                            yield from process_batch(batch_buffer)
                            batch_buffer = []
                except Exception as map_err:  # pylint: disable=broad-exception-caught
                    logger.warning(
                        "Skipping entity due to mapping error: (%s: %s)",
                        type(map_err).__name__,
                        map_err,
                    )

            # Process remaining points in buffer
            if batch_buffer:
                yield from process_batch(batch_buffer)

        def process_batch(points: list[PointStruct]) -> Iterable[PointStruct]:
            """Helper to check existing IDs and yield only new points."""
            if not points:
                return

            ids_to_check = [p.id for p in points]
            try:
                existing_records = sync_client.retrieve(
                    collection_name=collection_name,
                    ids=ids_to_check,
                    with_payload=False,
                    with_vectors=False,
                )
                existing_ids = {r.id for r in existing_records}

                for point in points:
                    if point.id not in existing_ids:
                        yield point
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning(
                    "Failed to check existence for batch due to error: %s."
                    " Falling back to upserting all points in batch.",
                    e,
                )
                yield from points

        try:
            sync_client.upload_points(
                collection_name=collection_name,
                points=safe_points_generator(),
                batch_size=batch_size,
                parallel=parallel,
            )
            self.wait_for_collection_index(collection_name, sync_client, wait_timeout)
            logger.info("Successfully uploaded points to collection '%s'.", collection_name)
        except Exception as e:
            logger.error(
                "(%s: %s): Failed to upload points to collection '%s'.",
                type(e).__name__,
                e,
                collection_name,
            )
            raise

    def _validate_vector_compatibility(self, point: PointStruct, collection_config: Any) -> None:
        """Validate that a point's vector structure matches the collection configuration.

        Args:
            point: The point structure to validate
            collection_config: The collection info/configuration

        Raises:
            ValueError: If validation fails
        """
        vectors_config = collection_config.config.params.vectors

        if isinstance(vectors_config, dict):
            if not isinstance(point.vector, dict):
                raise ValueError(
                    f"Collection '{collection_config.config.name}' expects named vectors "
                    f"({list(vectors_config.keys())}),"
                    f" but point provided unnamed vector: {type(point.vector)}"
                )

            for name, config in vectors_config.items():
                if name not in point.vector:
                    logger.warning(
                        "Vector '%s' defined in collection but missing in point payload.", name
                    )
                    continue

                vec_data = point.vector[name]
                if hasattr(vec_data, "__len__") and len(vec_data) != config.size:
                    raise ValueError(
                        f"Dimension mismatch for vector '{name}': "
                        f"Expected {config.size}, got {len(vec_data)}"
                    )

        else:
            if isinstance(point.vector, dict):
                raise ValueError(
                    f"Collection '{collection_config.config.name}' expects unnamed vector, "
                    f"but point provided named vectors: {list(point.vector.keys())}"
                )

            if hasattr(point.vector, "__len__") and len(point.vector) != vectors_config.size:
                raise ValueError(
                    f"Dimension mismatch for vector: "
                    f"Expected {vectors_config.size}, got {len(point.vector)}"
                )

    def wait_for_collection_index(
        self,
        collection_name: str,
        sync_client: QdrantClient | None = None,
        timeout: int = 300,
    ) -> None:
        """Wait for the collection to be fully indexed (status GREEN).

        Args:
            collection_name (str): The name of the collection.
            sync_client (QdrantClient, optional): Synchronous Qdrant client. If None, it is created.
            timeout (int): Maximum time to wait in seconds (default: 300).
        """
        if sync_client is None:
            sync_client = QdrantClient(
                host=self.host,
                port=self.port,
                api_key=self.api_key,
                https=self.https,
                **self.kwargs,
            )

        logger.info("Waiting for collection '%s' to be ready (GREEN)...", collection_name)

        start_time = time()
        while True:
            collection_info = sync_client.get_collection(collection_name)
            if collection_info.status == CollectionStatus.GREEN:
                logger.debug("Collection '%s' status is GREEN.", collection_name)
                break

            if time() - start_time > timeout:
                logger.warning(
                    "Timed out waiting for collection '%s' to be GREEN after %d seconds."
                    " Current status: %s",
                    collection_name,
                    timeout,
                    collection_info.status,
                )
                break

            sleep(5.0)

    async def search_points(  # pylint: disable=too-many-arguments
        self,
        *,
        collection_name: str,
        query: list[float],
        vector_name: str,
        filters: Filter | None = None,
        limit: int = 10,
    ) -> list[ScoredPoint]:
        """Search for points in a collection based on a query vector.

        Args:
            collection_name (str): The name of the collection to search
            query (list[float]): The query vector
            vector_name (str): The name of the vector to search in.
            filters (Filter, optional): Filters to apply to the search (default: None)
            limit (int): The maximum number of results to return (default: 10)

        Returns:
            list[ScoredPoint]: The search results

        Raises:
            Exception: If the search operation fails
        """
        try:
            start_time = perf_counter()
            response = await self.client.query_points(
                collection_name=collection_name,
                query=query,
                using=vector_name,
                query_filter=filters,
                with_payload=True,
                with_vectors=True,
                limit=limit,
            )
            duration = perf_counter() - start_time
            logger.debug(
                "Search in collection '%s' completed in %.4f seconds.", collection_name, duration
            )
            return response.points
        except Exception as e:
            logger.error(
                "(%s) %s: Failed to search collection '%s' using vector name '%s'",
                type(e).__name__,
                e,
                collection_name,
                vector_name,
            )
            raise

    async def count_points(self, *, collection_name: str, filters: Filter | None = None) -> int:
        """Count points in a collection, optionally applying filters.

        Args:
            collection_name (str): The name of the collection
            filters (Filter, optional): Filters to apply to the count (default: None)

        Returns:
            int: The count of points in the collection
        """
        count_response = await self.client.count(
            collection_name=collection_name,
            count_filter=filters,
        )
        return count_response.count

    async def get_all_points(self, collection_name: str, limit: int = 1000) -> list[Record]:
        """Retrieve all points from a collection.

        Args:
            collection_name (str): The name of the collection
            limit (int): The maximum number of points to retrieve (default: 1000)

        Returns:
            list[Record]: The list of retrieved points
        """
        response = await self.client.scroll(
            collection_name=collection_name,
            limit=limit,
            with_vectors=True,
        )
        return response[0]

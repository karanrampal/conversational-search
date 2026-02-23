"""Performance/Latency tests for Qdrant database."""

import asyncio
import os
import random
import time
import uuid
from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from qdrant_client.models import PointStruct

from core.config import QDBConfig
from database.qdrant_manager import QdrantManager


class TestQdrantPerformance:
    """Performance test suite for Qdrant interactions."""

    @pytest.fixture
    def qdrant_config(self) -> QDBConfig:
        """Fixture for Qdrant configuration."""
        return QDBConfig(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
            api_key=SecretStr(os.getenv("QDRANT_API_KEY", "test-api-key")),
            collection_name="perf_test_collection",
        )

    @pytest.fixture
    def manager(self, qdrant_config: QDBConfig) -> QdrantManager:
        """Fixture for QdrantManager with connectivity check."""
        try:
            base_url = f"http://{qdrant_config.host}:{qdrant_config.port}/collections"
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(base_url)
                if resp.status_code not in (200, 403, 401):
                    pytest.skip(f"Qdrant reachable but returned {resp.status_code}")
        except (httpx.RequestError, OSError) as e:
            pytest.skip(
                f"Qdrant not available at {qdrant_config.host}:{qdrant_config.port}. "
                f"Skipping test. Error: {e}"
            )

        return QdrantManager(
            host=qdrant_config.host,
            port=qdrant_config.port,
            api_key=qdrant_config.api_key.get_secret_value(),
        )

    @pytest_asyncio.fixture
    async def seed_collection(self, manager: QdrantManager) -> AsyncGenerator[str, None]:
        """Creates a temp collection, seeds it with random vectors, and cleans up."""
        collection_name = f"perf_test_{uuid.uuid4().hex}"
        vector_size = 1408
        num_points = 2000

        await manager.create_collection(
            collection_name=collection_name,
            vector_configs={"image": (vector_size, "Cosine")},
            replication_factor=1,
        )

        points = [
            PointStruct(id=i, vector={"image": [random.uniform(-1, 1) for _ in range(vector_size)]})
            for i in range(num_points)
        ]

        # Batch upsert to avoid overwhelming the port-forward connection
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            await manager.client.upsert(collection_name=collection_name, points=batch)

        await asyncio.sleep(1)

        yield collection_name

        await manager.delete_collection(collection_name)

    @pytest.mark.asyncio
    async def test_qdrant_search_latency(
        self, manager: QdrantManager, seed_collection: str
    ) -> None:
        """Benchmark search latency against a seeded Qdrant instance."""

        collection_name = seed_collection
        vector_size = 1408
        query_vector = [random.uniform(-1, 1) for _ in range(vector_size)]

        for _ in range(3):
            await manager.search_points(
                collection_name=collection_name, query=query_vector, vector_name="image", limit=5
            )

        iterations = 20
        latencies = []

        for _ in range(iterations):
            start = time.perf_counter()
            await manager.search_points(
                collection_name=collection_name, query=query_vector, vector_name="image", limit=5
            )
            latencies.append(time.perf_counter() - start)

        avg_latency_ms = (sum(latencies) / len(latencies)) * 1000
        p95_latency_ms = sorted(latencies)[int(len(latencies) * 0.95)] * 1000

        print(
            f"\nQdrant Search Latency (N={iterations}): "
            f"Avg={avg_latency_ms:.2f}ms, P95={p95_latency_ms:.2f}ms"
        )

        # Assertion: Ensure we are under a reasonable SLA (e.g. 60ms for local/CI test)
        assert avg_latency_ms < 60.0, f"Qdrant search too slow! Avg: {avg_latency_ms:.2f}ms"

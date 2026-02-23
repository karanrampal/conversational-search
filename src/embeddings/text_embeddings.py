"""Text embeddings calculation module."""

import asyncio
import logging
from typing import Literal

import vertexai
from google import genai
from google.genai.types import EmbedContentConfig
from vertexai.vision_models import MultiModalEmbeddingModel

logger = logging.getLogger(__name__)


TaskType = Literal[
    "SEMANTIC_SIMILARITY",
    "CLASSIFICATION",
    "CLUSTERING",
    "RETRIEVAL_DOCUMENT",
    "RETRIEVAL_QUERY",
    "CODE_RETRIEVAL_QUERY",
    "QUESTION_ANSWERING",
    "FACT_VERIFICATION",
]


class TextEmbeddingsGen:
    """Class to handle text embeddings using GenAI.

    Args:
        project (str): GCP project ID.
        location (str, optional): GCP location. Defaults to "europe-west1".
        multimodal_model_name (str, optional): Name of the multi-modal model.
            Default is "multimodalembedding@001".
    """

    def __init__(
        self,
        project: str,
        location: str = "europe-west1",
        multimodal_model_name: str = "multimodalembedding@001",
    ) -> None:
        self.client = genai.Client(vertexai=True, project=project, location=location)
        vertexai.init(project=project, location=location)
        self.model = MultiModalEmbeddingModel.from_pretrained(multimodal_model_name)

    async def get_text_embedding(
        self,
        question: str,
        model: str = "gemini-embedding-001",
        task_type: TaskType = "RETRIEVAL_DOCUMENT",
        dimensions: int = 768,
    ) -> list[float]:
        """Get text embedding from GenAI.

        Args:
            question (str): Text to embed.
            model (str, optional): Embedding model to use. Defaults to "gemini-embedding-001".
            task_type (TaskType, optional): Type of retrieval task. Default is "RETRIEVAL_DOCUMENT".
            dimensions (int, optional): Dimensionality of the embedding. Defaults to 768.

        Returns:
            list[float]: Embedding vector.

        Raises:
            ValueError: If embedding fails.
        """
        response = await self.client.aio.models.embed_content(
            model=model,
            contents=question,
            config=EmbedContentConfig(task_type=task_type, output_dimensionality=dimensions),
        )
        if not response.embeddings or not response.embeddings[0].values:
            logger.error("Failed to get embeddings for the question `%s`", question)
            raise ValueError("No embeddings returned from the model.")
        return response.embeddings[0].values

    async def get_multimodal_text_embeddings(
        self, query: str, dimension: int = 1408
    ) -> list[float]:
        """Get multi-modal text embeddings from Vertex AI.

        Args:
            query (str): Text to embed.
            dimension (int, optional): Dimensionality of the embedding. Defaults to 1408.

        Returns:
            list[float]: Embedding vector.

        Raises:
            ValueError: If embedding fails.
        """
        embeddings = await asyncio.to_thread(
            self.model.get_embeddings, contextual_text=query, dimension=dimension
        )
        if not embeddings.text_embedding:
            logger.error("Failed to get multi-modal embeddings for the query `%s`", query)
            raise ValueError("No embeddings returned from the multi-modal model.")
        return embeddings.text_embedding

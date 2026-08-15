"""
celia.pro Embeddings Provider
==============================
Semantic embeddings using fastembed (ONNX-based, lightweight).

Uses sentence-transformers models for true semantic understanding:
- "hello" and "greetings" will be similar
- "ما هو الطقس؟" and "كيف الجو؟" will be similar

Fallback to hash-based embeddings if model is unavailable.
"""

from typing import List, Optional
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """
    Semantic embedding provider using fastembed.
    
    Features:
    - True semantic understanding (not hash-based)
    - Multilingual support (English, Arabic, etc.)
    - Lightweight (ONNX Runtime, ~100MB)
    - Lazy loading (model loaded on first use)
    
    Models:
    - Default: sentence-transformers/all-MiniLM-L6-v2 (384 dims, 90MB)
    - Alternative: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (384 dims, 500MB)
    """
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize embedding provider.
        
        Args:
            model_name: HuggingFace model name
                       Default: all-MiniLM-L6-v2 (English, fast)
                       Alternative: paraphrase-multilingual-MiniLM-L12-v2 (multilingual)
        """
        self.model_name = model_name
        self.model = None
        self.dimensions = 384  # all-MiniLM-L6-v2 produces 384-dimensional vectors
        self._initialized = False
        
        logger.info(f"EmbeddingProvider initialized with model: {model_name}")
    
    def _load_model(self):
        """Lazy load the model on first use."""
        if self._initialized:
            return
        
        try:
            from fastembed import TextEmbedding
            
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = TextEmbedding(model_name=self.model_name)
            self._initialized = True
            logger.info("Embedding model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            logger.warning("Falling back to hash-based embeddings (no semantic understanding)")
            self.model = None
            self._initialized = True
    
    def embed(self, text: str, dimensions: Optional[int] = None) -> List[float]:
        """
        Generate semantic embedding for text.
        
        Args:
            text: Input text to embed
            dimensions: Target dimensions (default: model's native dimensions)
                       If different from model's dimensions, will truncate/pad
        
        Returns:
            Semantic embedding vector (List[float])
        
        Example:
            >>> provider = EmbeddingProvider()
            >>> vector = provider.embed("Hello world")
            >>> len(vector)
            384
        """
        self._load_model()
        
        # Use real model if available
        if self.model is not None:
            try:
                # fastembed returns iterator of embeddings
                embeddings = list(self.model.embed([text]))
                if not embeddings:
                    from core.exceptions import ToolExecutionError
                    raise ToolExecutionError(
                        tool_name="embeddings",
                        message="No embedding generated"
                    )
                
                vector = embeddings[0].tolist()
                
                # Adjust dimensions if needed
                if dimensions and dimensions != len(vector):
                    if dimensions < len(vector):
                        # Truncate
                        vector = vector[:dimensions]
                    else:
                        # Pad with zeros
                        vector.extend([0.0] * (dimensions - len(vector)))
                
                return vector
                
            except Exception as e:
                logger.error(f"Embedding generation failed: {e}")
                logger.warning("Falling back to hash-based embedding")
        
        # Fallback to hash-based (no semantic understanding)
        return self._hash_embedding(text, dimensions or self.dimensions)
    
    def embed_batch(self, texts: List[str], dimensions: Optional[int] = None) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batch processing).
        
        Args:
            texts: List of texts to embed
            dimensions: Target dimensions
        
        Returns:
            List of embedding vectors
        
        Example:
            >>> provider = EmbeddingProvider()
            >>> vectors = provider.embed_batch(["Hello", "World"])
            >>> len(vectors)
            2
        """
        self._load_model()
        
        if self.model is not None:
            try:
                embeddings = list(self.model.embed(texts))
                vectors = [emb.tolist() for emb in embeddings]
                
                # Adjust dimensions if needed
                if dimensions and dimensions != len(vectors[0]):
                    vectors = [
                        v[:dimensions] if dimensions < len(v)
                        else v + [0.0] * (dimensions - len(v))
                        for v in vectors
                    ]
                
                return vectors
                
            except Exception as e:
                logger.error(f"Batch embedding failed: {e}")
                logger.warning("Falling back to hash-based embeddings")
        
        # Fallback to hash-based
        return [self._hash_embedding(text, dimensions or self.dimensions) for text in texts]
    
    def _hash_embedding(self, text: str, dimensions: int = 384) -> List[float]:
        """
        Fallback: Hash-based embedding (NO SEMANTIC UNDERSTANDING).
        
        This is only used when the real model is unavailable.
        Similar words will NOT be similar with this method.
        
        Args:
            text: Input text
            dimensions: Vector dimensions
        
        Returns:
            Deterministic hash-based vector (no semantic meaning)
        """
        import hashlib
        import numpy as np
        
        # Create deterministic seed from text
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**32)
        np.random.seed(seed)
        
        # Generate normalized vector
        vector = np.random.randn(dimensions).astype(float)
        vector = vector / np.linalg.norm(vector)  # Normalize
        
        return vector.tolist()
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
        
        Returns:
            Cosine similarity (-1 to 1, where 1 means identical)
        
        Example:
            >>> provider = EmbeddingProvider()
            >>> v1 = provider.embed("hello")
            >>> v2 = provider.embed("greetings")
            >>> similarity = provider.cosine_similarity(v1, v2)
            >>> similarity > 0.5  # Should be True with semantic model
            True
        """
        import numpy as np
        
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        
        # Handle dimension mismatch
        if len(v1) != len(v2):
            min_len = min(len(v1), len(v2))
            v1 = v1[:min_len]
            v2 = v2[:min_len]
        
        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))


# Global provider instance (lazy loading)
_provider: Optional[EmbeddingProvider] = None


def get_embedding_provider() -> EmbeddingProvider:
    """
    Get the global embedding provider instance.
    
    Returns:
        EmbeddingProvider instance (singleton)
    
    Example:
        >>> provider = get_embedding_provider()
        >>> vector = provider.embed("Hello world")
    """
    global _provider
    if _provider is None:
        _provider = EmbeddingProvider()
    return _provider


def generate_embedding(text: str, dimensions: int = 384) -> List[float]:
    """
    Generate semantic embedding for text.
    
    This is the main API function. It uses a real semantic model
    (sentence-transformers via fastembed) to generate meaningful vectors.
    
    ✅ CURRENT IMPLEMENTATION: Semantic embeddings (fastembed)
    - True semantic understanding
    - "hello" and "greetings" will be similar
    - Multilingual support
    
    Args:
        text: Input text to embed
        dimensions: Vector dimensions (default: 384 for all-MiniLM-L6-v2)
    
    Returns:
        Semantic embedding vector (List[float])
    
    Example:
        >>> vector = generate_embedding("Hello world")
        >>> len(vector)
        384
        >>> 
        >>> # Semantic similarity test
        >>> v1 = generate_embedding("hello")
        >>> v2 = generate_embedding("greetings")
        >>> v3 = generate_embedding("car")
        >>> # v1 and v2 should be more similar than v1 and v3
    """
    provider = get_embedding_provider()
    return provider.embed(text, dimensions=dimensions)


def generate_embeddings_batch(texts: List[str], dimensions: int = 384) -> List[List[float]]:
    """
    Generate embeddings for multiple texts (batch processing).
    
    More efficient than calling generate_embedding() multiple times.
    
    Args:
        texts: List of texts to embed
        dimensions: Vector dimensions
    
    Returns:
        List of embedding vectors
    
    Example:
        >>> vectors = generate_embeddings_batch(["Hello", "World", "Test"])
        >>> len(vectors)
        3
    """
    provider = get_embedding_provider()
    return provider.embed_batch(texts, dimensions=dimensions)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Convenience function that uses the global provider.
    
    Args:
        vec1: First vector
        vec2: Second vector
    
    Returns:
        Cosine similarity (-1 to 1)
    
    Example:
        >>> v1 = generate_embedding("hello")
        >>> v2 = generate_embedding("greetings")
        >>> similarity = cosine_similarity(v1, v2)
        >>> similarity > 0.5  # Semantic similarity
        True
    """
    provider = get_embedding_provider()
    return provider.cosine_similarity(vec1, vec2)

"""AI-powered tag classification using sentence transformers."""

import numpy as np
from sentence_transformers import SentenceTransformer

from .config import config
from .models import Note, Tag, TagSuggestion


class LocalClassifier:
    """
    Tag classifier using sentence-transformers for semantic similarity.
    
    This classifier:
    1. Generates embeddings for all tag names
    2. For each note, generates an embedding of its content
    3. Computes cosine similarity between note and all tags
    4. Returns top-K most similar tags as suggestions
    """
    
    def __init__(self, model_name: str | None = None):
        """
        Initialize the classifier with a sentence transformer model.
        
        Args:
            model_name: HuggingFace model name. Defaults to config value.
        """
        self.model_name = model_name or config.embedding_model
        self._model: SentenceTransformer | None = None
        self._tag_embeddings: np.ndarray | None = None
        self._tags: list[Tag] = []
    
    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load the model on first use."""
        if self._model is None:
            print(f"Loading model: {self.model_name}...")
            self._model = SentenceTransformer(self.model_name)
            print("Model loaded!")
        return self._model
    
    def load_tags(self, tags: list[Tag]) -> None:
        """
        Pre-compute embeddings for all tags.
        
        Args:
            tags: List of tags to embed
        """
        self._tags = tags
        
        # Create rich descriptions for better matching
        tag_texts = []
        for tag in tags:
            # Use name + description if available
            text = tag.name
            if tag.description:
                text = f"{tag.name}: {tag.description}"
            tag_texts.append(text)
        
        # Generate embeddings
        self._tag_embeddings = self.model.encode(
            tag_texts,
            convert_to_numpy=True,
            show_progress_bar=len(tags) > 20
        )
        
        # Store embeddings in tag objects for reference
        for i, tag in enumerate(self._tags):
            tag.embedding = self._tag_embeddings[i].tolist()
    
    def classify(
        self,
        note: Note,
        top_k: int = 3,
        min_score: float = 0.2
    ) -> list[TagSuggestion]:
        """
        Classify a note and return suggested tags.
        
        Args:
            note: The note to classify
            top_k: Maximum number of suggestions to return
            min_score: Minimum similarity score threshold
            
        Returns:
            List of TagSuggestion objects sorted by score (descending)
        """
        if self._tag_embeddings is None or len(self._tags) == 0:
            raise ValueError("Tags not loaded. Call load_tags() first.")
        
        # Combine note name and content for better matching
        note_text = note.name
        if note.content:
            note_text = f"{note.name}\n{note.content}"
        
        # Skip empty notes
        if not note_text.strip():
            return []
        
        # Generate note embedding
        note_embedding = self.model.encode(
            note_text,
            convert_to_numpy=True
        )
        
        # Compute cosine similarities
        similarities = self._cosine_similarity(note_embedding, self._tag_embeddings)
        
        # Get top-K indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # Build suggestions
        suggestions = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score >= min_score:
                suggestions.append(TagSuggestion(
                    tag=self._tags[idx],
                    score=score
                ))
        
        return suggestions
    
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Compute cosine similarity between vector a and matrix b."""
        # Normalize vectors
        a_norm = a / np.linalg.norm(a)
        b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
        
        # Dot product gives cosine similarity for normalized vectors
        return np.dot(b_norm, a_norm)


# Singleton instance for reuse
_classifier: LocalClassifier | None = None


def get_classifier() -> LocalClassifier:
    """Get or create the global classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = LocalClassifier()
    return _classifier

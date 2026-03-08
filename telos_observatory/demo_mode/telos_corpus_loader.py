"""
TELOS Corpus Loader for Demo Mode
==================================

CRITICAL: This loader uses HUMAN-READABLE content ONLY.
NOT technical documentation. NOT code. NOT architecture diagrams.

This is The Steward's knowledge base - explanations a human can understand.

**Layer 2: RAG Corpus** (Knowledge Base - The North Star)
- Human-friendly explanations of TELOS
- Plain English, no technical jargon vomit
- Presentable responses users can understand

**What Gets Loaded:**
- demo_mode/corpus/TELOS_HUMAN_EXPLAINER.md - Main explanation document
- demo_mode/corpus/TELOS_QUICK_ANSWERS.md - FAQ-style quick answers

**What Does NOT Get Loaded:**
- Technical whitepapers (too dense, machine-specific)
- Architecture guides (implementation details, not user-facing)
- Code documentation (not relevant to users)
- Academic papers (research language, not conversation language)

Architecture:
------------
1. PA checks if question is within scope
2. RAG retrieves relevant HUMAN-READABLE chunks
3. LLM generates response using CLEAR, UNDERSTANDABLE context
4. PA validates response aligns with purpose

This creates The Steward - an AI that explains like a human, not a manual.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

# HUMAN-READABLE corpus files ONLY
# These are curated, clean explanations - NOT technical docs
# Includes BOTH technical knowledge (WHAT) and clinical empathy (HOW)
HUMAN_CORPUS_FILES = [
    # Clinical empathy - HOW to communicate with dignity and respect
    "CLINICAL_COMMUNICATION.md",      # Evidence-based communication principles
    "EMPATHIC_FACILITATION.md",       # Practical facilitation techniques
    # TELOS knowledge - WHAT to explain
    "TELOS_HUMAN_EXPLAINER.md",       # TELOS conceptual overview
    "TELOS_QUICK_ANSWERS.md",         # TELOS quick reference / FAQ
    "TELOS_IMPLEMENTATION.md",        # TELOS actual implementation details (how the code works)
]

# Corpus directory (relative to this file)
CORPUS_DIR = Path(__file__).parent / "corpus"


class CorpusLoadError(Exception):
    """Raised when corpus loading fails catastrophically."""
    pass


class CorpusRetrievalError(Exception):
    """Raised when retrieval fails."""
    pass


class TELOSCorpusLoader:
    """
    Loads and manages HUMAN-READABLE TELOS explanations for RAG retrieval.

    CRITICAL: Uses curated human-friendly content ONLY.
    NO technical docs, NO code, NO jargon vomit.

    This provides Layer 2 (Knowledge Base) for Demo Mode's two-layer architecture.
    """

    def __init__(self, embedding_provider):
        """
        Initialize corpus loader.

        Args:
            embedding_provider: SentenceTransformerProvider for encoding chunks

        Raises:
            CorpusLoadError: If initialization fails critically
        """
        try:
            if embedding_provider is None:
                raise ValueError("embedding_provider cannot be None")

            self.embedding_provider = embedding_provider
            self.corpus_dir = CORPUS_DIR

            # Storage for corpus
            self.documents: List[Dict[str, Any]] = []
            self.embeddings: Optional[np.ndarray] = None
            self._corpus_loaded = False

            # Verify corpus directory exists
            if not self.corpus_dir.exists():
                raise FileNotFoundError(
                    f"Corpus directory not found: {self.corpus_dir}\n"
                    f"Expected human-readable corpus files in demo_mode/corpus/"
                )

            logger.info(f"✓ TELOSCorpusLoader initialized")
            logger.info(f"  Corpus directory: {self.corpus_dir}")
            logger.info(f"  Will load: {', '.join(HUMAN_CORPUS_FILES)}")

        except Exception as e:
            logger.error(f"✗ Failed to initialize TELOSCorpusLoader: {e}", exc_info=True)
            raise CorpusLoadError(f"Corpus loader initialization failed: {e}") from e

    def load_corpus(self, file_list: Optional[List[str]] = None):
        """
        Load HUMAN-READABLE TELOS explanation files into corpus.

        CRITICAL: Uses ONLY curated human-friendly content.
        NO technical docs, NO code, NO jargon.

        Args:
            file_list: Optional list of filenames to load.
                      Defaults to HUMAN_CORPUS_FILES (curated list).

        Returns:
            int: Number of document chunks loaded

        Raises:
            CorpusLoadError: If loading fails critically (zero chunks loaded)
        """
        try:
            # Use human-readable corpus by default
            if file_list is None:
                file_list = HUMAN_CORPUS_FILES

            logger.info("="*60)
            logger.info("LOADING HUMAN-READABLE CORPUS")
            logger.info("="*60)
            logger.info(f"Target files: {', '.join(file_list)}")
            logger.info(f"Source directory: {self.corpus_dir}")

            # Reset documents
            self.documents = []
            loaded_files = []
            failed_files = []

            # Load each file explicitly (no globbing - be deterministic)
            for filename in file_list:
                file_path = self.corpus_dir / filename

                try:
                    if not file_path.exists():
                        logger.warning(f"✗ File not found: {filename}")
                        failed_files.append(f"{filename} (not found)")
                        continue

                    logger.info(f"→ Loading: {filename}")
                    chunks = self._load_and_chunk_file(file_path)

                    if not chunks:
                        logger.warning(f"  ⚠ No chunks extracted from {filename}")
                        failed_files.append(f"{filename} (empty)")
                        continue

                    self.documents.extend(chunks)
                    loaded_files.append(filename)
                    logger.info(f"  ✓ Added {len(chunks)} chunks from {filename}")

                except Exception as file_error:
                    logger.error(f"  ✗ Failed to load {filename}: {file_error}")
                    failed_files.append(f"{filename} (error: {file_error})")
                    continue

            # Check if we loaded anything
            if not self.documents:
                error_msg = (
                    f"✗ CORPUS LOAD FAILED: Zero chunks loaded\n"
                    f"  Attempted files: {', '.join(file_list)}\n"
                    f"  Failed files: {', '.join(failed_files)}\n"
                    f"  Corpus directory: {self.corpus_dir}"
                )
                logger.error(error_msg)
                raise CorpusLoadError(error_msg)

            # Generate embeddings for all chunks
            logger.info(f"→ Generating embeddings for {len(self.documents)} chunks...")
            try:
                self._generate_embeddings()
                logger.info(f"  ✓ Embeddings generated")
            except Exception as embed_error:
                logger.error(f"  ✗ Embedding generation failed: {embed_error}")
                raise CorpusLoadError(f"Embedding generation failed: {embed_error}") from embed_error

            # Mark as successfully loaded
            self._corpus_loaded = True

            # Summary
            logger.info("="*60)
            logger.info(f"✓ CORPUS LOADED SUCCESSFULLY")
            logger.info(f"  Total chunks: {len(self.documents)}")
            logger.info(f"  Loaded files: {', '.join(loaded_files)}")
            if failed_files:
                logger.warning(f"  Failed files: {', '.join(failed_files)}")
            logger.info("="*60)

            return len(self.documents)

        except CorpusLoadError:
            # Re-raise our own exceptions
            raise
        except Exception as e:
            # Catch-all for unexpected errors
            error_msg = f"✗ Unexpected corpus load error: {e}"
            logger.error(error_msg, exc_info=True)
            raise CorpusLoadError(error_msg) from e

    def _load_and_chunk_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Load a markdown file and split into semantic chunks.

        Args:
            file_path: Path to markdown file

        Returns:
            List of chunk dictionaries with text, metadata, etc.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Simple chunking strategy: split on section headers (## )
        # This preserves semantic coherence
        chunks = []
        sections = content.split('\n## ')

        for i, section in enumerate(sections):
            if not section.strip():
                continue

            # Add back the header marker (except for first section)
            if i > 0:
                section = '## ' + section

            # Create chunk metadata
            chunk = {
                'text': section.strip(),
                'source_file': file_path.name,
                'chunk_id': f"{file_path.stem}_chunk_{i}",
                'char_count': len(section)
            }

            chunks.append(chunk)

        return chunks

    def _generate_embeddings(self):
        """
        Generate embeddings for all corpus chunks using embedding provider.
        """
        if not self.documents:
            logger.warning("No documents to embed!")
            return

        # Extract text from all chunks
        texts = [doc['text'] for doc in self.documents]

        # Generate embeddings (batch operation)
        self.embeddings = np.array([
            self.embedding_provider.encode(text) for text in texts
        ])

        logger.info(f"Generated embeddings with shape: {self.embeddings.shape}")

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve most relevant HUMAN-READABLE corpus chunks for a query.

        Args:
            query: User's question or topic
            top_k: Number of top chunks to retrieve (default: 3)

        Returns:
            List of top-k most relevant chunks with similarity scores.
            Returns empty list on error (graceful degradation).

        Note:
            This method NEVER raises exceptions - it degrades gracefully.
            Errors are logged but don't crash the system.
        """
        try:
            # Validation
            if not query or not query.strip():
                logger.warning("Empty query provided to retrieve()")
                return []

            if top_k < 1:
                logger.warning(f"Invalid top_k={top_k}, using default=3")
                top_k = 3

            # Check corpus is loaded
            if not self._corpus_loaded:
                logger.error("✗ Corpus not loaded! Call load_corpus() first.")
                return []

            if not self.documents:
                logger.error("✗ No documents in corpus!")
                return []

            if self.embeddings is None:
                logger.error("✗ Embeddings not generated!")
                return []

            # Encode query
            try:
                query_embedding = self.embedding_provider.encode(query)
            except Exception as encode_error:
                logger.error(f"✗ Failed to encode query: {encode_error}")
                return []

            # Compute cosine similarity with all chunks
            # cosine_sim = dot(query, doc) / (||query|| * ||doc||)
            try:
                query_norm = np.linalg.norm(query_embedding)
                if query_norm == 0:
                    logger.warning("Query embedding has zero norm!")
                    return []

                doc_norms = np.linalg.norm(self.embeddings, axis=1)
                similarities = np.dot(self.embeddings, query_embedding) / (doc_norms * query_norm + 1e-8)

            except Exception as sim_error:
                logger.error(f"✗ Similarity computation failed: {sim_error}")
                return []

            # Get top-k indices
            try:
                # Clamp top_k to available documents
                actual_k = min(top_k, len(similarities))
                top_indices = np.argsort(similarities)[-actual_k:][::-1]

            except Exception as sort_error:
                logger.error(f"✗ Sorting failed: {sort_error}")
                return []

            # Build results
            results = []
            for idx in top_indices:
                try:
                    results.append({
                        **self.documents[idx],
                        'similarity': float(similarities[idx])
                    })
                except Exception as result_error:
                    logger.warning(f"  ⚠ Failed to package result {idx}: {result_error}")
                    continue

            # Log results
            logger.info(f"✓ Retrieved {len(results)} chunks for query: '{query[:50]}...'")
            for i, result in enumerate(results):
                logger.info(f"  {i+1}. {result['source_file']} (sim: {result['similarity']:.3f})")

            return results

        except Exception as e:
            # Catch-all: log but don't crash
            logger.error(f"✗ Unexpected retrieval error: {e}", exc_info=True)
            return []

    def get_stats(self) -> Dict[str, Any]:
        """
        Get corpus statistics.

        Returns:
            Dictionary with corpus stats (num_docs, total_chars, etc.)
        """
        return {
            'num_chunks': len(self.documents),
            'total_characters': sum(doc['char_count'] for doc in self.documents),
            'source_files': list(set(doc['source_file'] for doc in self.documents)),
            'embeddings_generated': self.embeddings is not None
        }


def format_context_for_llm(retrieved_chunks: List[Dict[str, Any]]) -> str:
    """
    Format retrieved HUMAN-READABLE corpus chunks for LLM prompt.

    IMPORTANT: This presents clean, human-friendly context.
    NO technical vomit, NO code, NO machine specs.

    Args:
        retrieved_chunks: List of chunks from retrieve()

    Returns:
        Clean, formatted context string for LLM consumption
    """
    if not retrieved_chunks:
        logger.warning("No chunks to format - empty context")
        return ""

    try:
        context_parts = []
        context_parts.append("=== TELOS Knowledge Base ===")
        context_parts.append("The following are human-friendly explanations of TELOS concepts:")
        context_parts.append("")

        for i, chunk in enumerate(retrieved_chunks, 1):
            # Extract metadata safely
            source = chunk.get('source_file', 'Unknown')
            similarity = chunk.get('similarity', 0.0)
            text = chunk.get('text', '').strip()

            if not text:
                logger.warning(f"Empty text in chunk {i}")
                continue

            context_parts.append(f"--- Section {i} (from {source}, relevance: {similarity:.2f}) ---")
            context_parts.append(text)
            context_parts.append("")  # Blank line between sections

        context_parts.append("=== End Knowledge Base ===")
        context_parts.append("")

        formatted = "\n".join(context_parts)
        logger.info(f"✓ Formatted {len(retrieved_chunks)} chunks into context ({len(formatted)} chars)")

        return formatted

    except Exception as e:
        logger.error(f"✗ Failed to format context: {e}")
        return ""  # Graceful degradation

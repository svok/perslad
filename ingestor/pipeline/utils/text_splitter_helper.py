"""
Text Splitter Helper - Shared logic for chunking text.

Provides common functionality for chunking both files and queries,
making it reusable across different pipelines.
"""

import hashlib
import aiofiles
from typing import List, Dict, Any, Tuple, Optional

from llama_index.core.node_parser import CodeSplitter, MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import Document


class TextSplitterHelper:
    """
    Helper class for text chunking operations.
    
    Provides methods for:
    - Creating splitters for different file types
    - Chunking files
    - Chunking arbitrary text
    
    All methods return errors instead of silently swallowing them.
    """

    @staticmethod
    def create_splitter(extension: str) -> Tuple[str, CodeSplitter | MarkdownNodeParser | SentenceSplitter]:
        """
        Creates a splitter and returns its type based on file extension.
        
        Args:
            extension: File extension including dot (e.g., '.py', '.md')
        
        Returns:
            Tuple of (chunk_type, splitter)
        """
        if extension == ".py":
            return "code", CodeSplitter(
                language="python",
                chunk_lines=40,
                chunk_lines_overlap=15,
                max_chars=1500,
            )
        elif extension == ".md":
            return "doc", MarkdownNodeParser()
        elif extension in {".yaml", ".yml", ".toml"}:
            return "config", SentenceSplitter(
                chunk_size=512,
                chunk_overlap=50,
            )
        else:
            return "text", SentenceSplitter(
                chunk_size=512,
                chunk_overlap=50,
            )

    @staticmethod
    async def chunk_text(
        text: str,
        splitter: CodeSplitter | MarkdownNodeParser | SentenceSplitter,
        chunk_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Splits text into chunks using the given splitter.
        
        Args:
            text: Text to split
            splitter: LlamaIndex splitter to use
            chunk_type: Type identifier for the chunk type
            metadata: Additional metadata for each chunk
        
        Returns:
            Tuple of (chunks, error). chunks is List of dicts with keys: content, metadata, chunk_type.
            error is None on success, error message string on failure.
        """
        if not text or not text.strip():
            return [], None

        doc = Document(
            text=text,
            metadata=metadata or {},  # type: ignore[arg-type]
        )

        try:
            nodes = splitter.get_nodes_from_documents([doc])
        except Exception as e:
            return [], f"Failed to split text with splitter {type(splitter).__name__}: {e}"

        return [
            {
                "content": getattr(node, "text", None),
                "metadata": getattr(node, "metadata", {}),
                "chunk_type": chunk_type,
            }
            for node in nodes
        ], None

    @staticmethod
    async def read_file_content(
        file_path: str,
        relative_path: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Reads file content with encoding handling.
        
        Args:
            file_path: Absolute file path
            relative_path: Relative path for error messages
        
        Returns:
            Tuple of (content, error). content is the file content or None if failed.
            error is None on success, error message string on failure.
        """
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                async with aiofiles.open(file_path, 'r', encoding=encoding, errors='strict') as f:
                    content = await f.read()
                return content, None
            except UnicodeDecodeError:
                continue
            except FileNotFoundError:
                return None, f"File not found: {relative_path}"
            except PermissionError:
                return None, f"Permission denied: {relative_path}"
            except Exception as e:
                return None, f"Failed to read {relative_path} with encoding {encoding}: {e}"
        
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = await f.read()
            return content, None
        except Exception as e:
            return None, f"Failed to read {relative_path}: {e}"

    @staticmethod
    def generate_chunk_id(file_path: str, index: int) -> str:
        """
        Generates deterministic chunk ID.
        
        Args:
            file_path: File path
            index: Chunk index
        
        Returns:
            Hash-based chunk ID (16 chars)
        """
        content = f"{file_path}::{index}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @staticmethod
    async def chunk_file(
        file_path: str,
        relative_path: str,
        extension: str,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Chunks a file using the appropriate splitter.
        
        Args:
            file_path: Absolute file path
            relative_path: Relative path for logging
            extension: File extension including dot
        
        Returns:
            Tuple of (chunks, error). chunks is List of chunk dicts, error is None on success.
        """
        content, error = await TextSplitterHelper.read_file_content(file_path, relative_path)
        if error is not None:
            return [], error
        if content is None:
            return [], f"Failed to read content from {relative_path}"

        chunk_type, splitter = TextSplitterHelper.create_splitter(extension)

        try:
            nodes = splitter.get_nodes_from_documents([
                Document(
                    text=content,
                    metadata={
                        "file_path": relative_path,
                        "extension": extension,
                    },
                )
            ])
        except Exception as e:
            return [], f"Failed to split file {relative_path}: {e}"

        chunks = []
        for idx, node in enumerate(nodes):
            chunk_id = TextSplitterHelper.generate_chunk_id(relative_path, idx)

            chunks.append({
                "id": chunk_id,
                "file_path": relative_path,
                "content": getattr(node,"text", None),
                "start_line": node.metadata.get("start_line", 0),
                "end_line": node.metadata.get("end_line", 0),
                "chunk_type": chunk_type,
                "metadata": {
                    "extension": extension,
                    "chunk_index": idx,
                    **node.metadata,
                },
            })

        return chunks, None

    @staticmethod
    def split_query_by_sentences(query: str, max_chars: int = 2000) -> Tuple[List[str], Optional[str]]:
        """
        Splits a query into sentences, handling large queries gracefully.
        
        Args:
            query: User query text
            max_chars: Maximum characters per chunk
        
        Returns:
            Tuple of (chunks, error). chunks is List of query chunks, error is None on success.
        """
        if not query or not query.strip():
            return [], None

        import re

        sentences = re.split(r'([.!?])\s+', query)

        sentences = [''.join([sentences[i], sentences[i+1]]).strip()
                     for i in range(0, len(sentences)-1, 2)]

        final_chunks = []
        for s in sentences:
            if len(s) <= max_chars:
                final_chunks.append(s)
            else:
                words = s.split()
                for i in range(0, len(words), max_chars // 200):
                    chunk = ' '.join(words[i:i+max_chars//200])
                    if chunk:
                        final_chunks.append(chunk)

        return final_chunks if final_chunks else [query], None

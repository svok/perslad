"""
Text Splitter Helper - Shared logic for chunking text.

Provides common functionality for chunking both files and queries,
making it reusable across different pipelines.
"""

import hashlib
from typing import List, Dict, Any, Tuple

from llama_index.core.node_parser import CodeSplitter, MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import Document


class TextSplitterHelper:
    """
    Helper class for text chunking operations.
    
    Provides methods for:
    - Creating splitters for different file types
    - Chunking files
    - Chunking arbitrary text
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
    def chunk_text(
        text: str,
        splitter: CodeSplitter | MarkdownNodeParser | SentenceSplitter,
        chunk_type: str = "text",
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Splits text into chunks using the given splitter.
        
        Args:
            text: Text to split
            splitter: LlamaIndex splitter to use
            chunk_type: Type identifier for the chunk type
            metadata: Additional metadata for each chunk
        
        Returns:
            List of dicts with keys: content, metadata, chunk_type
        """
        if not text or not text.strip():
            return []

        doc = Document(
            text=text,
            metadata=metadata or {},
        )

        try:
            nodes = splitter.get_nodes_from_documents([doc])
        except Exception as e:
            raise ValueError(f"Failed to split text with splitter {type(splitter)}: {e}")

        return [
            {
                "content": getattr(node, "text", None),
                "metadata": getattr(node, "metadata", {}),
                "chunk_type": chunk_type,
            }
            for node in nodes
        ]

    @staticmethod
    def read_file_content(
        file_path: str,
        relative_path: str
    ) -> str | None:
        """
        Reads file content with encoding handling.
        Tries multiple encodings. Returns None if all fail (likely binary).
        """
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding, errors='strict') as f:
                    content = f.read()
                return content
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"Warning: Failed to read {relative_path} with encoding {encoding}: {e}")
                return None
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            print(f"Warning: Used UTF-8 with errors ignored for {relative_path}")
            return content
        except Exception as e:
            print(f"Warning: Failed to read {relative_path}: {e}")
            return None

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
    def chunk_file(
        file_path: str,
        relative_path: str,
        extension: str,
        text_splitter_helper: 'TextSplitterHelper'
    ) -> List[Dict[str, Any]]:
        """
        Chunks a file using the appropriate splitter.
        
        Args:
            file_path: Absolute file path
            relative_path: Relative path for logging
            extension: File extension including dot
            text_splitter_helper: Instance of TextSplitterHelper
        
        Returns:
            List of chunk dicts
        """
        content = text_splitter_helper.read_file_content(file_path, relative_path)
        if content is None:
            return []

        chunk_type, splitter = text_splitter_helper.create_splitter(extension)

        nodes = splitter.get_nodes_from_documents([
            Document(
                text=content,
                metadata={
                    "file_path": relative_path,
                    "extension": extension,
                },
            )
        ])

        chunks = []
        for idx, node in enumerate(nodes):
            chunk_id = text_splitter_helper.generate_chunk_id(relative_path, idx)

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

        return chunks

    @staticmethod
    def split_query_by_sentences(query: str, max_chars: int = 2000) -> List[str]:
        """
        Splits a query into sentences, handling large queries gracefully.
        
        Args:
            query: User query text
            max_chars: Maximum characters per chunk
        
        Returns:
            List of query chunks
        """
        if not query or not query.strip():
            return []

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

        return final_chunks if final_chunks else [query]

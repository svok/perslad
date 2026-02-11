"""
Test script for the new knowledge search pipeline.

This script demonstrates how to use the new KnowledgeSearchPipeline
and TextSplitterHelper components.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


async def test_text_splitter_helper():
    """Test basic TextSplitterHelper functionality."""
    print("=== Testing TextSplitterHelper ===")
    
    from ingestor.pipeline.impl.text_splitter_helper import TextSplitterHelper
    
    helper = TextSplitterHelper()
    
    # Test 1: Create splitter for different extensions
    chunk_type, splitter = helper.create_splitter(".py")
    print(f"✓ Created splitter for .py: type={chunk_type}, splitter={type(splitter).__name__}")
    
    chunk_type, splitter = helper.create_splitter(".md")
    print(f"✓ Created splitter for .md: type={chunk_type}, splitter={type(splitter).__name__}")
    
    chunk_type, splitter = helper.create_splitter(".txt")
    print(f"✓ Created splitter for .txt: type={chunk_type}, splitter={type(splitter).__name__}")
    
    # Test 2: Chunk a simple text
    test_text = "This is a simple test. We want to split this into chunks."
    chunks = helper.chunk_text(
        text=test_text,
        splitter=helper.create_splitter(".txt")[1],
        chunk_type="test"
    )
    print(f"✓ Chunked text into {len(chunks)} parts")
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i}: {chunk['content'][:50]}...")
    
    # Test 3: Chunk a file (simulated)
    file_content = """def hello():
    print("Hello world")
    
def goodbye():
    print("Goodbye world")"""
    
    chunks = helper.chunk_file(
        file_path="/tmp/test.py",
        relative_path="test.py",
        extension=".py",
        text_splitter_helper=helper
    )
    print(f"✓ Chunked file into {len(chunks)} parts")
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i}: {chunk['content'][:50]}...")
    
    print("\n✅ TextSplitterHelper tests passed!\n")


async def test_query_text_chunker():
    """Test QueryTextChunker functionality."""
    print("=== Testing QueryTextChunker ===")
    
    from ingestor.pipeline.impl.text_splitter_helper import TextSplitterHelper
    from ingestor.pipeline.knowledge_search.query_text_chunker import QueryTextChunker
    
    helper = TextSplitterHelper()
    chunker = QueryTextChunker(helper, chunk_size=2000)
    
    # Test 1: Chunk a simple query
    query = "This is a test query with several sentences."
    chunks = await chunker.chunk(query)
    print(f"✓ Chunks: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i}: {chunk['content'][:50]}...")
    
    # Test 2: Chunk a large query
    long_query = """
    This is a longer query that goes on and on. It has multiple sentences
    and should be split into smaller chunks for better embedding performance.
    
    The purpose of chunking is to break down long text into manageable pieces
    that can be processed by the embedding model without exceeding the context window.
    """
    chunks = await chunker.chunk(long_query)
    print(f"✓ Large query split into {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i}: {len(chunk['content'])} chars")
    
    print("\n✅ QueryTextChunker tests passed!\n")


async def test_search_pipeline():
    """Test KnowledgeSearchPipeline functionality."""
    print("=== Testing KnowledgeSearchPipeline ===")
    
    from ingestor.adapters.memory.storage import MemoryStorage as InMemoryStorage
    from ingestor.pipeline.impl.text_splitter_helper import TextSplitterHelper
    from ingestor.pipeline.knowledge_search.pipeline import KnowledgeSearchPipeline
    
    # Create storage
    storage = InMemoryStorage()
    await storage.initialize()
    
    # Add some test chunks
    helper = TextSplitterHelper()
    
    test_chunks = [
        {
            "id": "1",
            "file_path": "test1.py",
            "content": "This is a simple function that does something.",
            "summary": "Simple function",
            "purpose": "Does something",
            "chunk_type": "code",
            "embedding": [0.1, 0.2, 0.3]  # Simple embedding for testing
        },
        {
            "id": "2",
            "file_path": "test2.py",
            "content": "Another function that does completely different things.",
            "summary": "Different function",
            "purpose": "Does different things",
            "chunk_type": "code",
            "embedding": [0.4, 0.5, 0.6]
        },
        {
            "id": "3",
            "file_path": "test1.py",
            "content": "The third chunk from the first file.",
            "summary": "Third chunk",
            "purpose": "Continues the story",
            "chunk_type": "code",
            "embedding": [0.7, 0.8, 0.9]
        }
    ]
    
    from ingestor.core.models.chunk import Chunk
    for chunk_data in test_chunks:
        chunk = Chunk(
            id=chunk_data["id"],
            file_path=chunk_data["file_path"],
            content=chunk_data["content"],
            start_line=0,
            end_line=10,
            chunk_type=chunk_data["chunk_type"],
            summary=chunk_data["summary"],
            purpose=chunk_data["purpose"],
            embedding=chunk_data["embedding"],
            metadata={}
        )
        await storage.save_chunk(chunk)
    
    print(f"✓ Added {len(test_chunks)} test chunks to storage")
    
    # Create search pipeline with embedding model (placeholder)
    # For testing, we'll create a mock embedding model

    class MockEmbeddingModel:
        async def get_embedding(self, text: str):
            import numpy as np
            # Return random embedding for testing
            return list(np.random.rand(1536))
    
    embed_model = MockEmbeddingModel()
    search_pipeline = KnowledgeSearchPipeline(
        storage=storage,
        text_splitter_helper=helper,
        embedding_model=embed_model,
        query_chunk_size=2000,
        top_k_per_query=2
    )
    
    # Test search with a query
    query = "simple function that does something"
    print(f"✓ Searching for: '{query}'")
    
    results = await search_pipeline.search(query, top_k=2)
    
    print(f"✓ Found {len(results['results'])} results")
    for i, result in enumerate(results["results"]):
        print(f"  Result {i}:")
        print(f"    ID: {result['chunk_id']}")
        print(f"    File: {result['file_path']}")
        print(f"    Score: {result['similarity']:.4f}")
        print(f"    Content: {result['content'][:50]}...")
    
    print("\n✅ KnowledgeSearchPipeline tests passed!\n")
    
    # Cleanup
    await storage.clear()
    print("✓ Cleaned up test storage")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Knowledge Search Pipeline Tests")
    print("=" * 60)
    print()
    
    try:
        await test_text_splitter_helper()
        await test_query_text_chunker()
        await test_search_pipeline()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

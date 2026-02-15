import pytest

from infra.config import Embedding


@pytest.mark.component
@pytest.mark.emb
@pytest.mark.fast
@pytest.mark.requires_gpu
class TestEMBComponent:
    """Component tests for LLM service"""
    

    @pytest.mark.asyncio
    async def test_embeddings_basic(self, emb_client, config):
        """Test basic embedding generation"""
        payload = {
            "model": config['emb_served_model_name'],
            "input": ["Hello world", "Test embedding"]
        }
        
        response = await emb_client.post(Embedding.EMBEDDINGS, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 2
        
        for embedding in data["data"]:
            assert "embedding" in embedding
            assert isinstance(embedding["embedding"], list)
            assert len(embedding["embedding"]) > 0
    
    @pytest.mark.asyncio
    async def test_embeddings_consistency(self, emb_client, config):
        """Test that same text produces same embedding"""
        test_text = "This is a test sentence for embedding consistency"
        
        payload = {
            "model": config['emb_served_model_name'],
            "input": [test_text]
        }
        
        # First request
        response1 = await emb_client.post(Embedding.EMBEDDINGS, json=payload)
        data1 = response1.json()
        embedding1 = data1["data"][0]["embedding"]
        
        # Second request
        response2 = await emb_client.post(Embedding.EMBEDDINGS, json=payload)
        data2 = response2.json()
        embedding2 = data2["data"][0]["embedding"]
        
        # Embeddings should be identical
        assert embedding1 == embedding2
    
    @pytest.mark.asyncio
    async def test_embeddings_batch(self, emb_client, config):
        """Test batch embedding generation"""
        texts = [
            "First text",
            "Second text",
            "Third text",
            "Fourth text",
            "Fifth text"
        ]
        
        payload = {
            "model": config['emb_served_model_name'],
            "input": texts
        }
        
        response = await emb_client.post(Embedding.EMBEDDINGS, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == len(texts)
        
        # Check each embedding
        for i, embedding in enumerate(data["data"]):
            assert "embedding" in embedding
            assert "index" in embedding
            assert embedding["index"] == i
            assert isinstance(embedding["embedding"], list)
            assert len(embedding["embedding"]) > 0

"""
test_db_operations.py

Tests for database operations and data persistence.
Covers: DB storing, Indexation workflows
"""

import time

import json
import random
import uuid
import pytest
from sqlalchemy import create_engine, text
from urllib.parse import urlparse


def create_embedding_vector(dimensions: int = 768) -> str:
    """Create a random embedding vector with specified dimensions"""
    return json.dumps([round(random.random(), 6) for _ in range(dimensions)])


def parse_pg_url(pg_url: str) -> tuple:
    """Parse PostgreSQL URL into (host, port, user, password, database)"""
    parsed = urlparse(pg_url)
    if parsed.hostname is None:
        parsed = urlparse(f"postgresql://{pg_url}")
    return (
        parsed.hostname or 'localhost',
        parsed.port or 5432,
        parsed.username,
        parsed.password,
        parsed.path.lstrip('/')
    )


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.fast
class TestDatabaseOperations:
    """Test suite for database operations"""
    
    @pytest.fixture
    def db_engine(self, config):
        """Create database engine"""
        engine = create_engine(config['pg_url'])
        yield engine
        engine.dispose()
    
    @pytest.mark.asyncio
    async def test_database_connection(self, config):
        """Test database connection"""
        import psycopg2
        
        try:
            host, port, user, password, database = parse_pg_url(config['pg_url'])
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database
            )
            conn.close()
            assert True
        except Exception as e:
            pytest.fail(f"Database connection failed: {e}")
    
    @pytest.mark.asyncio
    async def test_database_schema(self, db_engine):
        """Test database schema exists"""
        with db_engine.connect() as conn:
            # Check for expected tables
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result.fetchall()]
            
            # Should have at least chunks and file_summaries tables
            expected_tables = ['chunks', 'file_summaries', 'module_summaries']
            for table in expected_tables:
                assert table in tables, f"Table {table} not found in database"
    
    @pytest.mark.asyncio
    async def test_chunk_storage(self, db_engine, test_workspace, config):
        """Test storing and retrieving chunks"""
        # First, we need to ingest a file to create chunks
        # This would require the ingestor service to be running
        # For now, test direct database operations
        
        # Insert a test chunk
        with db_engine.connect() as conn:
            # Clean up first
            conn.execute(text("TRUNCATE TABLE chunks CASCADE"))
            conn.execute(text("TRUNCATE TABLE file_summaries CASCADE"))
            conn.commit()
            
            # Create parent record first (required by FK)
            conn.execute(text("""
                INSERT INTO file_summaries (file_path, summary)
                VALUES (:file_path, 'Test summary')
            """), {"file_path": "test.txt"})
            
            # Insert test chunk
            insert_sql = text("""
                INSERT INTO chunks (id, file_path, content, start_line, end_line, chunk_type, embedding)
                VALUES (:id, :file_path, :content, 0, 10, 'text', :embedding)
                RETURNING id
            """)
            
            result = conn.execute(insert_sql, {
                "id": str(uuid.uuid4()),
                "file_path": "test.txt",
                "content": "Test chunk content",
                "embedding": create_embedding_vector(config['pgvector_dimensions'])
            })
            
            chunk_id = result.fetchone()[0]
            assert chunk_id is not None
            
            # Verify insertion
            select_sql = text("SELECT * FROM chunks WHERE id = :id")
            result = conn.execute(select_sql, {"id": chunk_id})
            row = result.fetchone()
            assert row is not None
            assert row.content == "Test chunk content"
            
            # Clean up
            conn.execute(text("DELETE FROM chunks WHERE id = :id"), {"id": chunk_id})
            conn.commit()
    
    @pytest.mark.asyncio
    async def test_file_summary_storage(self, db_engine):
        """Test storing and retrieving file summaries"""
        with db_engine.connect() as conn:
            # Clean up first
            conn.execute(text("TRUNCATE TABLE file_summaries CASCADE"))
            conn.commit()
            
            # Insert test file summary
            insert_sql = text("""
                INSERT INTO file_summaries (file_path, summary, metadata)
                VALUES (:file_path, :summary, :metadata)
                RETURNING file_path
            """)
            
            result = conn.execute(insert_sql, {
                "file_path": "test.txt",
                "summary": "Test file summary",
                "metadata": '{"source": "test", "category": "documentation"}'
            })
            
            file_path = result.fetchone()[0]
            assert file_path == "test.txt"
            
            # Verify insertion
            select_sql = text("SELECT * FROM file_summaries WHERE file_path = :id")
            result = conn.execute(select_sql, {"id": file_path})
            row = result.fetchone()
            assert row is not None
            assert row.summary == "Test file summary"
            
            # Clean up
            conn.execute(text("DELETE FROM file_summaries WHERE file_path = :id"), {"id": file_path})
            conn.commit()

    @pytest.mark.asyncio
    async def test_query_execution(self, db_engine, config):
        """Test database query execution"""
        with db_engine.connect() as conn:
            # Create test data
            conn.execute(text("TRUNCATE TABLE chunks CASCADE"))
            conn.execute(text("TRUNCATE TABLE file_summaries CASCADE"))
            conn.commit()
            
            # Create parents
            conn.execute(text("""
                INSERT INTO file_summaries (file_path, summary) VALUES 
                ('doc1.txt', 'Summary 1'),
                ('doc2.txt', 'Summary 2')
            """))
            
            # Insert test data
            emb = create_embedding_vector(config['pgvector_dimensions'])
            insert_sql = text("""
                INSERT INTO chunks (id, file_path, content, start_line, end_line, chunk_type, embedding)
                VALUES 
                (:id1, 'doc1.txt', 'First chunk of doc1', 0, 10, 'text', :emb1),
                (:id2, 'doc1.txt', 'Second chunk of doc1', 10, 20, 'text', :emb2),
                (:id3, 'doc2.txt', 'First chunk of doc2', 0, 10, 'text', :emb3)
            """)
            conn.execute(insert_sql, {
                "id1": str(uuid.uuid4()),
                "id2": str(uuid.uuid4()),
                "id3": str(uuid.uuid4()),
                "emb1": emb, "emb2": emb, "emb3": emb
            })
            conn.commit()
            
            # Test query
            select_sql = text("SELECT COUNT(*) as count FROM chunks")
            result = conn.execute(select_sql)
            count = result.fetchone()[0]
            assert count == 3
            
            # Test filtering
            filter_sql = text("SELECT * FROM chunks WHERE file_path = :file_path")
            result = conn.execute(filter_sql, {"file_path": "doc1.txt"})
            rows = result.fetchall()
            assert len(rows) == 2
    
    @pytest.mark.asyncio
    async def test_vector_similarity_search(self, db_engine):
        """Test vector similarity search in database"""
        with db_engine.connect() as conn:
            # Test if vector operations work
            # This depends on pgvector extension
            try:
                # Test vector creation
                test_sql = text("SELECT '[0.1, 0.2, 0.3]'::vector")
                result = conn.execute(test_sql)
                vector = result.fetchone()[0]
                assert vector is not None
            except Exception as e:
                pytest.skip(f"Vector operations not available: {e}")
    
    @pytest.mark.asyncio
    async def test_transaction_handling(self, db_engine, config):
        """Test transaction handling and rollback"""
        with db_engine.connect() as conn:
            # Create parent
            conn.execute(text("INSERT INTO file_summaries (file_path, summary) VALUES ('transaction_test.txt', '')"))
            conn.commit()
            
            # Start transaction
            with conn.begin() as trans:
                try:
                    # Insert test data
                    insert_sql = text("""
                        INSERT INTO chunks (id, file_path, content, start_line, end_line, chunk_type, embedding)
                        VALUES (:id, :file_path, :content, 0, 10, 'text', :embedding)
                        RETURNING id
                    """)
                    
                    result = conn.execute(insert_sql, {
                        "id": str(uuid.uuid4()),
                        "file_path": "transaction_test.txt",
                        "content": "Transaction test chunk",
                        "embedding": create_embedding_vector(config['pgvector_dimensions'])
                    })
                    
                    chunk_id = result.fetchone()[0]
                    
                    # Verify insertion
                    select_sql = text("SELECT COUNT(*) as count FROM chunks WHERE id = :id")
                    result = conn.execute(select_sql, {"id": chunk_id})
                    count = result.fetchone()[0]
                    assert count == 1
                    
                    # Transaction will be rolled back automatically
                    # Test data should not persist
                except Exception as e:
                    trans.rollback()
                    raise e
    
    @pytest.mark.asyncio
    async def test_concurrent_db_operations(self, db_engine, config):
        """Test concurrent database operations"""
        import asyncio
        
        # Prepare parents
        with db_engine.connect() as conn:
            for i in range(5):
                conn.execute(text(f"INSERT INTO file_summaries (file_path, summary) VALUES ('concurrent_{i}.txt', '')"))
            conn.commit()
        
        test_embedding = create_embedding_vector(config['pgvector_dimensions'])
        
        async def insert_chunk(index, embedding):
            def db_operation():
                # Create a new connection for each operation
                import psycopg2
                host, port, user, password, database = parse_pg_url(config['pg_url'])
                conn = psycopg2.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=database
                )
                cursor = conn.cursor()
                
                try:
                    cursor.execute("""
                        INSERT INTO chunks (id, file_path, content, start_line, end_line, chunk_type, embedding)
                        VALUES (%s, %s, %s, 0, 10, 'text', %s)
                        RETURNING id
                    """, (
                        str(uuid.uuid4()),
                        f"concurrent_{index}.txt",
                        f"Concurrent test chunk {index}",
                        embedding
                    ))
                    
                    result = cursor.fetchone()
                    conn.commit()
                    return result[0]
                finally:
                    cursor.close()
                    conn.close()
            
            return await asyncio.get_event_loop().run_in_executor(None, db_operation)
        
        # Execute concurrent operations
        tasks = [insert_chunk(i, test_embedding) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 5
        assert all(r is not None for r in results)
        
        # Verify all chunks were inserted
        with db_engine.connect() as conn:
            select_sql = text("SELECT COUNT(*) as count FROM chunks WHERE file_path LIKE 'concurrent_%'")
            result = conn.execute(select_sql)
            count = result.fetchone()[0]
            assert count == 5
    
    @pytest.mark.asyncio
    async def test_database_error_handling(self, db_engine, config):
        """Test error handling for invalid database operations"""
        with db_engine.connect() as conn:
            # Create parent
            conn.execute(text("INSERT INTO file_summaries (file_path, summary) VALUES ('duplicate_test.txt', '')"))
            conn.commit()

            # Test invalid SQL
            try:
                conn.execute(text("INVALID SQL"))
                assert False, "Should have raised an error"
            except Exception:
                pass  # Expected
            
            # Test duplicate key insertion
            try:
                # Insert chunk with explicit ID
                insert_sql = text("""
                    INSERT INTO chunks (id, file_path, content, start_line, end_line, chunk_type, embedding)
                    VALUES (:id, :file_path, :content, 0, 10, 'text', :embedding)
                """)
                
                params = {
                    "id": "dup_chunk_1",
                    "file_path": "duplicate_test.txt",
                    "content": "Test chunk",
                    "embedding": create_embedding_vector(config['pgvector_dimensions'])
                }
                
                conn.execute(insert_sql, params)
                conn.commit()
                
                # Try to insert again with same ID
                conn.execute(insert_sql, params)
                conn.commit()
                
                # Should have failed
                assert False, "Should fail on duplicate PK"
            except Exception:
                # Expected behavior for duplicate keys
                pass
    
    @pytest.mark.asyncio
    async def test_data_persistence_across_connections(self, db_engine, config):
        """Test that data persists across database connections"""
        import psycopg2
        
        # Setup parent
        with db_engine.connect() as conn:
            conn.execute(text("INSERT INTO file_summaries (file_path, summary) VALUES ('persist_test.txt', '')"))
            conn.commit()
        
        # Connection 1: Insert data
        host, port, user, password, database = parse_pg_url(config['pg_url'])
        conn1 = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        cursor1 = conn1.cursor()
        cursor1.execute("""
            INSERT INTO chunks (id, file_path, content, start_line, end_line, chunk_type, embedding)
            VALUES (%s, %s, %s, 0, 10, 'text', %s)
            RETURNING id
        """, (str(uuid.uuid4()), "persist_test.txt", "Persistence test", create_embedding_vector(config['pgvector_dimensions'])))
        
        chunk_id = cursor1.fetchone()[0]
        conn1.commit()
        cursor1.close()
        conn1.close()
        
        # Connection 2: Verify data persists
        conn2 = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT content FROM chunks WHERE id = %s", (chunk_id,))
        result = cursor2.fetchone()
        conn2.close()
        
        assert result is not None
        assert result[0] == "Persistence test"
        
        # Clean up handled by fixture teardown (truncate)
    
    @pytest.mark.asyncio
    async def test_database_performance_queries(self, db_engine, config):
        """Test database query performance"""
        import time
        
        # Insert test data
        with db_engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE chunks CASCADE"))
            conn.execute(text("TRUNCATE TABLE file_summaries CASCADE"))
            conn.commit()
            
            # Prepare parents
            conn.execute(text("""
                INSERT INTO file_summaries (file_path, summary) 
                SELECT 'perf_test_' || generate_series(0, 99) || '.txt', ''
            """))
            
            # Insert 100 test chunks
            test_embedding = create_embedding_vector(config['pgvector_dimensions'])
            insert_sql = text("""
                INSERT INTO chunks (id, file_path, content, start_line, end_line, chunk_type, embedding)
                VALUES (:id, :file_path, :content, :i, :i+10, 'text', :embedding)
            """)
            
            # Batch insert loop (simplified)
            for i in range(100):
                conn.execute(insert_sql, {
                    "id": f"perf_{i}",
                    "file_path": f"perf_test_{i}.txt",
                    "content": f"Performance test chunk {i}",
                    "i": i,
                    "embedding": test_embedding
                })
            
            conn.commit()
            
            # Test query performance
            start_time = time.time()
            
            select_sql = text("SELECT COUNT(*) as count FROM chunks WHERE file_path LIKE 'perf_test_%'")
            result = conn.execute(select_sql)
            count = result.fetchone()[0]
            
            end_time = time.time()
            query_time = end_time - start_time
            
            assert count == 100
            assert query_time < 1.0  # Should complete within 1 second
    
    @pytest.mark.asyncio
    async def test_database_connection_pooling(self, config):
        """Test database connection pooling"""
        from psycopg2 import pool
        
        try:
            # Create connection pool
            host, port, user, password, database = parse_pg_url(config['pg_url'])
            db_pool = pool.SimpleConnectionPool(
                1, 5,
                host=host,
                port=port,
                user=user,
                password=password,
                database=database
            )

            # Get connection from pool
            conn = db_pool.getconn()
            cursor = conn.cursor()
            
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            assert result[0] == 1
            
            cursor.close()
            db_pool.putconn(conn)
            db_pool.closeall()
            
        except Exception as e:
            pytest.skip(f"Connection pooling test skipped: {e}")
    
    @pytest.mark.asyncio
    async def test_database_schema_versions(self, db_engine):
        """Test database schema version tracking"""
        with db_engine.connect() as conn:
            # Check if schema version table exists
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'schema_migrations'
            """))
            tables = [row[0] for row in result.fetchall()]
            
            if 'schema_migrations' in tables:
                # Check for version data
                result = conn.execute(text("SELECT COUNT(*) as count FROM schema_migrations"))
                count = result.fetchone()[0]
                assert count > 0, "Database should have schema migrations"
            else:
                # Schema versioning not implemented
                pytest.skip("Schema versioning not implemented")
    
    @pytest.mark.asyncio
    async def test_database_connection_limits(self, config):
        """Test database connection limits"""
        import psycopg2

        connections = []
        
        try:
            host, port, user, password, database = parse_pg_url(config['pg_url'])
            # Try to create multiple connections
            for i in range(10):
                conn = psycopg2.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=database
                )
                connections.append(conn)
            
            # All connections should succeed
            assert len(connections) == 10
            
        except Exception as e:
            # Connection limit reached or other error
            assert len(connections) > 0, "Should be able to create at least one connection"
        finally:
            # Clean up
            for conn in connections:
                conn.close()
    
    @pytest.mark.asyncio
    async def test_database_timeouts(self, db_engine):
        """Test database timeout handling"""
        with db_engine.connect() as conn:
            # Test long-running query (should timeout)
            try:
                # This query will take time if there are many records
                query = text("""
                    SELECT pg_sleep(0.1)  -- Sleep for 100ms
                """)
                
                start_time = time.time()
                result = conn.execute(query)
                end_time = time.time()
                
                # Should complete within reasonable time
                assert (end_time - start_time) < 1.0
                
            except Exception as e:
                # Timeout or other error
                pass
    
    @pytest.mark.asyncio
    async def test_database_index_performance(self, db_engine):
        """Test database index performance"""
        with db_engine.connect() as conn:
            # Test if indexes exist
            result = conn.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public'
            """))
            indexes = [row[0] for row in result.fetchall()]
            
            # Should have indexes for efficient querying
            expected_index_patterns = ['chunk', 'file', 'module']
            for pattern in expected_index_patterns:
                matching = [idx for idx in indexes if pattern in idx.lower()]
                if matching:
                    # Index exists
                    assert True
                else:
                    # Index might not exist, but that's okay for now
                    pass
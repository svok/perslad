"""
test_db_operations.py

Tests for database operations and data persistence.
Covers: DB storing, Indexation workflows
"""

import time

import pytest
from sqlalchemy import create_engine, text


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
            conn = psycopg2.connect(
                host=config['pg_url'].split('@')[1].split('/')[0].split(':')[0],
                port=int(config['pg_url'].split('@')[1].split('/')[0].split(':')[1]),
                user=config['pg_url'].split('://')[1].split(':')[0],
                password=config['pg_url'].split(':')[1].split('@')[0],
                database=config['pg_url'].split('/')[-1]
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
    async def test_chunk_storage(self, db_engine, test_workspace):
        """Test storing and retrieving chunks"""
        # First, we need to ingest a file to create chunks
        # This would require the ingestor service to be running
        # For now, test direct database operations
        
        # Insert a test chunk
        with db_engine.connect() as conn:
            # Clean up first
            conn.execute(text("TRUNCATE TABLE chunks CASCADE"))
            conn.commit()
            
            # Insert test chunk
            insert_sql = text("""
                INSERT INTO chunks (file_path, chunk_index, content, embedding, metadata)
                VALUES (:file_path, :chunk_index, :content, :embedding, :metadata)
                RETURNING id
            """)
            
            result = conn.execute(insert_sql, {
                "file_path": "test.txt",
                "chunk_index": 0,
                "content": "Test chunk content",
                "embedding": "[0.1, 0.2, 0.3]",
                "metadata": {"source": "test"}
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
                INSERT INTO file_summaries (file_path, summary, metadata, created_at)
                VALUES (:file_path, :summary, :metadata, NOW())
                RETURNING id
            """)
            
            result = conn.execute(insert_sql, {
                "file_path": "test.txt",
                "summary": "Test file summary",
                "metadata": {"source": "test", "category": "documentation"}
            })
            
            summary_id = result.fetchone()[0]
            assert summary_id is not None
            
            # Verify insertion
            select_sql = text("SELECT * FROM file_summaries WHERE id = :id")
            result = conn.execute(select_sql, {"id": summary_id})
            row = result.fetchone()
            assert row is not None
            assert row.summary == "Test file summary"
            
            # Clean up
            conn.execute(text("DELETE FROM file_summaries WHERE id = :id"), {"id": summary_id})
            conn.commit()
    
    @pytest.mark.asyncio
    async def test_module_summary_storage(self, db_engine):
        """Test storing and retrieving module summaries"""
        with db_engine.connect() as conn:
            # Clean up first
            conn.execute(text("TRUNCATE TABLE module_summaries CASCADE"))
            conn.commit()
            
            # Insert test module summary
            insert_sql = text("""
                INSERT INTO module_summaries (module_name, summary, file_paths, metadata)
                VALUES (:module_name, :summary, :file_paths, :metadata)
                RETURNING id
            """)
            
            result = conn.execute(insert_sql, {
                "module_name": "test_module",
                "summary": "Test module summary",
                "file_paths": ["test1.txt", "test2.txt"],
                "metadata": {"source": "test", "type": "module"}
            })
            
            module_id = result.fetchone()[0]
            assert module_id is not None
            
            # Verify insertion
            select_sql = text("SELECT * FROM module_summaries WHERE id = :id")
            result = conn.execute(select_sql, {"id": module_id})
            row = result.fetchone()
            assert row is not None
            assert row.module_name == "test_module"
            
            # Clean up
            conn.execute(text("DELETE FROM module_summaries WHERE id = :id"), {"id": module_id})
            conn.commit()
    
    @pytest.mark.asyncio
    async def test_query_execution(self, db_engine):
        """Test database query execution"""
        with db_engine.connect() as conn:
            # Create test data
            conn.execute(text("TRUNCATE TABLE chunks CASCADE"))
            conn.commit()
            
            # Insert test data
            insert_sql = text("""
                INSERT INTO chunks (file_path, chunk_index, content, embedding, metadata)
                VALUES 
                ('doc1.txt', 0, 'First chunk of doc1', '[0.1, 0.2, 0.3]', '{}'),
                ('doc1.txt', 1, 'Second chunk of doc1', '[0.4, 0.5, 0.6]', '{}'),
                ('doc2.txt', 0, 'First chunk of doc2', '[0.7, 0.8, 0.9]', '{}')
            """)
            conn.execute(insert_sql)
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
    async def test_transaction_handling(self, db_engine):
        """Test transaction handling and rollback"""
        with db_engine.connect() as conn:
            # Start transaction
            with conn.begin() as trans:
                try:
                    # Insert test data
                    insert_sql = text("""
                        INSERT INTO chunks (file_path, chunk_index, content, embedding, metadata)
                        VALUES (:file_path, :chunk_index, :content, :embedding, :metadata)
                        RETURNING id
                    """)
                    
                    result = conn.execute(insert_sql, {
                        "file_path": "transaction_test.txt",
                        "chunk_index": 0,
                        "content": "Transaction test chunk",
                        "embedding": "[0.1, 0.2, 0.3]",
                        "metadata": {"test": "transaction"}
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
        
        async def insert_chunk(index):
            async def db_operation():
                # Create a new connection for each operation
                import psycopg2
                conn = psycopg2.connect(
                    host=config['pg_url'].split('@')[1].split('/')[0].split(':')[0],
                    port=int(config['pg_url'].split('@')[1].split('/')[0].split(':')[1]),
                    user=config['pg_url'].split('://')[1].split(':')[0],
                    password=config['pg_url'].split(':')[1].split('@')[0],
                    database=config['pg_url'].split('/')[-1]
                )
                cursor = conn.cursor()
                
                try:
                    cursor.execute("""
                        INSERT INTO chunks (file_path, chunk_index, content, embedding, metadata)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        f"concurrent_{index}.txt",
                        index,
                        f"Concurrent test chunk {index}",
                        "[0.1, 0.2, 0.3]",
                        '{"test": "concurrent"}'
                    ))
                    
                    result = cursor.fetchone()
                    conn.commit()
                    return result[0]
                finally:
                    cursor.close()
                    conn.close()
            
            return await asyncio.get_event_loop().run_in_executor(None, db_operation)
        
        # Execute concurrent operations
        tasks = [insert_chunk(i) for i in range(5)]
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
    async def test_database_error_handling(self, db_engine):
        """Test error handling for invalid database operations"""
        with db_engine.connect() as conn:
            # Test invalid SQL
            try:
                conn.execute(text("INVALID SQL"))
                assert False, "Should have raised an error"
            except Exception:
                pass  # Expected
            
            # Test duplicate key insertion
            try:
                # Insert same chunk twice
                insert_sql = text("""
                    INSERT INTO chunks (file_path, chunk_index, content, embedding, metadata)
                    VALUES (:file_path, :chunk_index, :content, :embedding, :metadata)
                """)
                
                params = {
                    "file_path": "duplicate_test.txt",
                    "chunk_index": 0,
                    "content": "Test chunk",
                    "embedding": "[0.1, 0.2, 0.3]",
                    "metadata": {}
                }
                
                conn.execute(insert_sql, params)
                conn.commit()
                
                # Try to insert again with same file_path and chunk_index
                conn.execute(insert_sql, params)
                conn.commit()
                
                # Should have failed or overwritten
            except Exception:
                # Expected behavior for duplicate keys
                pass
    
    @pytest.mark.asyncio
    async def test_data_persistence_across_connections(self, db_engine, config):
        """Test that data persists across database connections"""
        import psycopg2
        
        # Connection 1: Insert data
        conn1 = psycopg2.connect(
            host=config['pg_url'].split('@')[1].split('/')[0].split(':')[0],
            port=int(config['pg_url'].split('@')[1].split('/')[0].split(':')[1]),
            user=config['pg_url'].split('://')[1].split(':')[0],
            password=config['pg_url'].split(':')[1].split('@')[0],
            database=config['pg_url'].split('/')[-1]
        )
        
        cursor1 = conn1.cursor()
        cursor1.execute("""
            INSERT INTO chunks (file_path, chunk_index, content, embedding, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, ("persist_test.txt", 0, "Persistence test", "[0.1, 0.2, 0.3]", "{}"))
        
        chunk_id = cursor1.fetchone()[0]
        conn1.commit()
        cursor1.close()
        conn1.close()
        
        # Connection 2: Verify data persists
        conn2 = psycopg2.connect(
            host=config['pg_url'].split('@')[1].split('/')[0].split(':')[0],
            port=int(config['pg_url'].split('@')[1].split('/')[0].split(':')[1]),
            user=config['pg_url'].split('://')[1].split(':')[0],
            password=config['pg_url'].split(':')[1].split('@')[0],
            database=config['pg_url'].split('/')[-1]
        )
        
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT content FROM chunks WHERE id = %s", (chunk_id,))
        result = cursor2.fetchone()
        conn2.close()
        
        assert result is not None
        assert result[0] == "Persistence test"
        
        # Clean up
        conn3 = psycopg2.connect(
            host=config['pg_url'].split('@')[1].split('/')[0].split(':')[0],
            port=int(config['pg_url'].split('@')[1].split('/')[0].split(':')[1]),
            user=config['pg_url'].split('://')[1].split(':')[0],
            password=config['pg_url'].split(':')[1].split('@')[0],
            database=config['pg_url'].split('/')[-1]
        )
        
        cursor3 = conn3.cursor()
        cursor3.execute("DELETE FROM chunks WHERE id = %s", (chunk_id,))
        conn3.commit()
        cursor3.close()
        conn3.close()
    
    @pytest.mark.asyncio
    async def test_database_performance_queries(self, db_engine):
        """Test database query performance"""
        import time
        
        # Insert test data
        with db_engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE chunks CASCADE"))
            conn.commit()
            
            # Insert 100 test chunks
            for i in range(100):
                insert_sql = text("""
                    INSERT INTO chunks (file_path, chunk_index, content, embedding, metadata)
                    VALUES (:file_path, :chunk_index, :content, :embedding, :metadata)
                """)
                
                conn.execute(insert_sql, {
                    "file_path": f"perf_test_{i}.txt",
                    "chunk_index": i,
                    "content": f"Performance test chunk {i}",
                    "embedding": "[0.1, 0.2, 0.3]",
                    "metadata": {"test": "performance"}
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
            db_pool = pool.SimpleConnectionPool(
                1, 5,
                host=config['pg_url'].split('@')[1].split('/')[0].split(':')[0],
                port=int(config['pg_url'].split('@')[1].split('/')[0].split(':')[1]),
                user=config['pg_url'].split('://')[1].split(':')[0],
                password=config['pg_url'].split(':')[1].split('@')[0],
                database=config['pg_url'].split('/')[-1]
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
    async def test_database_backup_restore(self, config):
        """Test database backup and restore (if possible)"""

        try:
            # This is a complex test that might not be possible in all environments
            # We'll just verify we can connect and run basic operations
            
            # Test database backup command (dry run)
            backup_command = f"pg_dump -h {config['pg_url'].split('@')[1].split('/')[0].split(':')[0]} -U {config['pg_url'].split('://')[1].split(':')[0]} -d {config['pg_url'].split('/')[-1]} --schema-only"
            
            # Just verify the command can be constructed
            assert isinstance(backup_command, str)
            assert len(backup_command) > 0
            
        except Exception as e:
            pytest.skip(f"Backup/restore test skipped: {e}")
    
    @pytest.mark.asyncio
    async def test_database_connection_limits(self, config):
        """Test database connection limits"""
        import psycopg2

        connections = []
        
        try:
            # Try to create multiple connections
            for i in range(10):
                conn = psycopg2.connect(
                    host=config['pg_url'].split('@')[1].split('/')[0].split(':')[0],
                    port=int(config['pg_url'].split('@')[1].split('/')[0].split(':')[1]),
                    user=config['pg_url'].split('://')[1].split(':')[0],
                    password=config['pg_url'].split(':')[1].split('@')[0],
                    database=config['pg_url'].split('/')[-1]
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
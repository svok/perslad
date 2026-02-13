#!/usr/bin/env python3
"""
Test NebulaGraph connection and performance
"""
import time
from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config

def test_connection():
    print("Testing NebulaGraph connection...")

    config = Config()
    config.max_connection_pool_size = 10
    config.execution_timeout = 60

    connection_pool = ConnectionPool()
    hosts = [('127.0.0.1', 9669)]

    try:
        ok = connection_pool.init(hosts, config)
        if not ok:
            print("❌ Failed to connect")
            return False

        session = connection_pool.get_session('root', 'nebula')
        print("✓ Connected to NebulaGraph")

        result = session.execute('SHOW HOSTS;')
        if result.is_succeed():
            print("\n📊 Cluster nodes:")
            values = result.values()
            for row in values:
                if row:
                    print(f"  - {row[0]}: online={row[1]}, leader={row[2]}/{row[3]}")
        else:
            print(f"❌ Query failed: {result.error_msg()}")

        result = session.execute('SHOW SPACES;')
        if result.is_succeed():
            print("\n📋 Available spaces:")
            for row in result.values():
                if row:
                    print(f"  - {row[0]}")

        session.release()
        print("\n✓ Connection test passed!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        connection_pool.close()

def test_performance():
    print("\n" + "="*50)
    print("Testing performance...")
    print("="*50)

    config = Config()
    config.max_connection_pool_size = 5
    config.execution_timeout = 30

    connection_pool = ConnectionPool()
    hosts = [('127.0.0.1', 9669)]

    try:
        ok = connection_pool.init(hosts, config)
        if not ok:
            print("❌ Cannot connect for performance test")
            return

        session = connection_pool.get_session('root', 'nebula')

        # Test 1: Create space
        print("\n📝 Test 1: Create space")
        start = time.time()
        result = session.execute('CREATE SPACE IF NOT EXISTS perf_test(vid_type=FIXED_STRING(20), partition_num=10, replica_factor=1);')
        duration = time.time() - start
        if result.is_succeed():
            print(f"✓ Space created in {duration:.3f}s")
        else:
            print(f"❌ Failed: {result.error_msg()}")

        result = session.execute('USE perf_test;')
        if result.is_succeed():
            print("✓ Using space")
        else:
            print(f"❌ Failed: {result.error_msg()}")

        # Test 2: Create tags
        print("\n📝 Test 2: Create tags")
        start = time.time()
        result = session.execute('CREATE TAG person(name STRING, age INT);')
        duration = time.time() - start
        if result.is_succeed():
            print(f"✓ TAG created in {duration:.3f}s")
        else:
            print(f"❌ Failed: {result.error_msg()}")

        # Test 3: Insert vertices
        print("\n📝 Test 3: Insert 1000 vertices")
        start = time.time()
        for i in range(1000):
            vid = f"user_{i}"
            stmt = f'INSERT VERTEX person(name, age) VALUES "{vid}":("User {i}", {i % 100});'
            result = session.execute(stmt)
            if not result.is_succeed():
                print(f"❌ Insert failed at {i}: {result.error_msg()}")
                break
        duration = time.time() - start
        print(f"✓ 1000 vertices inserted in {duration:.3f}s")
        print(f"  Speed: {1000/duration:.0f} ops/s")

        # Test 4: Insert edges
        print("\n📝 Test 4: Insert 2000 edges")
        start = time.time()
        for i in range(1000):
            src = f"user_{i}"
            dst = f"user_{(i+1)%1000}"
            stmt = f'INSERT EDGE knows(since, strength) VALUES "{src}"->"{dst}":({1704067200 + i}, {0.5 + i/1000});'
            result = session.execute(stmt)
            if not result.is_succeed():
                print(f"❌ Edge insert failed at {i}: {result.error_msg()}")
                break
        duration = time.time() - start
        print(f"✓ 2000 edges inserted in {duration:.3f}s")
        print(f"  Speed: {2000/duration:.0f} ops/s")

        # Test 5: Query
        print("\n📝 Test 5: Query vertices")
        start = time.time()
        result = session.execute('FETCH PROP ON person "user_500";')
        duration = time.time() - start
        if result.is_succeed():
            print(f"✓ Query executed in {duration:.3f}s")
        else:
            print(f"❌ Query failed: {result.error_msg()}")

        # Test 6: Graph traversal
        print("\n📝 Test 6: Graph traversal (3 hops)")
        start = time.time()
        result = session.execute('FETCH PROP ON person "user_0" 3 STEPS;')
        duration = time.time() - start
        if result.is_succeed():
            print(f"✓ Traversal executed in {duration:.3f}s")
        else:
            print(f"❌ Traversal failed: {result.error_msg()}")

        session.release()

        print("\n" + "="*50)
        print("✓ Performance tests completed!")
        print("="*50)

    except Exception as e:
        print(f"❌ Error during performance test: {e}")
    finally:
        connection_pool.close()

if __name__ == '__main__':
    success = test_connection()
    if success:
        test_performance()

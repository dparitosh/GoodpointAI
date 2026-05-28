#!/usr/bin/env python3
"""
PostgreSQL Connection Diagnostics Script

Tests PostgreSQL connectivity and provides troubleshooting information.
Useful for debugging "Connection refused" and other database errors.
"""

import os
import sys
from pathlib import Path

def test_postgres_connection():
    """Test PostgreSQL connectivity with detailed diagnostics."""
    
    print("=" * 80)
    print("PostgreSQL Connection Diagnostics")
    print("=" * 80)
    
    # Import after path is set
    sys.path.insert(0, str(Path(__file__).parent / "agentic-restored" / "python_backend"))
    
    from core.external_config import database_config
    from core.db_session import DATABASE_URL
    
    # Show configuration
    print("\n1. ENVIRONMENT CONFIGURATION")
    print("-" * 80)
    
    print(f"DATABASE_URL env var:  {os.getenv('DATABASE_URL', 'NOT SET')}")
    print(f"POSTGRES_HOST:         {database_config.postgres_host}")
    print(f"POSTGRES_PORT:         {database_config.postgres_port}")
    print(f"POSTGRES_DATABASE:     {database_config.postgres_database}")
    print(f"POSTGRES_USER:         {database_config.postgres_user}")
    print(f"POSTGRES_PASSWORD:     {'*' * len(database_config.postgres_password) if database_config.postgres_password else 'NOT SET'}")
    
    print(f"\nBuilt CONNECTION STRING: {DATABASE_URL}")
    
    # Try connection
    print("\n2. CONNECTION TEST")
    print("-" * 80)
    
    try:
        import psycopg
        print(f"psycopg version: {psycopg.__version__}")
        
        # Parse connection string
        from urllib.parse import urlparse
        parsed = urlparse(DATABASE_URL)
        
        print(f"\nParsed URL:")
        print(f"  Scheme: {parsed.scheme}")
        print(f"  Host: {parsed.hostname}")
        print(f"  Port: {parsed.port}")
        print(f"  Database: {parsed.path.lstrip('/')}")
        print(f"  User: {parsed.username}")
        
        # Try to connect
        print(f"\nConnecting to {parsed.hostname}:{parsed.port}...")
        
        conn = psycopg.connect(DATABASE_URL, timeout=5)
        print("✓ Connection successful!")
        
        # Get server info
        server_version = conn.info.server_version
        print(f"✓ PostgreSQL version: {server_version}")
        
        # Test query
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS test")
            result = cur.fetchone()
            print(f"✓ Test query executed: {result}")
        
        conn.close()
        print("\n✓ All checks passed!")
        return True
        
    except ImportError as e:
        print(f"✗ Error: psycopg not installed: {e}")
        print("Install with: pip install psycopg[binary]")
        return False
        
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print(f"✗ Error type: {type(e).__name__}")
        
        # Provide troubleshooting hints
        print("\n3. TROUBLESHOOTING HINTS")
        print("-" * 80)
        
        error_str = str(e).lower()
        
        if "connection refused" in error_str:
            print("⚠ Connection Refused:")
            print("  - PostgreSQL may not be running")
            print("  - Check if PostgreSQL is listening on the configured port")
            print("  - Verify: netstat -tuln | grep :5432")
            print(f"  - Try: psql -h {database_config.postgres_host} -p {database_config.postgres_port}")
            
        elif "could not translate host name" in error_str:
            print("⚠ Host Name Resolution Failed:")
            print(f"  - Cannot resolve hostname: {database_config.postgres_host}")
            print("  - Check DNS configuration")
            print("  - Try: ping " + (database_config.postgres_host or "localhost"))
            print("  - Try: nslookup " + (database_config.postgres_host or "localhost"))
            
        elif "password authentication failed" in error_str:
            print("⚠ Authentication Failed:")
            print("  - Wrong username or password")
            print("  - Check POSTGRES_USER and POSTGRES_PASSWORD")
            print("  - Try manually with psql to verify credentials")
            
        elif "database" in error_str and "does not exist" in error_str:
            print("⚠ Database Not Found:")
            print(f"  - Database '{database_config.postgres_database}' does not exist")
            print("  - Create it with:")
            print(f"    psql -U {database_config.postgres_user} -h {database_config.postgres_host} -p {database_config.postgres_port}")
            print(f"    CREATE DATABASE {database_config.postgres_database};")
            
        elif "timeout" in error_str:
            print("⚠ Connection Timeout:")
            print("  - PostgreSQL server not responding in time")
            print("  - Check network connectivity")
            print("  - Check firewall rules")
            print("  - Verify server is running")
            
        else:
            print(f"⚠ Connection Error: {error_str}")
            print("  - Check PostgreSQL logs for more details")
            print("  - Verify all connection parameters are correct")
        
        return False


def main():
    """Main entry point."""
    try:
        success = test_postgres_connection()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

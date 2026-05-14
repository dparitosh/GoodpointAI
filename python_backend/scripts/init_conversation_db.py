"""
Initialize Conversation Database Tables

Standalone script to create conversation persistence tables.
Run once during deployment or when manually initializing the database.

Usage:
    python -m scripts.init_conversation_db
    
With .env loading:
    GRAPH_TRACE_LOAD_DOTENV=true python -m scripts.init_conversation_db
"""

import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_conversation_tables():
    """Initialize conversation database tables"""
    try:
        logger.info("=" * 80)
        logger.info("INITIALIZING CONVERSATION DATABASE TABLES")
        logger.info("=" * 80)
        
        # Import database components
        from core.db_session import engine, Base, init_db
        from models.conversation_models import ConversationORM
        
        logger.info("✓ Imported database components")
        logger.info(f"  - Engine: {engine}")
        logger.info(f"  - Base: {Base}")
        logger.info(f"  - ConversationORM: {ConversationORM}")
        
        # Initialize database (creates all tables including conversation)
        logger.info("\nCalling init_db() to create tables...")
        init_db()
        logger.info("✓ Database tables created successfully")
        
        # Verify conversation table exists
        logger.info("\nVerifying 'conversations' table exists...")
        result = engine.execute(
            "SELECT EXISTS(SELECT FROM information_schema.tables WHERE table_name='conversations')"
        )
        table_exists = result.fetchone()[0]
        
        if table_exists:
            logger.info("✓ 'conversations' table verified in database")
            
            # Get table info
            result = engine.execute("SELECT COUNT(*) FROM conversations")
            record_count = result.fetchone()[0]
            logger.info(f"  - Current record count: {record_count}")
            
        else:
            logger.error("✗ 'conversations' table not found!")
            return False
        
        logger.info("\n" + "=" * 80)
        logger.info("INITIALIZATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info("\nConversation persistence is now ready.")
        logger.info("The chat endpoint will automatically save and load conversation history.")
        
        return True
        
    except Exception as e:
        logger.error(f"\n✗ ERROR during initialization: {str(e)}", exc_info=True)
        logger.error("Failed to initialize conversation tables")
        return False


if __name__ == "__main__":
    success = init_conversation_tables()
    exit(0 if success else 1)

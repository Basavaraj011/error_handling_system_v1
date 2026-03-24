"""
Chatbot - Bot Engine with Query Execution
"""
from config.settings import PROJECT_DB_CONFIG    
from connections.ai_connections import AIClient
from src.plugins.chatbot.query_executor import QueryExecutor
from connections.database_connections import DatabaseManager
from config.settings import DATABASE_URL
import logging

logger = logging.getLogger(__name__)


class ChatBot:
    """Interactive chatbot for error resolution and SQL query execution"""
    
    def __init__(self):
        self.ai_client = AIClient()
        self.db_manager = DatabaseManager(DATABASE_URL)
        self.db = self.db_manager.get_session()
        
        # Initialize query executor for SQL queries
        services = {
            "db": self.db,
            "ai": self.ai_client
        }
        self.query_executor = QueryExecutor(services, PROJECT_DB_CONFIG)
        self.conversation_history = []
    
    def process_message(self, user_message: str) -> dict:
        """
        Process user message and generate response.
        
        1. Try to execute as SQL query (mapped intent or AI-generated)
        2. If it's not a query, return generic AI response
        
        Args:
            user_message: User's input text
            
        Returns:
            Dict with response (card format or text)
        """
        self.conversation_history.append({"role": "user", "content": user_message})
        
        # Try to execute as a query (mapped intent or AI-generated SQL)
        try:
            card_response = self.query_executor.execute_user_query(user_message)
            
            logger.info(f"Query executed: {user_message[:50]}...")
            self.conversation_history.append({"role": "assistant", "content": str(card_response)})
            
            return card_response
        
        except Exception as e:
            logger.warning(f"Query execution failed: {e}. Falling back to AI response.")
        
        # Fallback: Generate generic AI response for non-query messages
        response = self.ai_client.generate_text(user_message)
        
        if response:
            self.conversation_history.append({"role": "assistant", "content": response})
        
        logger.info(f"AI response generated: {user_message[:50]}...")
        return {"type": "text", "content": response}
    
    def get_conversation_history(self) -> list:
        """Get conversation history"""
        return self.conversation_history
    
    def reset_conversation(self) -> None:
        """Reset conversation history"""
        self.conversation_history = []
        logger.info("Conversation reset")
    
    def close(self):
        """Cleanup resources"""
        self.db.close()
        self.db_manager.close()
        logger.info("ChatBot resources closed")
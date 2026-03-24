from connections.database_connections import DatabaseManager
from config.settings import DATABASE_URL
from database.database_operations import fetch_errors_from_db, update_processed_errors

"""
Vector embedding and storage for error logs using Chroma DB
"""
import os
import logging
from typing import List, Dict, Any, Optional
import chromadb
from sqlalchemy import text
from sentence_transformers import SentenceTransformer
from connections.ai_connections import AIClient
 

logger = logging.getLogger(__name__)


class ErrorEmbeddingManager:
    """Manages error embeddings and storage in Chroma DB"""
    
    def __init__(self, chroma_db_path: str = "./vector_store", collection_name: str = "error_logs"):
        """
        Initialize the embedding manager
        Args:
            chroma_db_path: Local path for Chroma DB persistence
            collection_name: Name of the Chroma collection
        """

        self.chroma_db_path = chroma_db_path
        self.collection_name = collection_name
        self.ai_client = AIClient()
        self.db_engine = DatabaseManager(DATABASE_URL)
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")  # Example embedding model
        
        
        # Initialize Chroma client
        self._initialize_chroma()
        self.collection = None

        
    def _initialize_chroma(self):
        """Initialize Chroma DB with persistent storage"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(self.chroma_db_path, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(
                path=self.chroma_db_path
            )

            logger.info(f"Chroma DB initialized at {self.chroma_db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize Chroma DB: {e}")
            raise
    
    def _get_or_create_collection(self):
        """Get or create Chroma collection"""
        try:
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Collection '{self.collection_name}' ready")
            return self.collection
        except Exception as e:
            logger.error(f"Failed to get/create collection: {e}")
            raise
    

    
    def embed_errors(self, errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """ Create embeddings for error messages
        Args:
            errors: List of error records
        Returns:
            List of errors with embeddings
        """
        embedded_errors = []
        
        for error in errors:
            try:
                # Use error message for embedding
                text_to_embed = (
                    f"Error Message: {error['error_message']}\n"
                    f"Stack Trace: {error['cleaned_stack_trace']}\n"
                    f"Project ID: {error['project_id']}\n"
                    f"Repo Name: {error['repo_name']}\n"
                       
                )
                error_id = error.get('error_id')
                if not text_to_embed:
                    logger.warning(f"No text to embed for error {error_id}")
                    continue
                # Get embedding using Claude's embedding API
                # Note: For production, consider using a dedicated embedding model
                embedding = self.get_embedding(text_to_embed)
                if embedding:
                    embedded_errors.append({
                        'error_id': error_id,
                        'embedding': embedding})
                    logger.debug(f"Embedded error {error_id}")
                else:
                    logger.warning(f"Failed to create embedding for error {error_id}")
            
            except Exception as e:
                logger.error(f"Error processing error {error.get('error_id')}: {e}")
                continue
        
        logger.info(f"Successfully embedded {len(embedded_errors)} out of {len(errors)} errors")
        return embedded_errors
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """ Get embedding vector for text using OpenAI or Chroma's built-in embedding
        Args:
            text: Text to embed
        Returns:
            Embedding vector or None if failed """
        try:
            embedding = self.embedding_model.encode(text).tolist()
            return embedding
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return None
    
    def store_embeddings_in_chroma(self, embedded_errors: List[Dict[str, Any]]) -> bool:
        """
        Store error embeddings in Chroma DB
        Args:
            embedded_errors: List of errors with embeddings
        Returns:
            Success status
        """
        try:
            if not self.collection:
                self._get_or_create_collection()
            
            # Prepare data for Chroma
            ids = []
            documents = []
            metadatas = []
            embeddings = []
            
            for error in embedded_errors:
                error_id = str(error.get('error_id'))
                ids.append(error_id)
                # Use clean error message as the document
                doc_text = error.get('error_message')
                documents.append(doc_text)
                embeddings.append(error['embedding'])
                # Store metadata
                metadata = {
                    'error_id': error_id
                }
                metadatas.append(metadata)
            
            # Add to Chroma collection
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings
            )
            
            logger.info(f"Stored {len(ids)} error embeddings in Chroma DB")
            return True
        
        except Exception as e:
            logger.error(f"Failed to store embeddings in Chroma: {e}")
            return False
    
    def delete_collection(self) -> bool:
        """Delete the Chroma collection"""
        try:
            self.chroma_client.delete_collection(name=self.collection_name)
            self.collection = None
            logger.info(f"Deleted collection '{self.collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the Chroma collection"""
        try:
            if not self.collection:
                self._get_or_create_collection()
            
            count = self.collection.count()
            return {
                'collection_name': self.collection_name,
                'total_documents': count,
                'status': 'active'
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}


def embed_errors_workflow(errors, severity_filter: str = None) -> bool:
    """
    Complete workflow to fetch errors and embed them in Chroma DB
    Args:
        limit: Maximum number of errors to fetch
        severity_filter: Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)
    Returns:
        Success status
    """
    try:
        print("\n=== Error Embedding Workflow ===\n")
        
        # Initialize manager
        manager = ErrorEmbeddingManager()
        # Embed errors
        print("\nEmbedding errors...")
        embedded_errors = manager.embed_errors(errors)

        if not embedded_errors:
            print("Failed to embed errors")
            return False
        
        print(f"✓ Embedded {len(embedded_errors)} errors")
        
        return embedded_errors
    
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        print(f"✗ Error: {e}")
        return False
    
def store_embeddings_workflow(embedded_errors) -> bool:
    """
    Workflow to store embedded errors in Chroma DB
    Args:
        embedded_errors: List of errors with embeddings
    Returns:
        Success status
    """
    try:
        print("\n=== Storing Embeddings in Chroma DB ===\n")
        
        manager = ErrorEmbeddingManager()
        success = manager.store_embeddings_in_chroma(embedded_errors)
        
        if success:
            print("✓ Successfully stored embeddings in Chroma DB")
            return True
        else:
            print("✗ Failed to store embeddings in Chroma DB")
            return False
    
    except Exception as e:
        logger.error(f"Failed to store embeddings: {e}")
        print(f"✗ Error: {e}")
        return False
    
if __name__ == "__main__":
    import chromadb
    client = chromadb.PersistentClient(path="./vector_store")
    collections = client.list_collections()
    print("Existing collections:", collections)
    collection = client.get_collection(name="error_logs")
    result = collection.get(ids=["21"])
    print("Retrieved document for test_id:", result)
    print("Id count:", len(result['ids']))
    print("Collection stats:", collection.count())
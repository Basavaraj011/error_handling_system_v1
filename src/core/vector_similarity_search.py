import sys
import os
import logging
from typing import List, Dict, Any
import yaml
from database.database_operations import update_processed_errors, fetch_errors_from_db
from src.core.vector_embedding import ErrorEmbeddingManager, embed_errors_workflow

class ErrorSearch:
    """Handles searching for similar errors using semantic similarity"""
    def __init__(self, collection):
        self.collection = collection
        self.logger = logging.getLogger(__name__)


    def search_similar_errors(self, embedded_errors: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar errors using semantic similarity
        Args:
            query_text: Error message or query text to search
            top_k: Number of top results to return
        Returns:
            List of similar errors with similarity scores
        """
        try:
            similar_error_id = []
            for errors in embedded_errors:
                error_id = errors['error_id']
                embedding = errors['embedding']
                results = self.collection.query(
                query_embeddings = [embedding],
                n_results=top_k
                )
                #embedded_error = embedded_errors[i]['embedding']            
                if results and results['ids'] and len(results['ids']) > 0:
                    similar_error = {
                            'query_error_id': error_id,
                            'similar_error_id': results['ids'][0][0],
                            'distance': results['distances'][0][0]
                        }    
                
                # Threshold for similarity
                if similar_error['distance'] < 0.25: 
                    similar_error_id.append( {
                        "similar_id": similar_error['similar_error_id'],
                        "query_error_id": similar_error['query_error_id']
                    })
            print(f"Similar error IDs within threshold: {similar_error_id}")
            return similar_error_id
        except Exception as e:
            self.logger.error(f"Failed to search similar errors: {e}")
            return []
        
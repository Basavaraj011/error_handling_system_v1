
from email import errors
from database.database_operations import fetch_errors_from_db, get_solution_data_from_db
from src.core.vector_similarity_search import ErrorSearch
from src.core.vector_embedding import ErrorEmbeddingManager, embed_errors_workflow
from connections.database_connections import DatabaseManager
from config.settings import DATABASE_URL
    

def search_similar_solutions(errors, db_manager):
    """Search for similar solutions based on embedded errors"""
    try:
        manager = ErrorEmbeddingManager()
        if errors:
            print("\n2. Performing similarity search...")
            # Step 2: Search for similar errors
        embedded_errors = embed_errors_workflow(errors, severity_filter=None)
        if embedded_errors:
            # Step 2: Search for similar errors
            if not manager.collection:
                print("Creating Chroma collection...")
                manager._get_or_create_collection()
            error_search = ErrorSearch(manager.collection)   
            similar_error_id = error_search.search_similar_errors(embedded_errors, top_k=3)
            print(f"Similar error IDs: {similar_error_id}")
            solution = get_solution_data_from_db(similar_error_id, db_manager)
            return solution
    except Exception as e:
        print(f"Error during similarity search: {e}")
        return None
    

if __name__ == "__main__":
    print("Running search for similar solutions...")
    db_manager = DatabaseManager(DATABASE_URL)
    print("Fetching errors from database...")
    errors = fetch_errors_from_db(limit=None, severity_filter=None, db_manager=db_manager)
    print(f"Fetched {len(errors)} errors from database.")
    solution = search_similar_solutions(errors, db_manager)
    print("Similar solution found:", solution)
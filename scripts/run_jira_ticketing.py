"""
Run JIRA Ticketing - Execute only the JIRA ticketing feature
"""

import logging


from database.database_operations import fetch_errors_from_db, update_processed_errors, fetch_jira_deets_from_db,upsert_rootcause_data
from src.core.vector_embedding import ErrorEmbeddingManager, embed_errors_workflow, store_embeddings_workflow
from src.core.vector_similarity_search import ErrorSearch
from connections.database_connections import DatabaseManager
from src.plugins.jira_ticketing.ticket_creator import jira_ticket
from config.settings import DATABASE_URL
from src.plugins.jira_ticketing.rca import RCAAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_jira_ticketing():
        """Main entry point for JIRA ticketing"""
        logger.info("=" * 60)
        logger.info("Starting JIRA Ticketing Workflow")
        logger.info("=" * 60)
        try:
            db_manager = DatabaseManager(DATABASE_URL)
            manager = ErrorEmbeddingManager()
            rca_analyzer = RCAAnalyzer()
            

            errors = fetch_errors_from_db(limit=None, severity_filter=None, db_manager=db_manager)
            
            logger.info(f"ERRORS : {errors}")

            embedded_errors = embed_errors_workflow(errors, severity_filter=None)
            
            if embedded_errors:
                logger.info("\n2. Performing similarity search...")
                # Step 2: Search for similar errors
                if not manager.collection:
                    manager._get_or_create_collection()
                
                error_search = ErrorSearch(manager.collection)   
                similar_error_id = error_search.search_similar_errors(embedded_errors, top_k=1)
                
                new_ids = [error['error_id'] 
                           for error in errors if error['error_id'] 
                           not in [similar['query_error_id'] 
                                   for similar in similar_error_id]]
                                
                if similar_error_id:
                    for id in similar_error_id:
                        logger.info(f"Similar error found with ID: {id}")
                        jira_ticket_details, rca = fetch_jira_deets_from_db(id ,db_manager=db_manager)
                        print(f"Jira ticket details fetched from DB")
                        ticket_res = jira_ticket(jira_ticket_details, rca, db_manager=db_manager)
                        if ticket_res:
                            pass
                        else:
                            return False
                        upsert_rootcause_data(jira_ticket_details, rca=rca, is_ai=False,  db_manager=db_manager)
                if new_ids:
                    for newid in new_ids:
                        logger.info(f"No similar error found for ID: {newid}. Starting AI-assisted ticket creation.")
                        error_data = next((error for error in errors if error['error_id'] == newid), None)
                        if error_data:
                            analyze_error_rca = rca_analyzer.generate_rca(error_data, system_context="")
                            if analyze_error_rca:
                                
                                ticket_res = jira_ticket(error_data, analyze_error_rca, db_manager=db_manager)
                                if ticket_res:
                                    upsert_rootcause_data(error_data, rca=analyze_error_rca, is_ai=True,  db_manager=db_manager)
                                else:
                                    return False
                            else:
                                return False
                        else:
                            logger.warning(f"No error data found for ID: {newid} during RCA analysis")
                store_embeddings_workflow(embedded_errors)
                # update_processed_errors(db_manager)
            db_manager.close()

            
        except Exception as e:
            logger.error(f"JIRA ticketing failed: {e}")
            return False
        

if __name__ == "__main__":
    run_jira_ticketing()

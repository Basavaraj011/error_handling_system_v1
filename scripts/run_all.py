"""
Run All - Execute all enabled features
"""
import os
import sys
from pathlib import Path
import logging
import yaml
import boto3


workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)
    
from scripts.run_jira_ticketing import run_jira_ticketing
from scripts.run_error_extractor import start_error_extractor
from src.runtime.runner import RuntimeRunner
from database.database_operations import update_processed_errors
from connections.database_connections import DatabaseManager
from config.settings import DATABASE_URL
from scripts.Arun_Error_Extractor import process_s3_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_enabled_teams():
    """Scan all team YAML files and return list of enabled teams"""
    projects_dir = os.path.join(os.path.dirname(__file__), '..', 'config', 'projects')
    enabled_teams = []
    
    try:
        for yaml_file in Path(projects_dir).glob('*.yaml'):
            if yaml_file.stem == 'template':  # Skip template file
                continue
                
            try:
                with open(yaml_file, 'r') as f:
                    config = yaml.safe_load(f)
                    if config.get('project', {}).get('enabled', False):
                        team_name = yaml_file.stem  # Get filename without extension
                        enabled_teams.append(team_name)
                        logger.info(f"Enabled team found: {team_name}")
            except Exception as e:
                logger.error(f"Error reading {yaml_file}: {e}")
                
    except Exception as e:
        logger.error(f"Error scanning projects directory: {e}")
    
    return enabled_teams

def read_latest_s3_file(bucket_name = 'error-log-bucket-arun1', prefix="incoming/"):
 
    s3 = boto3.client('s3')
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    objects = response.get('Contents', [])
    if not objects:
        raise ValueError(f"No files found in s3://{bucket_name}/{prefix}")
 
    objects.sort(key=lambda obj: obj['LastModified'], reverse=True)
 
 
    latest_key = objects[0]['Key']
    print(f"[INFO] Latest file detected: {latest_key}")
 
    file_obj = s3.get_object(Bucket=bucket_name, Key=latest_key)
    file_data = file_obj['Body'].read().decode('utf-8')  # returns string
    print("[DEBUG] File content preview (first 200 chars):")
    print(file_data[:200])
    return file_data


def main():
    print(f"Starting Error Handling System - Run All")
    """Main entry point"""
    runner = RuntimeRunner("config")
    
    logger.info("=" * 60)
    logger.info("Scanning for enabled teams...")
    logger.info("=" * 60)
    
    enabled_teams = get_enabled_teams()
    db_manager = DatabaseManager(DATABASE_URL)
    
    if not enabled_teams:
        logger.warning("No teams are enabled. Set 'enabled: true' in team YAML files.")
        return
    
    logger.info("\n" + "=" * 60)
    
    # Run JIRA ticketing for each enabled team
    for team_name in enabled_teams:
        print(f"\n{'='*60}")
        logger.info(f"Starting workflows for: {team_name}")
        logger.info("=" * 60)
        print(f"\n1. Starting error extractor for {team_name}...")
        
        error_file=read_latest_s3_file (bucket_name="error-log-bucket-arun1", prefix="incoming/")

        process_s3_file(content=error_file)
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting JIRA Ticketing for: {team_name}")
        logger.info("=" * 60)
        if runner.is_feature_enabled(team_name, "jira_ticketing"):
            run_jira_ticketing()
        else:
            logger.info(f"JIRA ticketing disabled for: {team_name}")
        update_processed_errors(db_manager)

if __name__ == "__main__":
    main()
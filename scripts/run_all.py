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


# -------------------------------------------------------------
# 1. GET ENABLED TEAMS
# -------------------------------------------------------------
def get_enabled_teams():
    """Scan all team YAML files and return list of enabled teams"""
    projects_dir = os.path.join(os.path.dirname(__file__), '..', 'config', 'projects')
    enabled_teams = []

    try:
        for yaml_file in Path(projects_dir).glob('*.yaml'):
            if yaml_file.stem == 'template':
                continue

            try:
                with open(yaml_file, 'r') as f:
                    config = yaml.safe_load(f)
                    if config.get('project', {}).get('enabled', False):
                        enabled_teams.append(yaml_file.stem)
                        logger.info(f"Enabled team found: {yaml_file.stem}")
            except Exception as e:
                logger.error(f"Error reading {yaml_file}: {e}")

    except Exception as e:
        logger.error(f"Error scanning projects directory: {e}")

    return enabled_teams


# -------------------------------------------------------------
# 2. READ FILES FROM S3 (SAFE — SKIPS FOLDERS)
# -------------------------------------------------------------
def read_all_s3_files(bucket_name='error-log-bucket-arun1', prefix="incoming/"):
    s3 = boto3.client('s3')
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    objects = response.get('Contents', [])

    if not objects:
        raise ValueError(f"No files found in s3://{bucket_name}/{prefix}")

    objects.sort(key=lambda obj: obj['LastModified'], reverse=True)

    all_files = []

    for obj in objects:
        key = obj['Key']

        # 🚫 IMPORTANT FIX: Skip folder placeholders
        if key.endswith("/"):
            print(f"[INFO] Skipping folder key: {key}")
            continue

        print(f"[INFO] Found file: {key}")
        file_obj = s3.get_object(Bucket=bucket_name, Key=key)
        file_data = file_obj['Body'].read().decode('utf-8')
        all_files.append((key, file_data))

    return all_files


# -------------------------------------------------------------
# 3. ARCHIVE FILE TO archive/ (SAFE — DOES NOT DELETE FOLDER)
# -------------------------------------------------------------
def archive_file(bucket_name, source_key, archive_prefix="archive/"):
    s3 = boto3.client('s3')

    # 🚫 Prevent deleting the folder "incoming/"
    if source_key.endswith("/"):
        print(f"[INFO] Skipping folder, not deleting: {source_key}")
        return

    dest_key = archive_prefix + source_key.split("/")[-1]
    print(f"[INFO] Archiving {source_key} --> {dest_key}")

    s3.copy_object(
        Bucket=bucket_name,
        CopySource={'Bucket': bucket_name, 'Key': source_key},
        Key=dest_key
    )
    s3.delete_object(Bucket=bucket_name, Key=source_key)


# -------------------------------------------------------------
# 4. MAIN WORKFLOW
# -------------------------------------------------------------
def main():
    print("Starting Error Handling System - Run All")
    runner = RuntimeRunner("config")
    logger.info("=" * 60)
    logger.info("Scanning for enabled teams...")
    logger.info("=" * 60)

    enabled_teams = get_enabled_teams()
    db_manager = DatabaseManager(DATABASE_URL)

    if not enabled_teams:
        logger.warning("No teams are enabled. Set 'enabled: true' in YAML files.")
        return

    print("\n" + "=" * 60)

    # ---------------------------------------------------------
    # Execute workflow per team
    # ---------------------------------------------------------
    for team_name in enabled_teams:

        print(f"\n{'='*60}")
        logger.info(f"Starting workflows for: {team_name}")
        print(f"\n1. Starting error extractor for {team_name}...")

        # Read files from S3
        error_files = read_all_s3_files(bucket_name="error-log-bucket-arun1", prefix="incoming/")

        for key, error_file in error_files:

            # 🛡 Extra safety (skip folder objects)
            if key.endswith("/"):
                print(f"[INFO] Skipping folder entry in main loop: {key}")
                continue

            print(f"[INFO] Processing file: {key}")
            process_s3_file(content=error_file)

            archive_file("error-log-bucket-arun1", key)
            print(f"[INFO] Archived: {key}")

        logger.info(f"\n{'='*60}")
        logger.info(f"Starting JIRA Ticketing for: {team_name}")

        if runner.is_feature_enabled(team_name, "jira_ticketing"):
            run_jira_ticketing()
        else:
            logger.info(f"JIRA ticketing disabled for: {team_name}")

        update_processed_errors(db_manager)


# -------------------------------------------------------------
# RUN SCRIPT
# -------------------------------------------------------------
if __name__ == "__main__":
    main()
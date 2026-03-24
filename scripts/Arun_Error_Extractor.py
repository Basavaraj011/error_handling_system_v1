from dataclasses import dataclass, field
from importlib import import_module
from typing import List, Dict, Optional, Any
from pathlib import Path
import re
import os
import sys
import yaml
from datetime import datetime
import boto3
import json

# -------------------------------
# Setup workspace for imports
# -------------------------------
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
sys.path.insert(0, workspace_root)
from config.settings import DATABASE_URL
from database.database_operations import insert_errors_into_db_new, insert_job_status_data
from connections.database_connections import DatabaseManager

# -------------------------------
# AWS Clients
# -------------------------------
s3 = boto3.client('s3')

# -------------------------------
# Log Extraction Functions
# -------------------------------
def parse_datetime(dt_str: str) -> Optional[str]:
    try:
        return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
    except:
        return None

def clean_stack_trace(trace: str) -> str:
    """
    Flatten trace into a single line and escape single quotes for SQL
    """
    cleaned = trace.replace("\n", "").replace("\r", "").replace("\t", "").strip()
    cleaned = cleaned.replace("'", "''")
    return cleaned

def extract_log_data_from_content(content: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract errors from a log content string.
    Returns a dictionary with 'errors' key containing list of error dicts.
    """
    raw_lines = content.splitlines()

    # Remove leading empty lines
    lines = []
    started = False
    for line in raw_lines:
        if not started and line.strip() == "":
            continue
        started = True
        lines.append(line.rstrip("\n"))

    if not lines:
        return {"errors": []}

    result = {"errors": []}
    total_failure_count = 0

    # 1. Label type
    first_line = lines[0]
    label_type = "ING" if "ING" in first_line else "PUB" if "PUB" in first_line else "UNKNOWN"
    label_type = "ingestion" if label_type == "ING" else "publishing" if label_type == "PUB" else "unknown"
    # 2. Start / End time
    start_time, end_time = None, None
    for line in lines[:5]:
        if "Start Time:" in line:
            start_time = parse_datetime(line.split("Start Time:")[1].strip())
        elif "End Time:" in line:
            end_time = parse_datetime(line.split("End Time:")[1].strip())

    # 3. Workflow counts
    running_count, success_count = 0, 0
    for line in lines:
        if "Running" in line and "workflows" in line:
            running_count = int(re.findall(r"\d+", line)[0])
        elif "Successful" in line and "workflows" in line:
            success_count = int(re.findall(r"\d+", line)[0])
        elif "Failed ing workflows (true errors):" in line or "Failed pub workflows (true errors):" in line:
            total_failure_count = int(re.findall(r"\d+", line)[0])

    # 4. Extract workflow blocks
    in_error_section = False
    current_block = []
    workflow_blocks = []

    for line in lines:
        if "Failed Workflow Details" in line:
            in_error_section = True
            continue
        if not in_error_section:
            continue
        # Stop condition
        if "Failed ing workflows" in line or "Failed pub workflows" in line:
            if current_block:
                workflow_blocks.append(current_block)
            break
        # Start new workflow block
        if "Workflow ID:" in line:
            if current_block:
                workflow_blocks.append(current_block)
            current_block = [line]
        else:
            if current_block:
                current_block.append(line)

    # 5. Process each block
    temp_error_dicts = []

    for block in workflow_blocks:
        failure_reason = None
        capture = False

        for line in block:
            if "Failure Reason:" in line:
                capture = True
                failure_reason = line.split("Failure Reason:")[1].strip()
                continue
            if capture:
                if line.strip() == "":
                    break
                failure_reason += " " + line.strip() if line.strip() else ""

        # Skip if Failure Reason is N/A
        if not failure_reason or failure_reason.strip().upper() == "N/A":
            continue

        # Flatten into single line
        full_stack_trace = failure_reason.strip()
        full_stack_trace_sql_safe = full_stack_trace.replace("\n", "").replace("\r", "").replace("\t", "").strip()
        cleaned_trace = clean_stack_trace(full_stack_trace)

        temp_error_dicts.append({
            "label_type": label_type,
            "start_time": start_time,
            "end_time": end_time,
            "running_workflows": running_count,
            "successful_workflows": success_count,
            "failure_workflows": total_failure_count,
            "stack_trace": full_stack_trace_sql_safe.replace("'", "''"),
            "cleaned_stack_trace": cleaned_trace,
            "tool": "Unknown",
            "main_error": "Failure Occurred in the Workflow"
        })

    result["errors"] = temp_error_dicts
    return result

# -------------------------------
# S3 Processing Function
# -------------------------------
def process_s3_file(content: str):
    """
    Download file from S3 and process it
    """

    # Extract errors from content
    data = extract_log_data_from_content(content)
    errors_list = data.get("errors", [])
    print("Extracted Errors:", errors_list)
    
    if True:
        try:
            # Load teams.yml
            config_path = os.path.join(workspace_root, 'config', 'teams.yml')
            with open(config_path) as f:
                cfg = yaml.safe_load(f)

            team_name = next(iter(cfg.get("teams", {})))
            project_name = next(iter(cfg.get("projects", {})))
            repo_name = next(iter(cfg.get("repo_names", {})))

            print("Team Name:", team_name)
            print("Project Name:", project_name)
            print("Repo Name:", repo_name)

            # Insert into DB
            try:
                db_manager = DatabaseManager(DATABASE_URL)

                # Insert error logs
                insert_errors_into_db_new(errors_list, db_manager, team_name, project_name, repo_name)
                print(f"Inserted {len(errors_list)} errors into the database successfully.")

                # Insert job status / non-error logs
                insert_job_status_data(errors_list, db_manager)
                print(f"Inserted job status data into the database successfully.")

            except Exception as e:
                print(f"Error connecting to database or inserting data: {e}")
                import traceback
                traceback.print_exc()

        except Exception as e:
            print(f"Error processing teams.yml or database: {e}")
            import traceback
            traceback.print_exc()


# -------------------------------
# Main Execution for local or testing
# -------------------------------
if __name__ == "__main__":
    # Example for local file (can remove when using S3 trigger)
    base_path = os.path.dirname(__file__)
    error_logs_file = os.path.join(base_path, "..", "Test_Error_Logs", "ErrorLogs1.txt")

    with open(error_logs_file, "r", encoding="utf-8") as f:
        content = f.read()

    data = extract_log_data_from_content(content)
    errors_list = data.get("errors", [])
    print("Extracted Errors (Local Test):", errors_list)
    process_s3_file("bucket","key")
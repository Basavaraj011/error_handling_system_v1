"""
Setup Project - Initialize the system for a new project
"""
import os
import yaml
import sqlite3
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_project(project_name: str, config_template: str = "template.yaml"):
    """Setup a new project"""
    logger.info(f"Setting up project: {project_name}")
    
    # Load template config
    config_path = Path(__file__).parent.parent / "config" / "projects" / config_template
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Customize config for new project
    config['project']['name'] = project_name
    
    # Save project config
    project_config_path = Path(__file__).parent.parent / "config" / "projects" / f"{project_name}.yaml"
    with open(project_config_path, 'w') as f:
        yaml.dump(config, f)
    
    logger.info(f"Project config created: {project_config_path}")
    
    # Initialize database
    db_path = Path(__file__).parent.parent / "database" / f"{project_name}.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables from schema files
    schema_dir = Path(__file__).parent.parent / "database"
    for schema_file in schema_dir.glob("*_schema.sql"):
        with open(schema_file, 'r') as f:
            sql = f.read()
            cursor.executescript(sql)
    
    conn.commit()
    conn.close()
    
    logger.info(f"Database initialized: {db_path}")
    logger.info(f"Project {project_name} setup completed!")


if __name__ == "__main__":
    import sys
    project_name = sys.argv[1] if len(sys.argv) > 1 else "my_project"
    setup_project(project_name)

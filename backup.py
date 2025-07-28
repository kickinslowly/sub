"""
SQLite Database Backup Module

This module provides functionality to create and manage backups of the SQLite database.
It includes functions to create daily and weekly backups, ensuring that there are always
two backup databases: one from 24 hours ago and one from a week ago.
"""

import os
import sqlite3
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backup.log')
    ]
)
logger = logging.getLogger('backup')

# Backup file paths
INSTANCE_DIR = 'instance'
BACKUP_DIR = os.path.join(INSTANCE_DIR, 'backups')
MAIN_DB = os.path.join(INSTANCE_DIR, 'portal.db')
DAILY_BACKUP = os.path.join(BACKUP_DIR, 'portal_daily_backup.db')
WEEKLY_BACKUP = os.path.join(BACKUP_DIR, 'portal_weekly_backup.db')


def ensure_backup_dir():
    """Ensure the backup directory exists."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        logger.info(f"Created backup directory: {BACKUP_DIR}")


def create_backup(source_db, destination_db):
    """
    Create a backup of the SQLite database using the SQLite Backup API.
    
    Args:
        source_db (str): Path to the source database file
        destination_db (str): Path to the destination backup file
    
    Returns:
        bool: True if backup was successful, False otherwise
    """
    try:
        # Ensure the backup directory exists
        ensure_backup_dir()
        
        # Connect to the source database
        source = sqlite3.connect(source_db)
        
        # Connect to the destination database (will be created if it doesn't exist)
        destination = sqlite3.connect(destination_db)
        
        # Create a backup
        source.backup(destination)
        
        # Close the connections
        source.close()
        destination.close()
        
        logger.info(f"Successfully created backup: {destination_db}")
        return True
    except Exception as e:
        logger.error(f"Error creating backup {destination_db}: {str(e)}")
        return False


def create_daily_backup():
    """Create a daily backup of the main database."""
    logger.info("Starting daily backup process")
    return create_backup(MAIN_DB, DAILY_BACKUP)


def create_weekly_backup():
    """Create a weekly backup of the main database."""
    logger.info("Starting weekly backup process")
    return create_backup(MAIN_DB, WEEKLY_BACKUP)


def get_backup_info():
    """
    Get information about the backup files.
    
    Returns:
        dict: Information about the backup files
    """
    daily_exists = os.path.exists(DAILY_BACKUP)
    weekly_exists = os.path.exists(WEEKLY_BACKUP)
    
    daily_time = None
    weekly_time = None
    
    if daily_exists:
        daily_time = datetime.fromtimestamp(os.path.getmtime(DAILY_BACKUP))
    
    if weekly_exists:
        weekly_time = datetime.fromtimestamp(os.path.getmtime(WEEKLY_BACKUP))
    
    return {
        'daily_backup': {
            'exists': daily_exists,
            'path': DAILY_BACKUP,
            'last_modified': daily_time
        },
        'weekly_backup': {
            'exists': weekly_exists,
            'path': WEEKLY_BACKUP,
            'last_modified': weekly_time
        }
    }


def restore_from_backup(backup_file, destination=None):
    """
    Restore the database from a backup file.
    
    Args:
        backup_file (str): Path to the backup file
        destination (str, optional): Path to the destination file. If None, restores to the main database.
    
    Returns:
        bool: True if restore was successful, False otherwise
    """
    if destination is None:
        destination = MAIN_DB
    
    try:
        if not os.path.exists(backup_file):
            logger.error(f"Backup file does not exist: {backup_file}")
            return False
        
        # Connect to the backup database
        backup = sqlite3.connect(backup_file)
        
        # Connect to the destination database
        dest = sqlite3.connect(destination)
        
        # Create a backup (which effectively restores the destination from the backup)
        backup.backup(dest)
        
        # Close the connections
        backup.close()
        dest.close()
        
        logger.info(f"Successfully restored from backup: {backup_file} to {destination}")
        return True
    except Exception as e:
        logger.error(f"Error restoring from backup {backup_file}: {str(e)}")
        return False
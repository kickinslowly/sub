"""
Scheduler Module for Database Backups

This module provides functionality to schedule database backups using APScheduler.
It configures daily and weekly backup jobs to ensure there are always two backup
databases: one from 24 hours ago and one from a week ago.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from backup import create_daily_backup, create_weekly_backup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scheduler.log')
    ]
)
logger = logging.getLogger('scheduler')

# Create scheduler
scheduler = BackgroundScheduler()


def configure_scheduler():
    """
    Configure the scheduler with daily and weekly backup jobs.
    
    The daily backup runs every day at 1:00 AM.
    The weekly backup runs every Sunday at 2:00 AM.
    """
    # Add daily backup job (runs at 1:00 AM every day)
    scheduler.add_job(
        create_daily_backup,
        trigger=CronTrigger(hour=1, minute=0),
        id='daily_backup',
        name='Daily Database Backup',
        replace_existing=True
    )
    logger.info("Scheduled daily backup job (runs at 1:00 AM every day)")
    
    # Add weekly backup job (runs at 2:00 AM every Sunday)
    scheduler.add_job(
        create_weekly_backup,
        trigger=CronTrigger(day_of_week='sun', hour=2, minute=0),
        id='weekly_backup',
        name='Weekly Database Backup',
        replace_existing=True
    )
    logger.info("Scheduled weekly backup job (runs at 2:00 AM every Sunday)")


def start_scheduler():
    """
    Start the scheduler if it's not already running.
    
    Returns:
        bool: True if the scheduler was started, False otherwise
    """
    if scheduler.running:
        logger.warning("Scheduler is already running")
        return False
    
    try:
        # Configure the scheduler
        configure_scheduler()
        
        # Start the scheduler
        scheduler.start()
        logger.info("Scheduler started successfully")
        return True
    except Exception as e:
        logger.error(f"Error starting scheduler: {str(e)}")
        return False


def stop_scheduler():
    """
    Stop the scheduler if it's running.
    
    Returns:
        bool: True if the scheduler was stopped, False otherwise
    """
    if not scheduler.running:
        logger.warning("Scheduler is not running")
        return False
    
    try:
        # Shutdown the scheduler
        scheduler.shutdown()
        logger.info("Scheduler stopped successfully")
        return True
    except Exception as e:
        logger.error(f"Error stopping scheduler: {str(e)}")
        return False


def get_scheduler_info():
    """
    Get information about the scheduler and its jobs.
    
    Returns:
        dict: Information about the scheduler and its jobs
    """
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run_time': job.next_run_time
        })
    
    return {
        'running': scheduler.running,
        'jobs': jobs
    }


def create_immediate_backup(backup_type='daily'):
    """
    Create an immediate backup of the specified type.
    
    Args:
        backup_type (str): The type of backup to create ('daily' or 'weekly')
    
    Returns:
        bool: True if the backup was created successfully, False otherwise
    """
    try:
        if backup_type == 'daily':
            return create_daily_backup()
        elif backup_type == 'weekly':
            return create_weekly_backup()
        else:
            logger.error(f"Invalid backup type: {backup_type}")
            return False
    except Exception as e:
        logger.error(f"Error creating immediate {backup_type} backup: {str(e)}")
        return False
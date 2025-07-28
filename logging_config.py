import os
import logging
from logging.handlers import RotatingFileHandler

def configure_logging(app):
    """Configure logging for the application."""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    # Set up file handler for all logs
    file_handler = RotatingFileHandler(
        'logs/app.log', 
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    
    # Set up formatters
    file_formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Add handlers to app logger
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.DEBUG)
    
    # Configure the root logger to ensure all loggers in the application use the same settings
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    
    # Log application startup
    app.logger.info('Application startup')
    
    return app.logger
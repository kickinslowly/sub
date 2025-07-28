import threading
import logging
import traceback
from functools import wraps

logger = logging.getLogger(__name__)

def run_in_background(func, *args, **kwargs):
    """
    Runs the given function in a background thread.
    
    This utility function creates a new thread to execute the provided function,
    allowing the main thread to continue execution without waiting for the function to complete.
    
    Args:
        func: The function to run in the background
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
    
    Returns:
        threading.Thread: The thread object that was created
    
    Example:
        run_in_background(send_email, "Subject", "recipient@example.com", "Email body")
    """
    def wrapped_func(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            # Log the exception but don't crash the thread
            logger.error(f"Error in background thread: {e}")
            logger.error(traceback.format_exc())
    
    # Create and start the thread
    thread = threading.Thread(target=wrapped_func, args=args, kwargs=kwargs)
    thread.daemon = True  # Thread will exit when the main program exits
    thread.start()
    
    return thread

def background_task(func):
    """
    Decorator that runs the decorated function in a background thread.
    
    This decorator can be applied to functions that should be executed in the background,
    allowing the main thread to continue execution without waiting for the function to complete.
    
    Example:
        @background_task
        def send_notification(user_id, message):
            # This function will run in a background thread
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return run_in_background(func, *args, **kwargs)
    return wrapper
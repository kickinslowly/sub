/**
 * Toasts.js - Handles toast notification functionality across the application
 * 
 * This script provides a standardized way to display toast notifications in the application.
 * It includes functions to show success, error, and info toast messages with customizable
 * duration and automatic dismissal.
 */

/**
 * Show a toast notification with the specified message
 * @param {string} message - The message to display in the toast
 * @param {string} type - The type of toast (success, error, info)
 * @param {number} duration - Duration in milliseconds to show the toast (default: 3000ms)
 */
function showToast(message, type = 'success', duration = 3000) {
    // Get the appropriate toast element based on type
    let toastId;
    switch (type) {
        case 'error':
            toastId = 'toast-error';
            break;
        case 'info':
            toastId = 'toast-info';
            break;
        case 'success':
        default:
            toastId = 'toast-success';
            break;
    }

    const toast = document.getElementById(toastId);
    
    // If the toast element doesn't exist, create it
    if (!toast) {
        console.warn(`Toast element with id "${toastId}" not found. Creating a new one.`);
        createToastElement(toastId, type);
        return showToast(message, type, duration); // Retry after creating
    }
    
    // Set the message and display the toast
    toast.textContent = message;
    toast.style.display = 'block';

    // Hide toast after the specified duration
    setTimeout(() => {
        toast.style.display = 'none';
    }, duration);
}

/**
 * Show a success toast notification
 * @param {string} message - The message to display
 * @param {number} duration - Duration in milliseconds (default: 3000ms)
 */
function showSuccessToast(message, duration = 3000) {
    showToast(message, 'success', duration);
}

/**
 * Show an error toast notification
 * @param {string} message - The message to display
 * @param {number} duration - Duration in milliseconds (default: 3000ms)
 */
function showErrorToast(message, duration = 3000) {
    showToast(message, 'error', duration);
}

/**
 * Show an info toast notification
 * @param {string} message - The message to display
 * @param {number} duration - Duration in milliseconds (default: 3000ms)
 */
function showInfoToast(message, duration = 3000) {
    showToast(message, 'info', duration);
}

/**
 * Create a toast element if it doesn't exist
 * @param {string} id - The id to give the toast element
 * @param {string} type - The type of toast (success, error, info)
 */
function createToastElement(id, type) {
    // Check if toast container exists, create if not
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
    }
    
    // Create the toast element
    const toast = document.createElement('div');
    toast.id = id;
    toast.className = 'toast';
    
    // Add type-specific styling
    switch (type) {
        case 'error':
            toast.classList.add('toast-error');
            break;
        case 'info':
            toast.classList.add('toast-info');
            break;
        case 'success':
            toast.classList.add('toast-success');
            break;
    }
    
    // Add the toast to the container
    toastContainer.appendChild(toast);
}
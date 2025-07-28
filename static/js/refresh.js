/**
 * Refresh.js - Handles data refresh functionality across the application
 * 
 * This script provides a standardized way to handle refreshing data in the application.
 * It includes functions to handle refresh button states, API calls, and updating the UI.
 */

/**
 * Initialize a refresh button with the specified options
 * @param {string} buttonId - The ID of the refresh button element
 * @param {Object} options - Configuration options
 * @param {string} options.endpoint - The API endpoint to fetch data from
 * @param {Function} options.onSuccess - Callback function to handle successful data fetch
 * @param {Function} options.onError - Callback function to handle errors (optional)
 * @param {boolean} options.reloadPage - Whether to reload the page instead of making an API call (default: false)
 */
function initRefreshButton(buttonId, options) {
    const refreshButton = document.getElementById(buttonId);
    if (!refreshButton) {
        console.error(`Refresh button with id "${buttonId}" not found.`);
        return;
    }

    refreshButton.addEventListener('click', function() {
        // Show loading state
        const originalContent = refreshButton.innerHTML;
        refreshButton.innerHTML = '<span class="spinner"></span> Refreshing...';
        refreshButton.disabled = true;

        if (options.reloadPage) {
            // Simple page reload
            location.reload();
            return;
        }

        // Fetch updated data from the API
        fetch(options.endpoint)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                // Call the success callback with the data
                if (typeof options.onSuccess === 'function') {
                    options.onSuccess(data);
                }
                
                // Show success toast if available
                if (typeof showSuccessToast === 'function') {
                    showSuccessToast('Data refreshed successfully!');
                }
                
                // Reset button
                refreshButton.innerHTML = originalContent;
                refreshButton.disabled = false;
            })
            .catch(error => {
                console.error('Error refreshing data:', error);
                
                // Call the error callback if provided
                if (typeof options.onError === 'function') {
                    options.onError(error);
                }
                
                // Show error toast if available
                if (typeof showErrorToast === 'function') {
                    showErrorToast('Error refreshing data. Please try again.');
                }
                
                // Reset button
                refreshButton.innerHTML = originalContent;
                refreshButton.disabled = false;
            });
    });
}

/**
 * Update a list of items in the UI
 * @param {string} containerId - The ID of the container element
 * @param {Array} items - The array of items to display
 * @param {Function} itemRenderer - Function that returns HTML for each item
 * @param {string} emptyMessage - Message to display when there are no items
 */
function updateItemsList(containerId, items, itemRenderer, emptyMessage = 'No items available.') {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`Container with id "${containerId}" not found.`);
        return;
    }
    
    // Clear existing content
    container.innerHTML = '';
    
    if (!items || items.length === 0) {
        // Display empty message
        const emptyEl = document.createElement('p');
        emptyEl.className = 'no-items';
        emptyEl.textContent = emptyMessage;
        container.appendChild(emptyEl);
        return;
    }
    
    // Add each item to the container
    items.forEach(item => {
        const itemHTML = itemRenderer(item);
        if (typeof itemHTML === 'string') {
            // If the renderer returns a string, insert it as HTML
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = itemHTML;
            while (tempDiv.firstChild) {
                container.appendChild(tempDiv.firstChild);
            }
        } else if (itemHTML instanceof Element) {
            // If the renderer returns a DOM element, append it directly
            container.appendChild(itemHTML);
        }
    });
}
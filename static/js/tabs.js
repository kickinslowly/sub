/**
 * Tabs.js - Handles tab switching functionality across the application
 * 
 * This script provides a standardized way to handle tab switching in the application.
 * It automatically sets up event listeners for tab elements and handles the switching
 * between tab content sections.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tab functionality
    initTabs();
});

/**
 * Initialize tab functionality for all tab elements on the page
 */
function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    const contents = document.querySelectorAll('.tab-content');

    if (tabs.length === 0) return; // No tabs found, exit early

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all tabs and contents
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));

            // Add active class to clicked tab and corresponding content
            tab.classList.add('active');
            const tabId = `tab-${tab.dataset.tab}`;
            const contentElement = document.getElementById(tabId);
            
            if (contentElement) {
                contentElement.classList.add('active');
            } else {
                console.warn(`Tab content with id "${tabId}" not found.`);
            }
        });
    });
}

/**
 * Manually switch to a specific tab
 * @param {string} tabId - The data-tab value of the tab to switch to
 */
function switchToTab(tabId) {
    const tab = document.querySelector(`.tab[data-tab="${tabId}"]`);
    if (tab) {
        tab.click();
    } else {
        console.warn(`Tab with data-tab="${tabId}" not found.`);
    }
}
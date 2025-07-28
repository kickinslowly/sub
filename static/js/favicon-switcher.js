/**
 * Favicon Switcher
 * 
 * This script detects the user's color scheme preference (dark or light mode)
 * and switches the favicon accordingly.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Function to update favicon based on color scheme
    function updateFavicon() {
        // Check if the user prefers dark mode
        const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        // Get the favicon link element
        const favicon = document.querySelector('link[rel="icon"]');
        
        // Set the appropriate favicon based on the color scheme
        if (prefersDarkMode) {
            favicon.href = favicon.href.replace('favicon.png', 'favicon_darkmode.png');
        } else {
            favicon.href = favicon.href.replace('favicon.png', 'favicon_lightmode.png');
        }
    }
    
    // Update favicon on page load
    updateFavicon();
    
    // Listen for changes in color scheme preference
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', updateFavicon);
});
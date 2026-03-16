/**
 * Single Page Application Navigation System
 * 
 * Converts traditional multi-page navigation into SPA-like behavior:
 * - Clicking nav links loads content without page reload
 * - Uses history.replaceState() - no new browser history entries
 * - Updates active nav states dynamically
 * - Provides instant navigation feel with loading transitions
 */
(function() {
    'use strict';
    
    console.log('[SPA] Script loaded, initializing...');

    // Configuration
    const CONFIG = {
        // Content area selectors (in order of priority)
        contentSelectors: ['.content-area', '.admin-content'],
        // Sidebar nav selectors
        navSelectors: ['.sidebar-nav', '.admin-nav'],
        // Links that should NOT be intercepted (standalone templates, auth, etc.)
        excludePatterns: [
            // Auth pages
            '/accounts/login',
            '/accounts/logout',
            '/accounts/register',
            '/accounts/verify',
            '/accounts/confirm-device',
            '/accounts/profile',        // Standalone template
            '/accounts/sessions',       // Standalone template  
            '/accounts/notification',   // Standalone template
            '/accounts/delete',         // Standalone template
            // Support pages (standalone templates)
            '/help/',
            // Subscription pages (standalone templates)
            '/subscriptions/pricing',
            '/subscriptions/checkout',
            '/subscriptions/my-subscription',
            '/subscriptions/payment-history',
            // Other
            'download',
            '/api/',
            '/admin/',  // Django admin
        ],
        // Page title element selector
        titleSelector: '.page-title h1, .admin-topbar h1, title',
        // Loading indicator delay (ms)
        loadingDelay: 50,
        // Minimum loading time for visual feedback (ms)
        minLoadingTime: 150,
    };

    // State
    let isNavigating = false;
    let loadingIndicator = null;
    let currentAbortController = null;

    /**
     * Initialize SPA navigation
     */
    function init() {
        // Create loading indicator
        createLoadingIndicator();
        
        // Intercept link clicks
        document.addEventListener('click', handleLinkClick);
        
        // Intercept form submissions
        document.addEventListener('submit', handleFormSubmit);
        
        // Handle back/forward (though we use replaceState, edge cases exist)
        window.addEventListener('popstate', handlePopState);
        
        console.log('[SPA] Navigation initialized');
    }

    /**
     * Create a top loading bar indicator
     */
    function createLoadingIndicator() {
        loadingIndicator = document.createElement('div');
        loadingIndicator.className = 'spa-loading-bar';
        loadingIndicator.innerHTML = '<div class="spa-loading-progress"></div>';
        document.body.appendChild(loadingIndicator);
    }

    /**
     * Show loading state
     */
    function showLoading() {
        document.body.classList.add('spa-navigating');
        loadingIndicator.classList.add('active');
        
        // Fade out content area slightly
        const contentArea = getContentArea();
        if (contentArea) {
            contentArea.style.opacity = '0.6';
            contentArea.style.pointerEvents = 'none';
        }
    }

    /**
     * Hide loading state
     */
    function hideLoading() {
        document.body.classList.remove('spa-navigating');
        loadingIndicator.classList.remove('active');
        
        const contentArea = getContentArea();
        if (contentArea) {
            contentArea.style.opacity = '';
            contentArea.style.pointerEvents = '';
        }
    }

    /**
     * Get the main content area element
     */
    function getContentArea() {
        for (const selector of CONFIG.contentSelectors) {
            const el = document.querySelector(selector);
            if (el) return el;
        }
        return null;
    }

    /**
     * Check if a URL should be intercepted for SPA navigation
     */
    function shouldIntercept(url) {
        // Must be same origin
        try {
            const urlObj = new URL(url, window.location.origin);
            if (urlObj.origin !== window.location.origin) return false;
            
            // Check exclude patterns
            const pathname = urlObj.pathname;
            for (const pattern of CONFIG.excludePatterns) {
                if (pathname.includes(pattern)) return false;
            }
            
            return true;
        } catch (e) {
            return false;
        }
    }

    /**
     * Handle link clicks
     */
    function handleLinkClick(e) {
        // Find closest anchor
        const link = e.target.closest('a');
        if (!link) return;

        const href = link.getAttribute('href');
        if (!href) return;

        // Skip various cases
        if (href.startsWith('#') ||
            href.startsWith('javascript:') ||
            href.startsWith('mailto:') ||
            href.startsWith('tel:') ||
            link.target === '_blank' ||
            link.hasAttribute('download') ||
            link.hasAttribute('data-no-spa') ||
            link.classList.contains('no-spa') ||
            e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) {
            console.log('[SPA] Skipping link (special case):', href);
            return;
        }

        // Check if we should intercept
        if (!shouldIntercept(href)) {
            console.log('[SPA] Skipping link (excluded):', href);
            return;
        }

        // Prevent default and navigate via SPA
        console.log('[SPA] Intercepting navigation to:', href);
        e.preventDefault();
        navigateTo(href);
    }

    /**
     * Handle form submissions
     */
    function handleFormSubmit(e) {
        const form = e.target;
        const action = form.getAttribute('action') || window.location.href;
        const method = (form.method || 'GET').toUpperCase();

        // Skip forms that should not be intercepted
        if (form.hasAttribute('data-no-spa') ||
            form.classList.contains('no-spa') ||
            form.classList.contains('auth-form') ||
            form.querySelector('input[type="file"]') ||
            action.includes('download')) {
            return;
        }

        // Check if we should intercept
        if (!shouldIntercept(action)) return;

        e.preventDefault();

        if (method === 'GET') {
            // Build URL with form data
            const formData = new FormData(form);
            const params = new URLSearchParams(formData).toString();
            const url = action.split('?')[0] + (params ? '?' + params : '');
            navigateTo(url);
        } else {
            // POST: Submit via fetch
            submitForm(form, action, method);
        }
    }

    /**
     * Submit form via fetch and handle response
     */
    async function submitForm(form, action, method) {
        if (isNavigating) return;
        isNavigating = true;
        showLoading();

        const startTime = Date.now();

        try {
            const formData = new FormData(form);
            
            // Get CSRF token
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                              getCookie('csrftoken');
            
            const response = await fetch(action, {
                method: method,
                body: formData,
                credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-SPA-Request': '1',
                },
            });

            // Ensure minimum loading time
            const elapsed = Date.now() - startTime;
            if (elapsed < CONFIG.minLoadingTime) {
                await new Promise(r => setTimeout(r, CONFIG.minLoadingTime - elapsed));
            }

            // Handle redirect
            if (response.redirected) {
                await loadContent(response.url, response);
            } else if (response.ok) {
                await loadContent(response.url || action, response);
            } else {
                // On error, fall back to traditional form submit
                hideLoading();
                form.submit();
            }
        } catch (error) {
            console.error('[SPA] Form submit error:', error);
            hideLoading();
            form.submit();
        } finally {
            isNavigating = false;
        }
    }

    /**
     * Navigate to a URL
     */
    async function navigateTo(url) {
        if (isNavigating) {
            // Cancel previous navigation
            if (currentAbortController) {
                currentAbortController.abort();
            }
        }

        isNavigating = true;
        currentAbortController = new AbortController();
        
        // Show loading after a small delay (avoid flicker for fast loads)
        const loadingTimeout = setTimeout(showLoading, CONFIG.loadingDelay);
        const startTime = Date.now();

        try {
            const response = await fetch(url, {
                method: 'GET',
                credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-SPA-Request': '1',
                },
                signal: currentAbortController.signal,
            });

            clearTimeout(loadingTimeout);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            // Ensure minimum loading time for visual feedback
            const elapsed = Date.now() - startTime;
            if (elapsed < CONFIG.minLoadingTime) {
                showLoading(); // Show it now if we haven't
                await new Promise(r => setTimeout(r, CONFIG.minLoadingTime - elapsed));
            }

            await loadContent(url, response);

        } catch (error) {
            clearTimeout(loadingTimeout);
            
            if (error.name === 'AbortError') {
                console.log('[SPA] Navigation cancelled');
                return;
            }

            console.error('[SPA] Navigation error:', error);
            // Fall back to traditional navigation
            window.location.replace(url);
        } finally {
            isNavigating = false;
            currentAbortController = null;
            hideLoading();
        }
    }

    /**
     * Load content from response into the page
     */
    async function loadContent(url, response) {
        console.log('[SPA] Loading content for:', url);
        const html = await response.text();
        
        // Parse the HTML
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        // Get current content area first - determine which selector we're using
        let currentContent = null;
        let currentSelector = null;
        for (const selector of CONFIG.contentSelectors) {
            currentContent = document.querySelector(selector);
            if (currentContent) {
                currentSelector = selector;
                break;
            }
        }
        
        if (!currentContent) {
            console.error('[SPA] No content area found on current page');
            window.location.replace(url);
            return;
        }

        // Get new content area from response using THE SAME selector
        // This ensures we only SPA-load compatible templates
        const newContent = doc.querySelector(currentSelector);

        if (!newContent) {
            console.log('[SPA] Template structure mismatch - falling back to full reload');
            console.log('[SPA] Current page has:', currentSelector, 'but new page does not');
            window.location.replace(url);
            return;
        }
        console.log('[SPA] Found matching content area:', currentSelector);

        // Check if either current or new page has embedded <style> tags
        // If so, fall back to full page reload to ensure proper styling
        const currentHasStyles = currentContent.querySelector('style') !== null;
        const newHasStyles = newContent.querySelector('style') !== null;
        
        if (currentHasStyles || newHasStyles) {
            console.log('[SPA] Page has embedded styles - falling back to full reload for proper CSS');
            window.location.replace(url);
            return;
        }

        // Update the URL using replaceState (no history entry)
        history.replaceState({ spa: true, url: url }, '', url);
        console.log('[SPA] URL updated to:', url);

        // Animate out old content
        currentContent.classList.add('spa-fade-out');
        
        await new Promise(r => setTimeout(r, 100));

        // Replace content
        currentContent.innerHTML = newContent.innerHTML;
        console.log('[SPA] Content replaced successfully');
        
        // Update page title
        const newTitle = doc.querySelector('title');
        if (newTitle) {
            document.title = newTitle.textContent;
        }

        // Update the H1 title if present
        const newH1 = doc.querySelector('.page-title h1');
        const currentH1 = document.querySelector('.page-title h1');
        if (newH1 && currentH1) {
            currentH1.innerHTML = newH1.innerHTML;
        }

        // Update breadcrumbs if present
        const newBreadcrumb = doc.querySelector('.breadcrumb');
        const currentBreadcrumb = document.querySelector('.breadcrumb');
        if (newBreadcrumb && currentBreadcrumb) {
            currentBreadcrumb.innerHTML = newBreadcrumb.innerHTML;
        }

        // Update active nav state
        updateActiveNav(url);

        // Execute scripts in new content
        executeScripts(currentContent);

        // Re-initialize any Bootstrap components
        reinitBootstrap(currentContent);

        // Animate in new content
        currentContent.classList.remove('spa-fade-out');
        currentContent.classList.add('spa-fade-in');
        
        setTimeout(() => {
            currentContent.classList.remove('spa-fade-in');
        }, 200);

        // Scroll to top of content
        currentContent.scrollTop = 0;
        
        // Dispatch custom event for other scripts to hook into
        window.dispatchEvent(new CustomEvent('spa:navigated', { 
            detail: { url, content: currentContent } 
        }));

        hideLoading();
    }

    /**
     * Update active state on navigation links
     */
    function updateActiveNav(url) {
        const pathname = new URL(url, window.location.origin).pathname;

        // Find all nav containers
        for (const navSelector of CONFIG.navSelectors) {
            const nav = document.querySelector(navSelector);
            if (!nav) continue;

            // Remove active from all links
            nav.querySelectorAll('.nav-link').forEach(link => {
                link.classList.remove('active');
            });

            // Find matching link and activate it
            let bestMatch = null;
            let bestMatchLength = 0;

            nav.querySelectorAll('.nav-link').forEach(link => {
                const href = link.getAttribute('href');
                if (!href || href === '#') return;

                try {
                    const linkPath = new URL(href, window.location.origin).pathname;
                    
                    // Check if current path starts with link path
                    if (pathname === linkPath || 
                        (linkPath !== '/' && pathname.startsWith(linkPath))) {
                        // Prefer more specific matches
                        if (linkPath.length > bestMatchLength) {
                            bestMatch = link;
                            bestMatchLength = linkPath.length;
                        }
                    }
                } catch (e) {}
            });

            if (bestMatch) {
                bestMatch.classList.add('active');
            }
        }
    }

    /**
     * Execute inline scripts in new content
     * Only executes scripts that are safe (not initialization/global scripts)
     */
    function executeScripts(container) {
        const scripts = container.querySelectorAll('script');
        scripts.forEach(oldScript => {
            // Skip external scripts (they should already be loaded)
            if (oldScript.src) return;
            
            const content = oldScript.textContent;
            
            // Skip scripts that look like they might cause duplicates or global issues
            // These patterns indicate initialization code that shouldn't be re-run
            const skipPatterns = [
                'DOMContentLoaded',
                'sessionCheckInterval',
                'checkSessionValidity',
                'loadNotifications',
                'setInterval',
                'showLoggedOutModal',
                'toast-container',
                'toastContainer',
            ];
            
            const shouldSkip = skipPatterns.some(pattern => content.includes(pattern));
            if (shouldSkip) {
                console.log('[SPA] Skipping initialization script');
                return;
            }
            
            const newScript = document.createElement('script');
            newScript.textContent = content;
            oldScript.parentNode.replaceChild(newScript, oldScript);
        });
    }

    /**
     * Re-initialize Bootstrap components
     */
    function reinitBootstrap(container) {
        // Re-init tooltips
        if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            container.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
                new bootstrap.Tooltip(el);
            });
        }

        // Re-init popovers
        if (typeof bootstrap !== 'undefined' && bootstrap.Popover) {
            container.querySelectorAll('[data-bs-toggle="popover"]').forEach(el => {
                new bootstrap.Popover(el);
            });
        }

        // Re-init dropdowns
        if (typeof bootstrap !== 'undefined' && bootstrap.Dropdown) {
            container.querySelectorAll('[data-bs-toggle="dropdown"]').forEach(el => {
                new bootstrap.Dropdown(el);
            });
        }
    }

    /**
     * Handle popstate (back/forward buttons)
     */
    function handlePopState(e) {
        // Even though we use replaceState, handle edge cases
        if (e.state && e.state.spa) {
            navigateTo(e.state.url);
        }
    }

    /**
     * Get cookie value by name
     */
    function getCookie(name) {
        const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        return match ? match[2] : null;
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose API for external use
    window.SPA = {
        navigateTo: navigateTo,
        refresh: () => navigateTo(window.location.href),
    };

})();

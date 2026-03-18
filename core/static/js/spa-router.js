/**
 * SPA Router - Client-side navigation for Hamsvic Office
 *
 * Intercepts link clicks and form submissions to load content via AJAX,
 * creating a smooth single-page application experience.
 *
 * Works with the SPAMiddleware on the backend which extracts partial content
 * from rendered Django templates and returns JSON responses.
 *
 * Supports three layout modes:
 * - 'app': Pages with sidebar + header (base_modern.html)
 * - 'auth': Centered auth pages (auth_base.html)
 * - 'standalone': Full page content (custom layouts)
 */
(function() {
    'use strict';

    // =========================================================================
    // CONFIGURATION
    // =========================================================================

    // URL prefixes that should bypass SPA navigation entirely
    var BYPASS_PREFIXES = ['/admin/', '/admin-panel/', '/health/', '/api/', '/static/', '/media/'];

    // Exact URLs that should bypass SPA navigation
    var BYPASS_EXACT = ['/accounts/logout/', '/logout/'];

    // URL patterns that indicate file downloads
    var DOWNLOAD_PATTERNS = ['/download/', '/export/', '/specification-report/', '/forwarding-letter/'];

    // Current layout mode
    var currentLayout = detectCurrentLayout();

    // Navigation state
    var isNavigating = false;
    var abortController = null;

    // =========================================================================
    // LAYOUT DETECTION
    // =========================================================================

    function detectCurrentLayout() {
        if (document.querySelector('.sidebar') && document.querySelector('.content-area')) {
            return 'app';
        }
        if (document.querySelector('.auth-container')) {
            return 'auth';
        }
        return 'standalone';
    }

    // =========================================================================
    // LOADING INDICATOR
    // =========================================================================

    function createLoadingBar() {
        var bar = document.getElementById('spa-loading-bar');
        if (bar) return bar;

        bar = document.createElement('div');
        bar.id = 'spa-loading-bar';
        bar.style.cssText = [
            'position: fixed',
            'top: 0',
            'left: 0',
            'width: 0%',
            'height: 3px',
            'background: linear-gradient(90deg, #6366f1, #8b5cf6, #a78bfa)',
            'z-index: 99999',
            'transition: width 0.3s ease',
            'opacity: 0',
            'box-shadow: 0 0 10px rgba(99, 102, 241, 0.5)',
            'pointer-events: none'
        ].join(';');
        document.body.appendChild(bar);
        return bar;
    }

    function showLoading() {
        var bar = createLoadingBar();
        bar.style.opacity = '1';
        bar.style.width = '0%';
        // Animate to 70% quickly, then slow down
        requestAnimationFrame(function() {
            bar.style.width = '30%';
            setTimeout(function() { bar.style.width = '60%'; }, 200);
            setTimeout(function() { bar.style.width = '80%'; }, 600);
        });
    }

    function hideLoading() {
        var bar = createLoadingBar();
        bar.style.width = '100%';
        setTimeout(function() {
            bar.style.opacity = '0';
            setTimeout(function() { bar.style.width = '0%'; }, 300);
        }, 200);
    }

    // =========================================================================
    // CONTENT INJECTION
    // =========================================================================

    function fadeOut(el) {
        return new Promise(function(resolve) {
            el.style.transition = 'opacity 0.15s ease';
            el.style.opacity = '0';
            setTimeout(resolve, 150);
        });
    }

    function fadeIn(el) {
        el.style.opacity = '0';
        requestAnimationFrame(function() {
            el.style.transition = 'opacity 0.2s ease';
            el.style.opacity = '1';
        });
    }

    function injectAppContent(data) {
        var contentArea = document.querySelector('.content-area');
        if (!contentArea) return fullPageLoad(data);

        // Update page title in header
        if (data.pageTitle !== undefined) {
            var titleEl = document.querySelector('.page-title h1');
            if (titleEl) titleEl.textContent = data.pageTitle;
        }

        // Update document title
        if (data.title) {
            document.title = data.title;
        }

        // Clear previous dynamic styles
        removeDynamicStyles();

        // Inject extra styles
        if (data.styles) {
            injectStyles(data.styles, 'spa-dynamic-styles');
        }

        // Inject head extras
        if (data.head) {
            injectHead(data.head);
        }

        // Fade out, swap content, fade in
        return fadeOut(contentArea).then(function() {
            // Clear messages and inject content
            contentArea.innerHTML = data.content;

            // Execute scripts
            if (data.scripts) {
                executeScripts(data.scripts, contentArea);
            }

            // Execute inline scripts in content
            executeInlineScripts(contentArea);

            fadeIn(contentArea);

            // Scroll to top of content
            contentArea.scrollTop = 0;
            window.scrollTo(0, 0);
        });
    }

    function injectAuthContent(data) {
        var authContainer = document.querySelector('.auth-container > div');
        if (!authContainer) {
            // We're in app layout, need to switch to auth layout
            return switchToAuthLayout(data);
        }

        // Update document title
        if (data.title) {
            document.title = data.title;
        }

        // Clear previous dynamic styles
        removeDynamicStyles();

        // Inject extra styles
        if (data.styles) {
            injectStyles(data.styles, 'spa-dynamic-styles');
        }

        // Find or create the auth content area (after the logo and back-to-dashboard link)
        return fadeOut(authContainer).then(function() {
            // Rebuild auth container content - keep logo, update the rest
            var logoHtml = '<div class="logo"><div class="logo-icon">H</div><span class="logo-text">HAMSVIC</span></div>';
            authContainer.innerHTML = logoHtml + data.content;

            // Execute scripts
            if (data.scripts) {
                executeScripts(data.scripts, authContainer);
            }

            executeInlineScripts(authContainer);
            fadeIn(authContainer);
            window.scrollTo(0, 0);
        });
    }

    function switchToAppLayout(data) {
        // Full page reload when switching from auth/standalone to app layout
        // This is the simplest and most reliable approach for layout switches
        window.location.href = data._url || window.location.href;
    }

    function switchToAuthLayout(data) {
        // Full page reload when switching from app to auth layout
        window.location.href = data._url || window.location.href;
    }

    function fullPageLoad(data) {
        // For standalone pages, replace entire body
        var body = document.body;

        removeDynamicStyles();
        if (data.styles) {
            injectStyles(data.styles, 'spa-dynamic-styles');
        }

        if (data.title) {
            document.title = data.title;
        }

        return fadeOut(body).then(function() {
            body.innerHTML = data.content;
            executeInlineScripts(body);
            fadeIn(body);
            window.scrollTo(0, 0);
        });
    }

    // =========================================================================
    // STYLE & SCRIPT HELPERS
    // =========================================================================

    function removeDynamicStyles() {
        var existing = document.querySelectorAll('.spa-dynamic-styles, .spa-dynamic-head');
        for (var i = 0; i < existing.length; i++) {
            existing[i].remove();
        }
    }

    function injectStyles(css, className) {
        if (!css.trim()) return;
        var style = document.createElement('style');
        style.className = className;
        style.textContent = css;
        document.head.appendChild(style);
    }

    function injectHead(headHtml) {
        if (!headHtml.trim()) return;
        var container = document.createElement('div');
        container.innerHTML = headHtml;
        var children = container.children;
        for (var i = 0; i < children.length; i++) {
            var el = children[i].cloneNode(true);
            el.classList.add('spa-dynamic-head');
            document.head.appendChild(el);
        }
    }

    function executeScripts(scriptsHtml, container) {
        if (!scriptsHtml.trim()) return;

        // Create a temporary container to parse script tags
        var temp = document.createElement('div');
        temp.innerHTML = scriptsHtml;
        var scripts = temp.querySelectorAll('script');

        scripts.forEach(function(oldScript) {
            var newScript = document.createElement('script');
            // Copy attributes
            for (var i = 0; i < oldScript.attributes.length; i++) {
                var attr = oldScript.attributes[i];
                newScript.setAttribute(attr.name, attr.value);
            }
            if (oldScript.src) {
                newScript.src = oldScript.src;
            } else {
                newScript.textContent = oldScript.textContent;
            }
            (container || document.body).appendChild(newScript);
        });

        // Also execute non-script content (inline event handlers etc.)
        var nonScripts = temp.innerHTML.replace(/<script[\s\S]*?<\/script>/gi, '').trim();
        if (nonScripts && container) {
            container.insertAdjacentHTML('beforeend', nonScripts);
        }
    }

    function executeInlineScripts(container) {
        // Re-execute script tags that were injected via innerHTML
        var scripts = container.querySelectorAll('script');
        scripts.forEach(function(oldScript) {
            var newScript = document.createElement('script');
            for (var i = 0; i < oldScript.attributes.length; i++) {
                var attr = oldScript.attributes[i];
                newScript.setAttribute(attr.name, attr.value);
            }
            if (oldScript.src) {
                newScript.src = oldScript.src;
            } else {
                newScript.textContent = oldScript.textContent;
            }
            oldScript.parentNode.replaceChild(newScript, oldScript);
        });
    }

    // =========================================================================
    // NAVIGATION
    // =========================================================================

    function shouldBypass(url) {
        // Check if URL should bypass SPA navigation
        for (var i = 0; i < BYPASS_PREFIXES.length; i++) {
            if (url.startsWith(BYPASS_PREFIXES[i])) return true;
        }
        // Check exact URL matches
        for (var i = 0; i < BYPASS_EXACT.length; i++) {
            if (url === BYPASS_EXACT[i]) return true;
        }
        return false;
    }

    function isDownloadUrl(url) {
        for (var i = 0; i < DOWNLOAD_PATTERNS.length; i++) {
            if (url.indexOf(DOWNLOAD_PATTERNS[i]) !== -1) return true;
        }
        return false;
    }

    function isExternalUrl(url) {
        if (url.startsWith('/') || url.startsWith('#') || url.startsWith('javascript:')) return false;
        try {
            return new URL(url, window.location.origin).origin !== window.location.origin;
        } catch (e) {
            return true;
        }
    }

    function navigate(url, options) {
        options = options || {};
        var pushHistory = options.pushHistory !== false;
        var method = (options.method || 'GET').toUpperCase();
        var body = options.body || null;
        var isFormSubmit = options.isFormSubmit || false;

        // Normalize URL
        if (!url.startsWith('/') && !url.startsWith('http')) {
            url = '/' + url;
        }

        // Check bypass conditions
        if (shouldBypass(url)) {
            window.location.href = url;
            return;
        }

        // Check download URLs
        if (isDownloadUrl(url) && method === 'GET') {
            window.location.href = url;
            return;
        }

        // Prevent double navigation
        if (isNavigating) {
            if (abortController) {
                abortController.abort();
            }
        }

        isNavigating = true;
        showLoading();

        // Abort previous request
        if (abortController) {
            abortController.abort();
        }
        abortController = new AbortController();

        // Get CSRF token from cookie for POST requests
        var csrfToken = '';
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        if (match) csrfToken = match[1];

        var fetchOptions = {
            method: method,
            credentials: 'same-origin',
            signal: abortController.signal,
            headers: {
                'X-SPA-Request': 'true',
            }
        };

        // Add CSRF token header for non-GET requests
        if (method !== 'GET' && csrfToken) {
            fetchOptions.headers['X-CSRFToken'] = csrfToken;
        }

        if (body) {
            fetchOptions.body = body;
            // Don't set Content-Type for FormData (browser sets it with boundary)
        }

        fetch(url, fetchOptions)
            .then(function(response) {
                // Check if response is JSON (SPA response)
                var contentType = response.headers.get('Content-Type') || '';
                if (contentType.indexOf('application/json') === -1) {
                    // Non-JSON response - might be a file download or error
                    if (response.ok && contentType.indexOf('text/html') !== -1) {
                        // Full HTML page - do a normal navigation
                        window.location.href = url;
                        return null;
                    }
                    // File download or other binary response
                    window.location.href = url;
                    return null;
                }
                return response.json();
            })
            .then(function(data) {
                if (!data) return;

                hideLoading();
                isNavigating = false;

                // Handle different response types
                if (data.type === 'redirect') {
                    // Follow the redirect via SPA
                    navigate(data.url, { pushHistory: false });
                    if (pushHistory) {
                        history.replaceState({ spaUrl: data.url }, '', data.url);
                    }
                    return;
                }

                if (data.type === 'download') {
                    // Trigger a normal download
                    window.location.href = data.url;
                    return;
                }

                // Store URL on data for layout switch fallback
                data._url = url;

                // Handle content based on layout
                var targetLayout = data.layout;

                if (targetLayout === currentLayout) {
                    // Same layout - just swap content
                    if (targetLayout === 'app') {
                        injectAppContent(data);
                    } else if (targetLayout === 'auth') {
                        injectAuthContent(data);
                    } else {
                        fullPageLoad(data);
                    }
                } else if (targetLayout === 'app' && currentLayout !== 'app') {
                    // Switching TO app layout - need full page structure
                    switchToAppLayout(data);
                    return; // Will do full page load
                } else if (targetLayout === 'auth' && currentLayout !== 'auth') {
                    // Switching TO auth layout - need full page structure
                    switchToAuthLayout(data);
                    return; // Will do full page load
                } else {
                    // Standalone or other - full page load
                    fullPageLoad(data);
                    currentLayout = targetLayout;
                }

                // Update browser history
                if (pushHistory) {
                    history.pushState({ spaUrl: url }, '', url);
                }

                // Update active nav link
                updateActiveNavLink(url);

                // Dispatch custom event for other scripts to hook into
                document.dispatchEvent(new CustomEvent('spa:navigation', {
                    detail: { url: url, layout: targetLayout }
                }));
            })
            .catch(function(error) {
                if (error.name === 'AbortError') return;
                console.error('SPA navigation error:', error);
                hideLoading();
                isNavigating = false;
                // Fallback to normal navigation on error
                if (method === 'GET') {
                    window.location.href = url;
                } else {
                    showToast && showToast('Navigation failed. Please try again.', 'error');
                }
            });
    }

    function updateActiveNavLink(url) {
        var navLinks = document.querySelectorAll('.sidebar .nav-link');
        navLinks.forEach(function(link) {
            link.classList.remove('active');
            var href = link.getAttribute('href');
            if (href && (url === href || (url.startsWith(href) && href !== '/'))) {
                link.classList.add('active');
            }
        });
    }

    // =========================================================================
    // EVENT HANDLERS
    // =========================================================================

    // Intercept link clicks
    document.addEventListener('click', function(e) {
        var anchor = e.target.closest('a');
        if (!anchor) return;

        var href = anchor.getAttribute('href');
        if (!href) return;

        // Skip: anchors, javascript:, external, new-tab, download, modifier keys, dropdown toggles
        if (href.charAt(0) === '#' ||
            href.startsWith('javascript:') ||
            anchor.target === '_blank' ||
            anchor.hasAttribute('download') ||
            anchor.classList.contains('no-spa') ||
            anchor.dataset.bsToggle ||  // Bootstrap dropdown/collapse
            e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) {
            return;
        }

        // Skip external links
        if (isExternalUrl(href)) return;

        // Skip download URLs
        if (isDownloadUrl(href)) return;

        // Intercept the navigation
        e.preventDefault();
        navigate(href);
    });

    // Intercept form submissions
    document.addEventListener('submit', function(e) {
        var form = e.target;
        var action = form.getAttribute('action') || window.location.href;

        // Skip forms with special handling
        if (form.classList.contains('no-spa') ||
            form.classList.contains('download-form') ||
            form.querySelector('button[type="submit"].btn-download')) {
            return;
        }

        // Skip auth forms - they have complex OTP/redirect flows that need native handling
        if (form.classList.contains('auth-form') ||
            action.indexOf('/accounts/') !== -1) {
            return;
        }

        // Skip forms with file uploads (they need native handling for progress)
        if (form.querySelector('input[type=file]')) {
            // But still handle them via SPA for non-download forms
            var hasFiles = false;
            var fileInputs = form.querySelectorAll('input[type=file]');
            for (var i = 0; i < fileInputs.length; i++) {
                if (fileInputs[i].files && fileInputs[i].files.length > 0) {
                    hasFiles = true;
                    break;
                }
            }
            // If files are actually selected, let native behavior handle it
            if (hasFiles) return;
        }

        // Skip download actions
        if (isDownloadUrl(action)) return;

        // Skip external actions
        if (isExternalUrl(action)) return;

        // Skip bypass paths
        if (shouldBypass(action)) return;

        e.preventDefault();

        var method = (form.method || 'GET').toUpperCase();
        var formData = new FormData(form);

        if (method === 'GET') {
            var params = new URLSearchParams(formData).toString();
            var url = action.split('?')[0] + (params ? '?' + params : '');
            navigate(url);
        } else {
            navigate(action, {
                method: method,
                body: formData,
                isFormSubmit: true
            });
        }
    });

    // Handle browser back/forward buttons
    window.addEventListener('popstate', function(e) {
        var url = window.location.pathname + window.location.search;
        navigate(url, { pushHistory: false });
    });

    // =========================================================================
    // INITIALIZATION
    // =========================================================================

    // Set initial history state
    history.replaceState(
        { spaUrl: window.location.pathname + window.location.search },
        '',
        window.location.pathname + window.location.search
    );

    // Create loading bar on init
    createLoadingBar();

    // Mark the current page as SPA-ready
    document.documentElement.setAttribute('data-spa', 'true');
    document.documentElement.setAttribute('data-spa-layout', currentLayout);

    // Export navigate function for programmatic use
    window.spaNavigate = navigate;

    // Log SPA initialization
    console.log('[SPA] Router initialized, layout:', currentLayout);

})();

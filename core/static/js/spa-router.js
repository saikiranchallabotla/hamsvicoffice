/**
 * SPA Router - Client-side navigation for Hamsvic Office
 *
 * Intercepts link clicks and form submissions to load content via AJAX,
 * creating a smooth single-page application experience.
 *
 * Works with the SPAMiddleware on the backend which extracts partial content
 * from rendered Django templates and returns JSON responses.
 *
 * Keeps in-app navigation smooth while preserving the real current URL
 * so refresh and direct actions (like SOR/backend switching) stay on the
 * expected page.
 *
 * Supports four layout modes:
 * - 'app': Pages with sidebar + header (base_modern.html)
 * - 'auth': Centered auth pages (auth_base.html)
 * - 'classic': Pages with header/nav/footer (core/base.html, base.html)
 * - 'standalone': Full page content (custom layouts)
 */
(function() {
    'use strict';

    // =========================================================================
    // CONFIGURATION
    // =========================================================================

    // Fixed document title so Chrome tab never changes
    var FIXED_TITLE = 'Hamsvic';

    // URL prefixes that should bypass SPA navigation entirely
    var BYPASS_PREFIXES = ['/admin/', '/admin-panel/', '/health/', '/api/', '/static/', '/media/'];

    // Exact URLs that should bypass SPA navigation
    var BYPASS_EXACT = ['/accounts/logout/', '/logout/'];

    // URL patterns that indicate file downloads
    var DOWNLOAD_PATTERNS = ['/download/', '/export/', '/specification-report/', '/forwarding-letter/', '/bill-generate/', '/bill/document/', '/self-formatted/generate/'];

    // Dashboard is the floor — back button should not go past this
    var DASHBOARD_URL = '/dashboard/';

    // Track whether we're at the dashboard floor
    var isDashboardFloor = false;

    // History stack for proper back-button sequencing
    var historyStack = [window.location.pathname + window.location.search];

    /**
     * Set dashboard as the navigation floor.
     * Uses a guard entry technique: pushes a duplicate dashboard entry
     * so that pressing back lands on the guard, which we detect and
     * push forward again — effectively trapping the user on dashboard.
     */
    function setDashboardFloor() {
        isDashboardFloor = true;
        historyStack = [DASHBOARD_URL];
        // Replace current entry to mark it as the floor
        history.replaceState({ spa: true, url: DASHBOARD_URL, dashboardFloor: true }, '', DASHBOARD_URL);
    }

    // After every SPA navigation, check if we landed on dashboard and set floor
    function checkDashboardFloor(url) {
        if (url === DASHBOARD_URL || url === DASHBOARD_URL.replace(/\/$/, '')) {
            setDashboardFloor();
        }
    }

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
        return 'classic';
    }

    // =========================================================================
    // TRANSITION HELPERS
    // =========================================================================

    function fadeOut(el, duration) {
        return Promise.resolve();
    }

    function fadeIn(el, duration) {
        el.style.opacity = '1';
    }

    // =========================================================================
    // CONTENT INJECTION (same-layout)
    // =========================================================================

    // Clean up Bootstrap modals and body scroll locks before content swap
    function cleanupBeforeSwap() {
        var modals = document.querySelectorAll('.modal.show');
        modals.forEach(function(modal) {
            var instance = typeof bootstrap !== 'undefined' && bootstrap.Modal && bootstrap.Modal.getInstance(modal);
            if (instance) {
                try { instance.dispose(); } catch(e) {}
            }
        });
        document.querySelectorAll('.modal-backdrop').forEach(function(el) { el.remove(); });
        document.body.classList.remove('modal-open');
        document.body.style.removeProperty('overflow');
        document.body.style.removeProperty('padding-right');
    }

    function injectAppContent(data) {
        var contentArea = document.querySelector('.content-area');
        if (!contentArea) return fullPageSwitch(data);

        cleanupBeforeSwap();

        // Update page title in header (use innerHTML to render icons)
        if (data.pageTitle !== undefined) {
            var titleEl = document.querySelector('.page-title h1');
            if (titleEl) titleEl.innerHTML = data.pageTitle;
        }

        // Clear previous dynamic styles
        removeDynamicStyles();

        if (data.styles) injectStyles(data.styles, 'spa-dynamic-styles');
        if (data.head) injectHead(data.head);

        return fadeOut(contentArea).then(function() {
            contentArea.innerHTML = data.content;
            if (data.scripts) executeScripts(data.scripts, contentArea);
            executeInlineScripts(contentArea);
            fadeIn(contentArea);
            contentArea.scrollTop = 0;
            window.scrollTo(0, 0);
        });
    }

    function injectAuthContent(data) {
        var authContainer = document.querySelector('.auth-container > div');
        if (!authContainer) return fullPageSwitch(data);

        cleanupBeforeSwap();

        removeDynamicStyles();
        if (data.styles) injectStyles(data.styles, 'spa-dynamic-styles');

        return fadeOut(authContainer).then(function() {
            var logoHtml = '<div class="logo"><div class="logo-icon">H</div><span class="logo-text">HAMSVIC</span></div>';
            authContainer.innerHTML = logoHtml + data.content;
            if (data.scripts) executeScripts(data.scripts, authContainer);
            executeInlineScripts(authContainer);
            fadeIn(authContainer);
            window.scrollTo(0, 0);
        });
    }

    function injectClassicContent(data) {
        var container = document.querySelector('.container-fluid') || document.querySelector('main.container');
        if (!container) return fullPageSwitch(data);

        cleanupBeforeSwap();

        removeDynamicStyles();
        if (data.styles) injectStyles(data.styles, 'spa-dynamic-styles');
        if (data.head) injectHead(data.head);

        return fadeOut(container).then(function() {
            container.innerHTML = data.content;
            if (data.scripts) executeScripts(data.scripts, container);
            executeInlineScripts(container);
            fadeIn(container);
            container.scrollTop = 0;
            window.scrollTo(0, 0);
        });
    }

    // =========================================================================
    // CROSS-LAYOUT TRANSITION (full page replacement, no browser navigation)
    // =========================================================================

    /**
     * When the target page uses a different layout (e.g. app → classic,
     * classic → auth), we cannot simply swap the content area because the
     * page shell (sidebar, header, footer) is completely different.
     *
     * Strategy: Always fetch full HTML and replace the document client-side
     * so the browser tab never shows a loading state.
     */
    function fullPageSwitch(data) {
        var targetUrl = data._url || window.location.pathname;

        // If we already have full HTML (from prefetch or fallback), use it directly
        if (data._fullHtml) {
            return fadeOut(document.body, 80).then(function() {
                replaceDocument(data._fullHtml, targetUrl);
            });
        }

        // Fetch full HTML without SPA header so the server returns the complete page
        return fetch(targetUrl, {
            method: 'GET',
            credentials: 'same-origin'
        })
        .then(function(response) {
            return response.text();
        })
        .then(function(html) {
            return fadeOut(document.body, 80).then(function() {
                replaceDocument(html, targetUrl);
            });
        })
        .catch(function() {
            // Last resort: native navigation (only on network error)
            window.location.replace(targetUrl);
        });
    }

    /**
     * Replace the current document's content with parsed HTML from a full-page response.
     * This preserves the SPA router (it re-initialises itself).
     */
    function replaceDocument(html, targetUrl) {
        var doc = new DOMParser().parseFromString(html, 'text/html');

        // Replace all stylesheets and style tags in <head>
        var oldHeadEls = document.querySelectorAll('head style, head link[rel="stylesheet"]');
        var newHeadEls = doc.querySelectorAll('head style, head link[rel="stylesheet"]');

        oldHeadEls.forEach(function(el) { el.remove(); });
        newHeadEls.forEach(function(el) {
            document.head.appendChild(el.cloneNode(true));
        });

        // Copy any other head elements (meta viewport, fonts, etc.)
        var newMeta = doc.querySelectorAll('head meta[name="viewport"], head link[rel="preconnect"], head link[href*="fonts"]');
        newMeta.forEach(function(el) {
            if (!document.querySelector('head ' + el.tagName.toLowerCase() + '[href="' + el.getAttribute('href') + '"]')) {
                document.head.appendChild(el.cloneNode(true));
            }
        });

        // Replace body
        document.body.innerHTML = doc.body.innerHTML;

        // Execute all scripts in the new body
        executeInlineScripts(document.body);

        // Keep title fixed and URL synced to the actual current page
        var normalizedTarget = normalizeUrl(targetUrl || '');
        if (normalizedTarget) {
            currentLogicalUrl = normalizedTarget;
        }
        document.title = FIXED_TITLE;
        // Use pushState so back button works (replaceState was eating history)
        if (normalizedTarget && normalizedTarget !== historyStack[historyStack.length - 1]) {
            history.pushState({ spa: true, url: currentLogicalUrl }, '', currentLogicalUrl);
            historyStack.push(currentLogicalUrl);
            checkDashboardFloor(currentLogicalUrl);
        } else {
            history.replaceState({ spa: true, url: currentLogicalUrl }, '', currentLogicalUrl);
        }

        // Re-detect layout
        currentLayout = detectCurrentLayout();

        window.scrollTo(0, 0);
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

        var temp = document.createElement('div');
        temp.innerHTML = scriptsHtml;
        var scripts = temp.querySelectorAll('script');

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
            (container || document.body).appendChild(newScript);
        });

        var nonScripts = temp.innerHTML.replace(/<script[\s\S]*?<\/script>/gi, '').trim();
        if (nonScripts && container) {
            container.insertAdjacentHTML('beforeend', nonScripts);
        }
    }

    function executeInlineScripts(container) {
        var scripts = container.querySelectorAll('script');

        // Patch addEventListener to capture DOMContentLoaded callbacks registered
        // by the new inline scripts, since the real event already fired.
        var pendingCallbacks = [];
        var origAddEventListener = document.addEventListener;
        document.addEventListener = function(type, fn, opts) {
            if (type === 'DOMContentLoaded') {
                pendingCallbacks.push(fn);
            } else {
                origAddEventListener.call(document, type, fn, opts);
            }
        };

        scripts.forEach(function(oldScript) {
            // Skip the SPA router script itself to avoid double-init
            if (oldScript.src && oldScript.src.indexOf('spa-router.js') !== -1) return;

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

        // Restore original addEventListener
        document.addEventListener = origAddEventListener;

        // Execute captured DOMContentLoaded callbacks
        pendingCallbacks.forEach(function(fn) {
            try { fn(); } catch (e) { console.error('[SPA] DOMContentLoaded callback error:', e); }
        });
    }

    // =========================================================================
    // NAVIGATION
    // =========================================================================

    function shouldBypass(url) {
        for (var i = 0; i < BYPASS_PREFIXES.length; i++) {
            if (url.startsWith(BYPASS_PREFIXES[i])) return true;
        }
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

    function normalizeUrl(url) {
        if (!url) return null;
        if (url.startsWith('#') || url.startsWith('javascript:')) return null;

        try {
            var parsed = new URL(url, window.location.origin);
            if (parsed.origin !== window.location.origin) return null;
            return parsed.pathname + parsed.search;
        } catch (e) {
            return null;
        }
    }

    // Track current logical URL (the page we're actually viewing)
    var currentLogicalUrl = window.location.pathname + window.location.search;

    function navigate(url, options) {
        options = options || {};
        var method = (options.method || 'GET').toUpperCase();
        var body = options.body || null;

        url = normalizeUrl(url) || url;
        if (!url || isExternalUrl(url)) {
            if (url) window.location.replace(url);
            return;
        }

        // Skip navigation if already on same page (GET requests only)
        if (method === 'GET' && url === currentLogicalUrl) {
            return;
        }

        // Bypass conditions
        if (shouldBypass(url)) {
            window.location.replace(url);
            return;
        }

        // Download URLs
        if (isDownloadUrl(url) && method === 'GET') {
            // For downloads, open in hidden iframe so URL doesn't change
            var iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = url;
            document.body.appendChild(iframe);
            setTimeout(function() { iframe.remove(); }, 60000);
            return;
        }

        // Prevent double navigation
        if (isNavigating && abortController) {
            abortController.abort();
        }

        isNavigating = true;

        if (abortController) abortController.abort();
        abortController = new AbortController();

        // CSRF token
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

        if (method !== 'GET' && csrfToken) {
            fetchOptions.headers['X-CSRFToken'] = csrfToken;
        }

        if (body) {
            fetchOptions.body = body;
        }

        fetch(url, fetchOptions)
            .then(function(response) {
                var contentType = response.headers.get('Content-Type') || '';
                if (contentType.indexOf('application/json') === -1) {
                    // Non-JSON response — file download or unsupported page
                    if (response.ok && contentType.indexOf('text/html') !== -1) {
                        // Full HTML page — the middleware didn't process it
                        return response.text().then(function(html) {
                            return { _fullHtml: html };
                        });
                    }
                    // Binary / file download — trigger natively via hidden iframe
                    var iframe = document.createElement('iframe');
                    iframe.style.display = 'none';
                    iframe.src = url;
                    document.body.appendChild(iframe);
                    setTimeout(function() { iframe.remove(); }, 60000);
                    return null;
                }
                return response.json();
            })
            .then(function(data) {
                if (!data) {
                    isNavigating = false;
                    return;
                }

                isNavigating = false;

                // Full HTML fallback (middleware didn't intercept)
                if (data._fullHtml) {
                    return fadeOut(document.body, 80).then(function() {
                        replaceDocument(data._fullHtml, url);
                    });
                }

                // Handle redirect
                if (data.type === 'redirect') {
                    navigate(data.url);
                    return;
                }

                // Handle download
                if (data.type === 'download') {
                    var iframe = document.createElement('iframe');
                    iframe.style.display = 'none';
                    iframe.src = data.url;
                    document.body.appendChild(iframe);
                    setTimeout(function() { iframe.remove(); }, 60000);
                    return;
                }

                // Store URL for layout-switch fallback
                data._url = url;

                var targetLayout = data.layout;
                var injectionPromise;

                // Same layout — swap content in place
                if (targetLayout === currentLayout) {
                    if (targetLayout === 'app') {
                        injectionPromise = injectAppContent(data);
                    } else if (targetLayout === 'auth') {
                        injectionPromise = injectAuthContent(data);
                    } else if (targetLayout === 'classic') {
                        injectionPromise = injectClassicContent(data);
                    } else {
                        injectionPromise = fullPageSwitch(data);
                    }
                } else {
                    // Different layout — full client-side page replacement (no browser nav)
                    injectionPromise = fullPageSwitch(data);
                    // After fullPageSwitch, further state updates happen inside replaceDocument
                    return injectionPromise;
                }

                // Keep title fixed and URL synced to current page
                document.title = FIXED_TITLE;
                // Track current logical URL for same-page detection
                currentLogicalUrl = url;
                history.pushState({ spa: true, url: url }, '', currentLogicalUrl);
                historyStack.push(url);
                checkDashboardFloor(url);

                // Update active nav link
                updateActiveNavLink(url);

                // Dispatch event for other scripts
                document.dispatchEvent(new CustomEvent('spa:navigation', {
                    detail: { url: url, layout: targetLayout }
                }));
            })
            .catch(function(error) {
                if (error.name === 'AbortError') return;
                console.error('[SPA] Navigation error:', error);
                isNavigating = false;
                // Fallback: use location.replace so no new history entry
                if (method === 'GET') {
                    window.location.replace(url);
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
            anchor.dataset.bsToggle ||
            e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) {
            return;
        }

        if (isExternalUrl(href)) return;
        if (isDownloadUrl(href)) {
            // Trigger download without changing URL
            e.preventDefault();
            var iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = href;
            document.body.appendChild(iframe);
            setTimeout(function() { iframe.remove(); }, 60000);
            return;
        }

        e.preventDefault();
        navigate(href);
    });

    // Intercept form submissions
    document.addEventListener('submit', function(e) {
        var form = e.target;
        var action = form.getAttribute('action') || currentLogicalUrl;

        // Skip forms with special handling
        if (form.classList.contains('no-spa') ||
            form.classList.contains('download-form') ||
            form.querySelector('button[type="submit"].btn-download')) {
            return;
        }

        // Skip forms with actual file uploads
        if (form.querySelector('input[type=file]')) {
            var hasFiles = false;
            var fileInputs = form.querySelectorAll('input[type=file]');
            for (var i = 0; i < fileInputs.length; i++) {
                if (fileInputs[i].files && fileInputs[i].files.length > 0) {
                    hasFiles = true;
                    break;
                }
            }
            if (hasFiles) {
                // Fix action for forms without explicit action — browser would use
                // the locked SPA URL instead of the actual page URL
                if (!form.getAttribute('action')) {
                    form.setAttribute('action', currentLogicalUrl);
                }
                return;
            }
        }

        if (isDownloadUrl(action)) {
            if (!form.getAttribute('action')) form.setAttribute('action', currentLogicalUrl);
            return;
        }
        if (isExternalUrl(action)) return;
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
                body: formData
            });
        }
    });

    // Handle browser back/forward
    window.addEventListener('popstate', function(e) {
        var url = window.location.pathname + window.location.search;
        var state = e.state || {};

        // Dashboard floor enforcement:
        // If user pressed back and landed on dashboard (or before it),
        // and our history stack says dashboard is the bottom, stay on dashboard.
        if (historyStack.length <= 1 || (currentLogicalUrl === DASHBOARD_URL && url !== currentLogicalUrl)) {
            // User is trying to go back past dashboard — block it
            history.pushState({ spa: true, url: DASHBOARD_URL, dashboardFloor: true }, '', DASHBOARD_URL);
            currentLogicalUrl = DASHBOARD_URL;
            return;
        }

        // If landed on a pre-auth page, redirect to dashboard
        if (url === '/' || url === '/accounts/login/' || url === '/login/') {
            history.replaceState({ spa: true, url: DASHBOARD_URL }, '', DASHBOARD_URL);
            url = DASHBOARD_URL;
            historyStack = [DASHBOARD_URL];
        }

        if (url !== currentLogicalUrl) {
            // Pop from our stack if going back
            if (historyStack.length > 1 && historyStack[historyStack.length - 2] === url) {
                historyStack.pop();
            }
            currentLogicalUrl = url;
            // Use originalNavigate to avoid pushState (browser already updated the URL)
            isNavigating = true;

            var csrfToken = '';
            var match = document.cookie.match(/csrftoken=([^;]+)/);
            if (match) csrfToken = match[1];

            fetch(url, {
                method: 'GET',
                credentials: 'same-origin',
                headers: { 'X-SPA-Request': 'true' }
            })
            .then(function(response) {
                var contentType = response.headers.get('Content-Type') || '';
                if (contentType.indexOf('application/json') !== -1) {
                    return response.json();
                }
                return response.text().then(function(html) { return { _fullHtml: html }; });
            })
            .then(function(data) {
                isNavigating = false;
                if (!data) return;

                if (data._fullHtml) {
                    // Full page — replace document but DON'T push history (we're going back)
                    var doc = new DOMParser().parseFromString(data._fullHtml, 'text/html');
                    var oldHeadEls = document.querySelectorAll('head style, head link[rel="stylesheet"]');
                    var newHeadEls = doc.querySelectorAll('head style, head link[rel="stylesheet"]');
                    oldHeadEls.forEach(function(el) { el.remove(); });
                    newHeadEls.forEach(function(el) { document.head.appendChild(el.cloneNode(true)); });
                    document.body.innerHTML = doc.body.innerHTML;
                    executeInlineScripts(document.body);
                    document.title = FIXED_TITLE;
                    currentLayout = detectCurrentLayout();
                    window.scrollTo(0, 0);
                    return;
                }

                if (data.type === 'redirect') {
                    window.location.replace(data.url);
                    return;
                }

                data._url = url;
                var targetLayout = data.layout;

                if (targetLayout === currentLayout) {
                    if (targetLayout === 'app') {
                        injectAppContent(data);
                    } else if (targetLayout === 'auth') {
                        injectAuthContent(data);
                    } else if (targetLayout === 'classic') {
                        injectClassicContent(data);
                    } else {
                        // Replace without pushing history
                        var doc2 = new DOMParser().parseFromString('', 'text/html');
                        fetch(url, { method: 'GET', credentials: 'same-origin' })
                            .then(function(r) { return r.text(); })
                            .then(function(html) {
                                var d = new DOMParser().parseFromString(html, 'text/html');
                                var ohe = document.querySelectorAll('head style, head link[rel="stylesheet"]');
                                var nhe = d.querySelectorAll('head style, head link[rel="stylesheet"]');
                                ohe.forEach(function(el) { el.remove(); });
                                nhe.forEach(function(el) { document.head.appendChild(el.cloneNode(true)); });
                                document.body.innerHTML = d.body.innerHTML;
                                executeInlineScripts(document.body);
                                document.title = FIXED_TITLE;
                                currentLayout = detectCurrentLayout();
                                window.scrollTo(0, 0);
                            });
                    }
                } else {
                    // Cross-layout back: fetch full HTML and replace without pushing history
                    fetch(url, { method: 'GET', credentials: 'same-origin' })
                        .then(function(r) { return r.text(); })
                        .then(function(html) {
                            var d = new DOMParser().parseFromString(html, 'text/html');
                            var ohe = document.querySelectorAll('head style, head link[rel="stylesheet"]');
                            var nhe = d.querySelectorAll('head style, head link[rel="stylesheet"]');
                            ohe.forEach(function(el) { el.remove(); });
                            nhe.forEach(function(el) { document.head.appendChild(el.cloneNode(true)); });
                            document.body.innerHTML = d.body.innerHTML;
                            executeInlineScripts(document.body);
                            document.title = FIXED_TITLE;
                            currentLayout = detectCurrentLayout();
                            window.scrollTo(0, 0);
                        });
                }

                document.title = FIXED_TITLE;
                updateActiveNavLink(url);
            })
            .catch(function(error) {
                isNavigating = false;
                if (error.name !== 'AbortError') {
                    window.location.replace(url);
                }
            });
        }
    });

    // =========================================================================
    // INITIALIZATION
    // =========================================================================

    // Keep title fixed and preserve the current URL on initial load
    document.title = FIXED_TITLE;
    history.replaceState({ spa: true, url: currentLogicalUrl }, '', currentLogicalUrl);

    // If initial load is dashboard, set it as the floor
    if (currentLogicalUrl === DASHBOARD_URL || currentLogicalUrl === DASHBOARD_URL.replace(/\/$/, '')) {
        setDashboardFloor();
    }

    document.documentElement.setAttribute('data-spa', 'true');
    document.documentElement.setAttribute('data-spa-layout', currentLayout);

    // Export navigate function for programmatic use
    window.spaNavigate = navigate;

    // Expose the current logical URL (the actual page being viewed)
    Object.defineProperty(window, 'spaCurrentUrl', {
        get: function() { return currentLogicalUrl; }
    });

    // Global safe navigation helper — always avoids creating new history entries.
    // Use this everywhere instead of window.location.href = url
    window.safeNavigate = function(url) {
        if (window.spaNavigate) {
            window.spaNavigate(url);
        } else {
            window.location.replace(url);
        }
    };

    // =========================================================================
    // LINK PREFETCHING
    // =========================================================================

    var prefetchCache = {};
    var prefetchTimeout = null;
    var PREFETCH_TTL_MS = 15000;

    function getPrefetchEntry(url) {
        var entry = prefetchCache[url];
        if (!entry) return null;
        if (entry.status === 'ready' && Date.now() - entry.timestamp > PREFETCH_TTL_MS) {
            delete prefetchCache[url];
            return null;
        }
        return entry;
    }

    function prefetchUrl(url) {
        url = normalizeUrl(url);
        if (!url) return;

        // Skip if already prefetched or currently navigating
        var existingEntry = getPrefetchEntry(url);
        if (existingEntry || isNavigating) return;
        if (shouldBypass(url) || isDownloadUrl(url) || isExternalUrl(url)) return;
        if (url === currentLogicalUrl) return;

        // Use low-priority fetch
        var fetchOptions = {
            method: 'GET',
            credentials: 'same-origin',
            headers: { 'X-SPA-Request': 'true' },
            priority: 'low'
        };

        var prefetchPromise = fetch(url, fetchOptions)
            .then(function(response) {
                if (response.ok) {
                    var contentType = response.headers.get('Content-Type') || '';
                    if (contentType.indexOf('application/json') !== -1) {
                        return response.json();
                    }
                }
                return null;
            })
            .then(function(data) {
                if (data && data.type === 'content') {
                    prefetchCache[url] = {
                        status: 'ready',
                        data: data,
                        timestamp: Date.now()
                    };
                } else {
                    delete prefetchCache[url];
                }
            })
            .catch(function() {
                delete prefetchCache[url];
            });

        prefetchCache[url] = {
            status: 'pending',
            promise: prefetchPromise,
            timestamp: Date.now()
        };
    }

    // Prefetch on hover with small delay
    document.addEventListener('mouseover', function(e) {
        var link = e.target.closest('a[href]');
        if (!link) return;

        var href = link.getAttribute('href');
        if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;

        // Delay prefetch to avoid unnecessary requests on fast mouse movements
        clearTimeout(prefetchTimeout);
        prefetchTimeout = setTimeout(function() {
            prefetchUrl(href);
        }, 65);
    });

    // Also prefetch on touchstart for mobile
    document.addEventListener('touchstart', function(e) {
        var link = e.target.closest('a[href]');
        if (!link) return;

        var href = link.getAttribute('href');
        if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;

        prefetchUrl(href);
    }, { passive: true });

    // Use prefetched data when navigating
    var originalNavigate = navigate;
    navigate = function(url, options) {
        options = options || {};
        var method = (options.method || 'GET').toUpperCase();
        var normalizedUrl = normalizeUrl(url);
        if (normalizedUrl) {
            url = normalizedUrl;
        }

        // Only use prefetch cache for GET requests
        if (method === 'GET') {
            var entry = getPrefetchEntry(url);

            if (entry && entry.status === 'pending' && entry.promise) {
                // Do not block user click on an in-flight prefetch.
                // Fire normal navigation immediately for snappier group switching.
                return originalNavigate(url, options);
            }

            if (entry && entry.status === 'ready' && entry.data) {
                var data = entry.data;

                // Skip if same page
                if (url === currentLogicalUrl) return;

                isNavigating = true;
                isNavigating = false;

                data._url = url;
                var targetLayout = data.layout;
                var injectionPromise;

                if (targetLayout === currentLayout) {
                    if (targetLayout === 'app') {
                        injectionPromise = injectAppContent(data);
                    } else if (targetLayout === 'auth') {
                        injectionPromise = injectAuthContent(data);
                    } else if (targetLayout === 'classic') {
                        injectionPromise = injectClassicContent(data);
                    } else {
                        injectionPromise = fullPageSwitch(data);
                    }
                } else {
                    fullPageSwitch(data);
                    return;
                }

                document.title = FIXED_TITLE;
                currentLogicalUrl = url;
                history.pushState({ spa: true, url: url }, '', currentLogicalUrl);
                historyStack.push(url);
                checkDashboardFloor(url);
                updateActiveNavLink(url);
                document.dispatchEvent(new CustomEvent('spa:navigation', {
                    detail: { url: url, layout: targetLayout }
                }));
                return;
            }
        }

        return originalNavigate(url, options);
    };

    console.log('[SPA] Router initialized, layout:', currentLayout, ', URL:', currentLogicalUrl);

})();

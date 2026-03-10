/**
 * Prevent internal navigations from creating separate browser history entries.
 * Uses location.replace() for link clicks and form submissions so only
 * the initial site entry remains in browser history.
 */
(function(){
    // Intercept internal link clicks
    document.addEventListener('click', function(e){
        var a = e.target.closest('a');
        if (!a) return;
        var h = a.getAttribute('href');
        if (!h) return;
        // Skip: anchors, javascript:, external, new-tab, download, modifier keys
        if (h.charAt(0)==='#' || h.startsWith('javascript:') ||
            a.target==='_blank' || a.hasAttribute('download') ||
            e.ctrlKey || e.metaKey || e.shiftKey) return;
        // Only intercept same-origin links
        if (h.startsWith('/') || h.startsWith(location.origin)) {
            e.preventDefault();
            location.replace(h);
        }
    });

    // Intercept form submissions
    document.addEventListener('submit', function(e){
        var f = e.target;
        // Use getAttribute to avoid name collision with inputs named 'action'
        var action = f.getAttribute('action') || location.href;
        // Skip forms with file uploads or external actions
        if (f.querySelector('input[type=file]')) return;
        try { if (new URL(action, location.origin).origin !== location.origin) return; } catch(x){ return; }

        e.preventDefault();
        var method = (f.method || 'GET').toUpperCase();

        if (method === 'GET') {
            var params = new URLSearchParams(new FormData(f)).toString();
            var url = action.split('?')[0] + (params ? '?' + params : '');
            location.replace(url);
            return;
        }
        // POST: submit via fetch, then replace to the redirect destination
        fetch(action, {
            method: 'POST',
            body: new FormData(f),
            credentials: 'same-origin'
        }).then(function(r){ location.replace(r.url); })
          .catch(function(){ f.submit(); });
    });
})();

(function () {
    'use strict';

    function getCsrfToken(form) {
        if (form) {
            var inp = form.querySelector('[name=csrfmiddlewaretoken]');
            if (inp && inp.value) return inp.value;
        }
        var any = document.querySelector('[name=csrfmiddlewaretoken]');
        return any ? any.value : '';
    }

    function parseFilename(disposition, fallback) {
        if (!disposition) return fallback;
        var m = disposition.match(/filename\*=UTF-8''([^;]+)/i);
        if (m && m[1]) {
            try { return decodeURIComponent(m[1]); } catch (e) { /* fall through */ }
        }
        m = disposition.match(/filename="?([^";\n]+)"?/i);
        return (m && m[1]) ? m[1] : fallback;
    }

    function showError(message) {
        try {
            if (typeof window.showSmoothDownloadError === 'function') {
                window.showSmoothDownloadError(message);
                return;
            }
        } catch (e) { /* ignore */ }
        alert(message || 'Download failed. Please try again.');
    }

    function setBusy(button, busy, originalHTML) {
        if (!button) return originalHTML;
        if (busy) {
            var html = button.innerHTML;
            button.disabled = true;
            button.dataset._origHTML = html;
            button.innerHTML = '<i class="bi bi-hourglass-split"></i> Generating...';
            return html;
        } else {
            button.disabled = false;
            if (button.dataset._origHTML !== undefined) {
                button.innerHTML = button.dataset._origHTML;
                delete button.dataset._origHTML;
            } else if (originalHTML !== undefined) {
                button.innerHTML = originalHTML;
            }
        }
    }

    /**
     * smoothDownload(formOrSpec, opts)
     *   formOrSpec: a <form> element OR { url, formData, method }
     *   opts:
     *     button:    button element to show "Generating..." state on
     *     fallbackName: default filename if Content-Disposition missing
     */
    window.smoothDownload = function (formOrSpec, opts) {
        opts = opts || {};
        var url, method, formData, formEl = null;

        if (formOrSpec && formOrSpec.tagName === 'FORM') {
            formEl = formOrSpec;
            url = formEl.getAttribute('action') || window.location.href;
            method = (formEl.getAttribute('method') || 'POST').toUpperCase();
            formData = new FormData(formEl);
        } else if (formOrSpec && typeof formOrSpec === 'object') {
            url = formOrSpec.url;
            method = (formOrSpec.method || 'POST').toUpperCase();
            formData = formOrSpec.formData || new FormData();
        } else {
            return Promise.reject(new Error('smoothDownload: invalid input'));
        }

        var csrf = getCsrfToken(formEl);
        if (csrf && method !== 'GET' && !formData.has('csrfmiddlewaretoken')) {
            formData.append('csrfmiddlewaretoken', csrf);
        }

        var button = opts.button || null;
        setBusy(button, true);

        var fetchOpts = {
            method: method,
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' }
        };
        if (method !== 'GET') fetchOpts.body = formData;

        return fetch(url, fetchOpts)
            .then(function (response) {
                if (!response.ok) {
                    return response.text().then(function (txt) {
                        var msg = 'Download failed (' + response.status + ').';
                        if (txt && txt.length < 500) msg += ' ' + txt;
                        throw new Error(msg);
                    });
                }
                var disposition = response.headers.get('Content-Disposition') || '';
                var filename = parseFilename(disposition, opts.fallbackName || 'download');
                return response.blob().then(function (blob) {
                    return { blob: blob, filename: filename };
                });
            })
            .then(function (result) {
                var blobUrl = window.URL.createObjectURL(result.blob);
                var a = document.createElement('a');
                a.href = blobUrl;
                a.download = result.filename;
                a.style.display = 'none';
                document.body.appendChild(a);
                a.click();
                setTimeout(function () {
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(blobUrl);
                }, 100);
                setBusy(button, false);
            })
            .catch(function (err) {
                console.error('smoothDownload error:', err);
                setBusy(button, false);
                showError(err && err.message ? err.message : 'Download failed. Please try again.');
                throw err;
            });
    };
})();

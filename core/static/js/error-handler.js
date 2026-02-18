/**
 * Hamsvic Unified UI Feedback System
 * Replaces ALL browser-native dialogs (alert, confirm, prompt) with custom UI.
 * Provides: toast notifications, confirmation modals, input modals,
 * session expired modal, payment failure modal, network offline detection,
 * global error boundary, and centralized API wrapper.
 */

(function(window) {
    'use strict';

    const HamsvicErrors = {
        /**
         * Show a toast notification
         * @param {string} message
         * @param {string} type - 'success', 'error', 'warning', 'info'
         * @param {number} duration - ms, default 4000
         */
        showToast: function(message, type = 'info', duration = 4000) {
            const toastContainer = this._getToastContainer();
            const toast = document.createElement('div');
            toast.className = `hamsvic-toast hamsvic-toast-${type}`;
            toast.setAttribute('role', 'alert');
            toast.setAttribute('aria-live', 'assertive');

            const icons = {
                success: '<i class="bi bi-check-circle-fill"></i>',
                error: '<i class="bi bi-exclamation-circle-fill"></i>',
                warning: '<i class="bi bi-exclamation-triangle-fill"></i>',
                info: '<i class="bi bi-info-circle-fill"></i>'
            };

            toast.innerHTML = `
                <div class="hamsvic-toast-icon">${icons[type] || icons.info}</div>
                <div class="hamsvic-toast-msg">${this._escapeHtml(message)}</div>
                <button class="hamsvic-toast-close" aria-label="Close notification">
                    <i class="bi bi-x"></i>
                </button>
            `;

            toast.querySelector('.hamsvic-toast-close').addEventListener('click', function() {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            });

            toastContainer.appendChild(toast);
            requestAnimationFrame(() => {
                requestAnimationFrame(() => toast.classList.add('show'));
            });

            if (duration > 0) {
                setTimeout(() => {
                    if (toast.parentElement) {
                        toast.classList.remove('show');
                        setTimeout(() => toast.remove(), 300);
                    }
                }, duration);
            }
            return toast;
        },

        /**
         * Show a confirmation modal (replaces confirm())
         * @param {Object} opts
         * @param {string} opts.title - Modal title
         * @param {string} opts.message - Body text
         * @param {string} opts.confirmText - Confirm button text (default 'Confirm')
         * @param {string} opts.cancelText - Cancel button text (default 'Cancel')
         * @param {string} opts.type - 'danger', 'warning', 'info' (default 'danger')
         * @param {string} opts.icon - Bootstrap icon class
         * @returns {Promise<boolean>}
         */
        showConfirm: function(opts = {}) {
            return new Promise((resolve) => {
                const type = opts.type || 'danger';
                const colors = {
                    danger: { bg: 'linear-gradient(135deg, #fee2e2, #fecaca)', icon: '#ef4444', title: '#991b1b', btn: 'linear-gradient(135deg, #ef4444, #dc2626)' },
                    warning: { bg: 'linear-gradient(135deg, #fef3c7, #fde68a)', icon: '#f59e0b', title: '#92400e', btn: 'linear-gradient(135deg, #f59e0b, #d97706)' },
                    info: { bg: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', icon: '#3b82f6', title: '#1e40af', btn: 'linear-gradient(135deg, #3b82f6, #2563eb)' }
                };
                const c = colors[type] || colors.danger;
                const iconClass = opts.icon || (type === 'danger' ? 'bi-exclamation-triangle-fill' : type === 'warning' ? 'bi-question-circle-fill' : 'bi-info-circle-fill');

                const overlay = document.createElement('div');
                overlay.className = 'hamsvic-modal-overlay';
                overlay.setAttribute('role', 'dialog');
                overlay.setAttribute('aria-modal', 'true');
                overlay.innerHTML = `
                    <div class="hamsvic-modal hamsvic-modal-confirm">
                        <div class="hamsvic-modal-header" style="background:${c.bg};">
                            <i class="bi ${iconClass}" style="font-size:2.5rem;color:${c.icon};display:block;margin-bottom:12px;"></i>
                            <h3 style="margin:0;color:${c.title};font-size:1.2rem;font-weight:600;">${this._escapeHtml(opts.title || 'Confirm Action')}</h3>
                        </div>
                        <div class="hamsvic-modal-body">
                            <p>${this._escapeHtml(opts.message || 'Are you sure?')}</p>
                        </div>
                        <div class="hamsvic-modal-footer">
                            <button class="hamsvic-btn hamsvic-btn-cancel">${this._escapeHtml(opts.cancelText || 'Cancel')}</button>
                            <button class="hamsvic-btn hamsvic-btn-confirm" style="background:${c.btn};color:white;">${this._escapeHtml(opts.confirmText || 'Confirm')}</button>
                        </div>
                    </div>
                `;

                const close = (result) => {
                    overlay.classList.remove('show');
                    setTimeout(() => { overlay.remove(); resolve(result); }, 300);
                };

                overlay.querySelector('.hamsvic-btn-cancel').addEventListener('click', () => close(false));
                overlay.querySelector('.hamsvic-btn-confirm').addEventListener('click', () => close(true));
                overlay.addEventListener('click', (e) => { if (e.target === overlay) close(false); });
                overlay.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(false); });

                document.body.appendChild(overlay);
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => overlay.classList.add('show'));
                });
                overlay.querySelector('.hamsvic-btn-confirm').focus();
            });
        },

        /**
         * Show an input modal (replaces prompt())
         * @param {Object} opts
         * @param {string} opts.title
         * @param {string} opts.message
         * @param {string} opts.placeholder
         * @param {string} opts.defaultValue
         * @param {string} opts.confirmText
         * @returns {Promise<string|null>}
         */
        showPrompt: function(opts = {}) {
            return new Promise((resolve) => {
                const overlay = document.createElement('div');
                overlay.className = 'hamsvic-modal-overlay';
                overlay.setAttribute('role', 'dialog');
                overlay.setAttribute('aria-modal', 'true');
                overlay.innerHTML = `
                    <div class="hamsvic-modal hamsvic-modal-prompt">
                        <div class="hamsvic-modal-header" style="background:linear-gradient(135deg, #dbeafe, #bfdbfe);">
                            <i class="bi bi-pencil-square" style="font-size:2.5rem;color:#3b82f6;display:block;margin-bottom:12px;"></i>
                            <h3 style="margin:0;color:#1e40af;font-size:1.2rem;font-weight:600;">${this._escapeHtml(opts.title || 'Enter Value')}</h3>
                        </div>
                        <div class="hamsvic-modal-body">
                            ${opts.message ? `<p style="margin-bottom:1rem;">${this._escapeHtml(opts.message)}</p>` : ''}
                            <input type="text" class="hamsvic-modal-input" placeholder="${this._escapeHtml(opts.placeholder || '')}" value="${this._escapeHtml(opts.defaultValue || '')}">
                            <div class="hamsvic-input-error" style="display:none;color:#ef4444;font-size:0.8rem;margin-top:6px;"></div>
                        </div>
                        <div class="hamsvic-modal-footer">
                            <button class="hamsvic-btn hamsvic-btn-cancel">Cancel</button>
                            <button class="hamsvic-btn hamsvic-btn-confirm" style="background:linear-gradient(135deg, #4f46e5, #6366f1);color:white;">${this._escapeHtml(opts.confirmText || 'OK')}</button>
                        </div>
                    </div>
                `;

                const input = overlay.querySelector('.hamsvic-modal-input');
                const errorEl = overlay.querySelector('.hamsvic-input-error');

                const close = (value) => {
                    overlay.classList.remove('show');
                    setTimeout(() => { overlay.remove(); resolve(value); }, 300);
                };

                const submit = () => {
                    const val = input.value.trim();
                    if (opts.required !== false && !val) {
                        errorEl.textContent = 'This field is required';
                        errorEl.style.display = 'block';
                        input.classList.add('error');
                        input.focus();
                        return;
                    }
                    close(val);
                };

                overlay.querySelector('.hamsvic-btn-cancel').addEventListener('click', () => close(null));
                overlay.querySelector('.hamsvic-btn-confirm').addEventListener('click', submit);
                input.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit(); });
                input.addEventListener('input', () => { errorEl.style.display = 'none'; input.classList.remove('error'); });
                overlay.addEventListener('click', (e) => { if (e.target === overlay) close(null); });
                overlay.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(null); });

                document.body.appendChild(overlay);
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => overlay.classList.add('show'));
                });
                input.focus();
                input.select();
            });
        },

        /**
         * Show error modal for serious errors
         */
        showErrorModal: function(title, message, options = {}) {
            const headerStyle = options.headerStyle || 'error';
            const styles = {
                error: { bg: 'linear-gradient(135deg, #fee2e2, #fecaca)', icon: '#ef4444', title: '#991b1b', iconClass: 'bi-exclamation-circle' },
                warning: { bg: 'linear-gradient(135deg, #fef3c7, #fde68a)', icon: '#f59e0b', title: '#92400e', iconClass: 'bi-exclamation-triangle' },
                info: { bg: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', icon: '#3b82f6', title: '#1e40af', iconClass: 'bi-info-circle' }
            };
            const s = styles[headerStyle] || styles.error;

            const overlay = document.createElement('div');
            overlay.className = 'hamsvic-modal-overlay';
            overlay.setAttribute('role', 'alertdialog');
            overlay.setAttribute('aria-modal', 'true');
            overlay.innerHTML = `
                <div class="hamsvic-modal">
                    <div class="hamsvic-modal-header" style="background:${s.bg};">
                        <i class="bi ${options.icon || s.iconClass}" style="font-size:2.5rem;color:${s.icon};display:block;margin-bottom:12px;"></i>
                        <h3 style="margin:0;color:${s.title};font-size:1.2rem;font-weight:600;">${this._escapeHtml(title)}</h3>
                    </div>
                    <div class="hamsvic-modal-body">
                        <p>${this._escapeHtml(message)}</p>
                        ${options.details ? `<details style="margin-top:12px;"><summary style="cursor:pointer;color:#6b7280;font-size:0.85rem;">Technical Details</summary><pre style="margin:8px 0 0;font-size:0.75rem;color:#6b7280;white-space:pre-wrap;background:#f3f4f6;padding:12px;border-radius:8px;">${this._escapeHtml(options.details)}</pre></details>` : ''}
                    </div>
                    <div class="hamsvic-modal-footer">
                        ${options.retryAction ? `<button class="hamsvic-btn hamsvic-btn-confirm" style="background:linear-gradient(135deg,#4f46e5,#6366f1);color:white;" data-action="${this._escapeHtml(options.retryAction)}">Try Again</button>` : ''}
                        <button class="hamsvic-btn hamsvic-btn-cancel">${options.closeText || 'Close'}</button>
                    </div>
                </div>
            `;

            const close = () => {
                overlay.classList.remove('show');
                setTimeout(() => overlay.remove(), 300);
            };

            overlay.querySelector('.hamsvic-btn-cancel').addEventListener('click', close);
            overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
            overlay.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });

            const retryBtn = overlay.querySelector('[data-action]');
            if (retryBtn) {
                retryBtn.addEventListener('click', () => {
                    const action = retryBtn.dataset.action;
                    close();
                    if (typeof window[action] === 'function') window[action]();
                });
            }

            document.body.appendChild(overlay);
            requestAnimationFrame(() => {
                requestAnimationFrame(() => overlay.classList.add('show'));
            });
        },

        /**
         * Show session expired modal
         */
        showSessionExpired: function(message) {
            const overlay = document.createElement('div');
            overlay.className = 'hamsvic-modal-overlay';
            overlay.setAttribute('role', 'alertdialog');
            overlay.innerHTML = `
                <div class="hamsvic-modal">
                    <div class="hamsvic-modal-header" style="background:linear-gradient(135deg, #fee2e2, #fecaca);">
                        <i class="bi bi-clock-history" style="font-size:2.5rem;color:#ef4444;display:block;margin-bottom:12px;"></i>
                        <h3 style="margin:0;color:#991b1b;font-size:1.2rem;font-weight:600;">Session Expired</h3>
                    </div>
                    <div class="hamsvic-modal-body">
                        <p>${this._escapeHtml(message || 'Your session has expired. Please log in again to continue.')}</p>
                    </div>
                    <div class="hamsvic-modal-footer" style="justify-content:center;">
                        <button class="hamsvic-btn hamsvic-btn-confirm" style="background:linear-gradient(135deg, #4f46e5, #6366f1);color:white;width:100%;">
                            <i class="bi bi-box-arrow-in-right" style="margin-right:8px;"></i>Login Again
                        </button>
                    </div>
                </div>
            `;

            overlay.querySelector('.hamsvic-btn-confirm').addEventListener('click', () => {
                window.location.href = '/accounts/login/';
            });

            document.body.appendChild(overlay);
            requestAnimationFrame(() => {
                requestAnimationFrame(() => overlay.classList.add('show'));
            });
        },

        /**
         * Show payment failure modal
         */
        showPaymentFailure: function(message, retryFn) {
            const overlay = document.createElement('div');
            overlay.className = 'hamsvic-modal-overlay';
            overlay.setAttribute('role', 'alertdialog');
            overlay.innerHTML = `
                <div class="hamsvic-modal">
                    <div class="hamsvic-modal-header" style="background:linear-gradient(135deg, #fef3c7, #fde68a);">
                        <i class="bi bi-credit-card-2-back" style="font-size:2.5rem;color:#f59e0b;display:block;margin-bottom:12px;"></i>
                        <h3 style="margin:0;color:#92400e;font-size:1.2rem;font-weight:600;">Payment Failed</h3>
                    </div>
                    <div class="hamsvic-modal-body">
                        <p>${this._escapeHtml(message || 'Your payment could not be processed. Please try again or use a different payment method.')}</p>
                    </div>
                    <div class="hamsvic-modal-footer">
                        <button class="hamsvic-btn hamsvic-btn-cancel">Cancel</button>
                        <button class="hamsvic-btn hamsvic-btn-confirm" style="background:linear-gradient(135deg, #4f46e5, #6366f1);color:white;">
                            <i class="bi bi-arrow-clockwise" style="margin-right:8px;"></i>Retry Payment
                        </button>
                    </div>
                </div>
            `;

            const close = () => {
                overlay.classList.remove('show');
                setTimeout(() => overlay.remove(), 300);
            };

            overlay.querySelector('.hamsvic-btn-cancel').addEventListener('click', close);
            overlay.querySelector('.hamsvic-btn-confirm').addEventListener('click', () => {
                close();
                if (typeof retryFn === 'function') retryFn();
            });
            overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });

            document.body.appendChild(overlay);
            requestAnimationFrame(() => {
                requestAnimationFrame(() => overlay.classList.add('show'));
            });
        },

        /**
         * Show network offline indicator
         */
        showOffline: function() {
            if (document.getElementById('hamsvic-offline-bar')) return;
            const bar = document.createElement('div');
            bar.id = 'hamsvic-offline-bar';
            bar.setAttribute('role', 'alert');
            bar.innerHTML = `
                <i class="bi bi-wifi-off"></i>
                <span>You are offline. Some features may not work.</span>
            `;
            document.body.appendChild(bar);
            requestAnimationFrame(() => {
                requestAnimationFrame(() => bar.classList.add('show'));
            });
        },

        hideOffline: function() {
            const bar = document.getElementById('hamsvic-offline-bar');
            if (bar) {
                bar.classList.remove('show');
                setTimeout(() => bar.remove(), 300);
                this.showToast('You are back online', 'success', 3000);
            }
        },

        /**
         * Handle AJAX errors consistently
         */
        handleAjaxError: function(xhr, context, options = {}) {
            let message = 'An unexpected error occurred.';
            let type = 'error';

            if (xhr.responseJSON) {
                message = xhr.responseJSON.reason || xhr.responseJSON.error || xhr.responseJSON.message || message;
            } else if (xhr.status) {
                switch (xhr.status) {
                    case 400:
                        message = 'Invalid request. Please check your input.';
                        break;
                    case 401:
                        this.showSessionExpired();
                        return;
                    case 403:
                        message = 'You do not have permission to perform this action.';
                        break;
                    case 404:
                        message = 'The requested resource was not found.';
                        break;
                    case 429:
                        message = 'Too many requests. Please wait a moment and try again.';
                        type = 'warning';
                        break;
                    case 500:
                        message = 'A server error occurred. Our team has been notified.';
                        break;
                    case 502: case 503: case 504:
                        message = 'The server is temporarily unavailable. Please try again.';
                        type = 'warning';
                        break;
                    default:
                        if (xhr.status >= 400 && xhr.status < 500) message = 'There was a problem with your request.';
                        else if (xhr.status >= 500) message = 'A server error occurred.';
                }
            }

            const fullMessage = context ? `Error ${context}: ${message}` : message;

            if (options.useModal || xhr.status === 500) {
                this.showErrorModal('Something Went Wrong', fullMessage, {
                    details: options.showDetails ? `Status: ${xhr.status}\nURL: ${xhr.url || 'unknown'}` : null,
                    retryAction: options.retryAction
                });
            } else {
                this.showToast(fullMessage, type);
            }

            console.error(`[Hamsvic] ${fullMessage}`, xhr);
        },

        /**
         * Handle fetch API errors
         */
        handleFetchError: async function(response, context) {
            let errorData = { status: response.status };
            try { errorData.responseJSON = await response.json(); } catch (e) {}
            this.handleAjaxError(errorData, context);
        },

        /**
         * Centralized API wrapper with interceptors
         * @param {string} url
         * @param {Object} options - fetch options
         * @param {string} context - context for error messages
         * @returns {Promise<Object>}
         */
        fetchWithErrorHandling: async function(url, options = {}, context = '') {
            try {
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
                const headers = {
                    'X-Requested-With': 'XMLHttpRequest',
                    ...options.headers
                };
                if (csrfToken && options.method && options.method !== 'GET') {
                    headers['X-CSRFToken'] = csrfToken.value;
                }

                const response = await fetch(url, { ...options, headers });

                if (response.status === 401) {
                    this.showSessionExpired();
                    throw new Error('HTTP 401');
                }

                if (!response.ok) {
                    await this.handleFetchError(response, context);
                    throw new Error(`HTTP ${response.status}`);
                }

                const contentType = response.headers.get('Content-Type') || '';
                if (contentType.includes('application/json')) {
                    return await response.json();
                }
                return response;
            } catch (error) {
                if (error.message.startsWith('HTTP')) throw error;
                if (!navigator.onLine) {
                    this.showOffline();
                } else {
                    this.showToast('Network error. Please check your connection.', 'error');
                }
                throw error;
            }
        },

        /**
         * Show a loading indicator
         */
        showLoading: function(message = 'Loading...') {
            const overlay = document.createElement('div');
            overlay.className = 'hamsvic-loading-overlay';
            overlay.innerHTML = `
                <div class="hamsvic-loading-content">
                    <div class="hamsvic-spinner"></div>
                    <p>${this._escapeHtml(message)}</p>
                </div>
            `;
            document.body.appendChild(overlay);
            requestAnimationFrame(() => {
                requestAnimationFrame(() => overlay.classList.add('show'));
            });
            return {
                hide: () => {
                    overlay.classList.remove('show');
                    setTimeout(() => overlay.remove(), 300);
                },
                updateMessage: (newMessage) => {
                    overlay.querySelector('p').textContent = newMessage;
                }
            };
        },

        // ---- Private helpers ----
        _getToastContainer: function() {
            let container = document.getElementById('hamsvic-toast-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'hamsvic-toast-container';
                container.setAttribute('aria-live', 'polite');
                document.body.appendChild(container);
            }
            return container;
        },

        _escapeHtml: function(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = String(text);
            return div.innerHTML;
        }
    };

    // =========================================================================
    // Override browser-native dialogs globally
    // =========================================================================
    window.alert = function(message) {
        HamsvicErrors.showToast(String(message), 'info');
    };

    window.confirm = function() {
        console.warn('[Hamsvic] Native confirm() is disabled. Use HamsvicErrors.showConfirm() instead.');
        return false;
    };

    window.prompt = function() {
        console.warn('[Hamsvic] Native prompt() is disabled. Use HamsvicErrors.showPrompt() instead.');
        return null;
    };

    // =========================================================================
    // Global error handlers
    // =========================================================================
    window.addEventListener('unhandledrejection', function(event) {
        console.error('[Hamsvic] Unhandled promise rejection:', event.reason);
        const msg = event.reason && event.reason.message ? event.reason.message : 'An unexpected error occurred.';
        if (!msg.startsWith('HTTP')) {
            HamsvicErrors.showToast(msg, 'error');
        }
    });

    window.addEventListener('error', function(event) {
        console.error('[Hamsvic] Uncaught error:', event.error || event.message);
        // Avoid spamming for script loading errors
        if (event.filename && !event.filename.includes(window.location.origin)) return;
        if (event.message && !event.message.includes('Script error')) {
            HamsvicErrors.showToast('An unexpected error occurred. Please refresh.', 'error');
        }
    });

    // =========================================================================
    // Network online/offline detection
    // =========================================================================
    window.addEventListener('offline', function() {
        HamsvicErrors.showOffline();
    });

    window.addEventListener('online', function() {
        HamsvicErrors.hideOffline();
    });

    // =========================================================================
    // Disable HTML5 default form validation globally
    // =========================================================================
    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('form:not([data-allow-validation])').forEach(function(form) {
            form.setAttribute('novalidate', '');
        });
    });

    // =========================================================================
    // Confirmation modal helper for forms with data-confirm attribute
    // Usage: <form data-confirm="Are you sure?"> or
    //        <button data-confirm="Delete this item?" data-confirm-title="Delete">
    // =========================================================================
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('[data-confirm]');
        if (!btn) return;

        // Only intercept if not already handled
        if (btn._hamsvicConfirming) return;

        const form = btn.closest('form');
        const message = btn.dataset.confirm;
        const title = btn.dataset.confirmTitle || 'Confirm Action';
        const type = btn.dataset.confirmType || 'danger';

        e.preventDefault();
        e.stopPropagation();

        HamsvicErrors.showConfirm({ title: title, message: message, type: type, confirmText: btn.dataset.confirmOk || 'Confirm' }).then(function(confirmed) {
            if (confirmed) {
                if (form) {
                    btn._hamsvicConfirming = true;
                    form.submit();
                } else if (btn.tagName === 'A') {
                    window.location.href = btn.href;
                }
            }
        });
    }, true);

    // =========================================================================
    // Inject Styles
    // =========================================================================
    const style = document.createElement('style');
    style.textContent = `
        /* Toast Container */
        #hamsvic-toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 99999;
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-width: 400px;
            pointer-events: none;
        }
        @media (max-width: 480px) {
            #hamsvic-toast-container { right: 10px; left: 10px; max-width: none; }
        }

        .hamsvic-toast {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 14px 16px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 30px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.08);
            transform: translateX(110%);
            opacity: 0;
            transition: transform 0.35s cubic-bezier(0.21,1.02,0.73,1), opacity 0.3s ease;
            pointer-events: auto;
            border-left: 4px solid #6366f1;
        }
        .hamsvic-toast.show { transform: translateX(0); opacity: 1; }
        .hamsvic-toast-success { border-left-color: #10b981; }
        .hamsvic-toast-error { border-left-color: #ef4444; }
        .hamsvic-toast-warning { border-left-color: #f59e0b; }
        .hamsvic-toast-info { border-left-color: #6366f1; }

        .hamsvic-toast-icon { font-size: 1.2rem; flex-shrink: 0; line-height: 1; }
        .hamsvic-toast-success .hamsvic-toast-icon { color: #10b981; }
        .hamsvic-toast-error .hamsvic-toast-icon { color: #ef4444; }
        .hamsvic-toast-warning .hamsvic-toast-icon { color: #f59e0b; }
        .hamsvic-toast-info .hamsvic-toast-icon { color: #6366f1; }

        .hamsvic-toast-msg { flex: 1; font-size: 0.88rem; color: #374151; line-height: 1.4; font-family: 'Inter', -apple-system, sans-serif; }
        .hamsvic-toast-close {
            background: none; border: none; color: #9ca3af; cursor: pointer; padding: 2px; font-size: 1.1rem; line-height: 1; flex-shrink: 0;
        }
        .hamsvic-toast-close:hover { color: #4b5563; }

        /* Modal Overlay */
        .hamsvic-modal-overlay {
            position: fixed; inset: 0;
            background: rgba(0,0,0,0.5);
            backdrop-filter: blur(4px);
            display: flex; align-items: center; justify-content: center;
            z-index: 100000;
            opacity: 0;
            transition: opacity 0.3s ease;
            padding: 1rem;
        }
        .hamsvic-modal-overlay.show { opacity: 1; }
        .hamsvic-modal-overlay.show .hamsvic-modal {
            transform: scale(1) translateY(0);
        }

        .hamsvic-modal {
            background: white;
            border-radius: 16px;
            max-width: 440px;
            width: 100%;
            overflow: hidden;
            box-shadow: 0 25px 60px rgba(0,0,0,0.25);
            transform: scale(0.9) translateY(20px);
            transition: transform 0.35s cubic-bezier(0.21,1.02,0.73,1);
        }

        .hamsvic-modal-header { padding: 24px 24px 20px; text-align: center; }
        .hamsvic-modal-body { padding: 20px 24px; }
        .hamsvic-modal-body p { margin: 0; color: #4b5563; line-height: 1.6; font-size: 0.95rem; }
        .hamsvic-modal-footer {
            padding: 16px 24px;
            background: #f9fafb;
            display: flex; justify-content: flex-end; gap: 10px;
            border-top: 1px solid #f3f4f6;
        }

        .hamsvic-btn {
            padding: 10px 20px;
            border-radius: 10px;
            border: none;
            font-weight: 500;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.2s;
            font-family: 'Inter', -apple-system, sans-serif;
        }
        .hamsvic-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        .hamsvic-btn:active { transform: translateY(0); }
        .hamsvic-btn-cancel { background: #f1f5f9; color: #475569; }
        .hamsvic-btn-cancel:hover { background: #e2e8f0; }

        /* Prompt Input */
        .hamsvic-modal-input {
            width: 100%;
            padding: 10px 14px;
            border: 2px solid #e2e8f0;
            border-radius: 10px;
            font-size: 0.95rem;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
            font-family: 'Inter', -apple-system, sans-serif;
        }
        .hamsvic-modal-input:focus {
            border-color: #6366f1;
            box-shadow: 0 0 0 3px rgba(99,102,241,0.15);
        }
        .hamsvic-modal-input.error {
            border-color: #ef4444;
            box-shadow: 0 0 0 3px rgba(239,68,68,0.15);
        }

        /* Loading Overlay */
        .hamsvic-loading-overlay {
            position: fixed; inset: 0;
            background: rgba(255,255,255,0.92);
            backdrop-filter: blur(4px);
            display: flex; align-items: center; justify-content: center;
            z-index: 100001;
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        .hamsvic-loading-overlay.show { opacity: 1; }
        .hamsvic-loading-content { text-align: center; }
        .hamsvic-spinner {
            width: 44px; height: 44px;
            border: 4px solid #e5e7eb;
            border-top-color: #6366f1;
            border-radius: 50%;
            animation: hamsvic-spin 0.8s linear infinite;
            margin: 0 auto 16px;
        }
        @keyframes hamsvic-spin { to { transform: rotate(360deg); } }
        .hamsvic-loading-content p {
            color: #6b7280; margin: 0; font-size: 0.95rem;
            font-family: 'Inter', -apple-system, sans-serif;
        }

        /* Offline Bar */
        #hamsvic-offline-bar {
            position: fixed; bottom: 0; left: 0; right: 0;
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: white;
            padding: 12px 20px;
            display: flex; align-items: center; justify-content: center; gap: 10px;
            font-size: 0.9rem; font-weight: 500;
            z-index: 100002;
            transform: translateY(100%);
            transition: transform 0.35s cubic-bezier(0.21,1.02,0.73,1);
            font-family: 'Inter', -apple-system, sans-serif;
        }
        #hamsvic-offline-bar.show { transform: translateY(0); }

        /* Legacy compat: old error modal overlay class */
        .hamsvic-error-modal-overlay { display: none !important; }
    `;
    document.head.appendChild(style);

    // Export
    window.HamsvicErrors = HamsvicErrors;

    // Alias for convenience in templates using showToast directly
    if (typeof window.showToast === 'undefined') {
        window.showToast = function(message, type, title, duration) {
            HamsvicErrors.showToast(message, type, duration);
        };
    }

})(window);

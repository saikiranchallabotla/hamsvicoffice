/**
 * Hamsvic Error Handler Utilities
 * Provides consistent error handling and user feedback for AJAX operations.
 */

(function(window) {
    'use strict';

    const HamsvicErrors = {
        /**
         * Show a toast notification to the user
         * @param {string} message - The message to display
         * @param {string} type - 'success', 'error', 'warning', 'info'
         * @param {number} duration - How long to show (ms), default 5000
         */
        showToast: function(message, type = 'info', duration = 5000) {
            const toastContainer = this._getToastContainer();
            
            const toast = document.createElement('div');
            toast.className = `hamsvic-toast hamsvic-toast-${type}`;
            
            const icons = {
                success: '<i class="bi bi-check-circle-fill"></i>',
                error: '<i class="bi bi-exclamation-circle-fill"></i>',
                warning: '<i class="bi bi-exclamation-triangle-fill"></i>',
                info: '<i class="bi bi-info-circle-fill"></i>'
            };
            
            toast.innerHTML = `
                <div class="toast-icon">${icons[type] || icons.info}</div>
                <div class="toast-message">${this._escapeHtml(message)}</div>
                <button class="toast-close" onclick="this.parentElement.remove()">
                    <i class="bi bi-x"></i>
                </button>
            `;
            
            toastContainer.appendChild(toast);
            
            // Trigger animation
            setTimeout(() => toast.classList.add('show'), 10);
            
            // Auto-remove
            if (duration > 0) {
                setTimeout(() => {
                    toast.classList.remove('show');
                    setTimeout(() => toast.remove(), 300);
                }, duration);
            }
            
            return toast;
        },

        /**
         * Show a modal error dialog for serious errors
         * @param {string} title - Modal title
         * @param {string} message - Error message
         * @param {Object} options - Additional options
         */
        showErrorModal: function(title, message, options = {}) {
            const modal = document.createElement('div');
            modal.className = 'hamsvic-error-modal-overlay';
            modal.innerHTML = `
                <div class="hamsvic-error-modal">
                    <div class="modal-header error">
                        <i class="bi bi-exclamation-circle"></i>
                        <h3>${this._escapeHtml(title)}</h3>
                    </div>
                    <div class="modal-body">
                        <p>${this._escapeHtml(message)}</p>
                        ${options.details ? `<details><summary>Technical Details</summary><pre>${this._escapeHtml(options.details)}</pre></details>` : ''}
                    </div>
                    <div class="modal-footer">
                        ${options.retryAction ? '<button class="btn-retry" onclick="window.HamsvicErrors._handleRetry(this)">Try Again</button>' : ''}
                        <button class="btn-close-modal" onclick="this.closest(\'.hamsvic-error-modal-overlay\').remove()">Close</button>
                    </div>
                </div>
            `;
            
            if (options.retryAction) {
                modal.querySelector('.btn-retry').dataset.action = options.retryAction;
            }
            
            document.body.appendChild(modal);
            setTimeout(() => modal.classList.add('show'), 10);
        },

        /**
         * Handle AJAX errors consistently
         * @param {Object} xhr - XMLHttpRequest or fetch response
         * @param {string} context - What operation failed (e.g., "saving estimate")
         * @param {Object} options - Additional options
         */
        handleAjaxError: function(xhr, context, options = {}) {
            let message = 'An unexpected error occurred.';
            let type = 'error';
            
            // Parse error from response
            if (xhr.responseJSON) {
                message = xhr.responseJSON.reason || xhr.responseJSON.error || xhr.responseJSON.message || message;
            } else if (xhr.status) {
                switch (xhr.status) {
                    case 400:
                        message = 'Invalid request. Please check your input.';
                        break;
                    case 401:
                        message = 'Your session has expired. Please log in again.';
                        if (!options.noRedirect) {
                            setTimeout(() => window.location.href = '/login/', 2000);
                        }
                        break;
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
                    case 502:
                    case 503:
                    case 504:
                        message = 'The server is temporarily unavailable. Please try again in a moment.';
                        type = 'warning';
                        break;
                    default:
                        if (xhr.status >= 400 && xhr.status < 500) {
                            message = 'There was a problem with your request.';
                        } else if (xhr.status >= 500) {
                            message = 'A server error occurred.';
                        }
                }
            }
            
            // Add context
            const fullMessage = context ? `Error ${context}: ${message}` : message;
            
            // Show appropriate notification
            if (options.useModal || xhr.status === 500) {
                this.showErrorModal('Something Went Wrong', fullMessage, {
                    details: options.showDetails ? `Status: ${xhr.status}\nURL: ${xhr.url || 'unknown'}` : null,
                    retryAction: options.retryAction
                });
            } else {
                this.showToast(fullMessage, type);
            }
            
            // Log for debugging
            console.error(`[Hamsvic] ${fullMessage}`, xhr);
        },

        /**
         * Handle fetch API errors
         * @param {Response} response - Fetch response
         * @param {string} context - What operation failed
         */
        handleFetchError: async function(response, context) {
            let errorData = { status: response.status };
            
            try {
                errorData.responseJSON = await response.json();
            } catch (e) {
                // Response wasn't JSON
            }
            
            this.handleAjaxError(errorData, context);
        },

        /**
         * Wrap a fetch call with automatic error handling
         * @param {string} url - URL to fetch
         * @param {Object} options - Fetch options
         * @param {string} context - Context for error messages
         * @returns {Promise} - Resolves with JSON data or rejects with error
         */
        fetchWithErrorHandling: async function(url, options = {}, context = '') {
            try {
                const response = await fetch(url, {
                    ...options,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        ...options.headers
                    }
                });
                
                if (!response.ok) {
                    await this.handleFetchError(response, context);
                    throw new Error(`HTTP ${response.status}`);
                }
                
                return await response.json();
            } catch (error) {
                if (error.message.startsWith('HTTP')) {
                    throw error; // Already handled
                }
                // Network error
                this.showToast('Network error. Please check your connection.', 'error');
                throw error;
            }
        },

        /**
         * Show a loading indicator
         * @param {string} message - Loading message
         * @returns {Object} - Object with hide() method
         */
        showLoading: function(message = 'Loading...') {
            const overlay = document.createElement('div');
            overlay.className = 'hamsvic-loading-overlay';
            overlay.innerHTML = `
                <div class="hamsvic-loading-content">
                    <div class="loading-spinner"></div>
                    <p>${this._escapeHtml(message)}</p>
                </div>
            `;
            document.body.appendChild(overlay);
            setTimeout(() => overlay.classList.add('show'), 10);
            
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

        // Private helper methods
        _getToastContainer: function() {
            let container = document.getElementById('hamsvic-toast-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'hamsvic-toast-container';
                document.body.appendChild(container);
            }
            return container;
        },

        _escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },

        _handleRetry: function(button) {
            const action = button.dataset.action;
            if (action && typeof window[action] === 'function') {
                button.closest('.hamsvic-error-modal-overlay').remove();
                window[action]();
            }
        }
    };

    // Inject CSS
    const style = document.createElement('style');
    style.textContent = `
        #hamsvic-toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-width: 400px;
        }

        .hamsvic-toast {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 16px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            transform: translateX(100%);
            opacity: 0;
            transition: all 0.3s ease;
        }

        .hamsvic-toast.show {
            transform: translateX(0);
            opacity: 1;
        }

        .hamsvic-toast .toast-icon {
            font-size: 1.25rem;
            flex-shrink: 0;
        }

        .hamsvic-toast-success .toast-icon { color: #10b981; }
        .hamsvic-toast-error .toast-icon { color: #ef4444; }
        .hamsvic-toast-warning .toast-icon { color: #f59e0b; }
        .hamsvic-toast-info .toast-icon { color: #6366f1; }

        .hamsvic-toast .toast-message {
            flex: 1;
            font-size: 0.9rem;
            color: #374151;
            line-height: 1.4;
        }

        .hamsvic-toast .toast-close {
            background: none;
            border: none;
            color: #9ca3af;
            cursor: pointer;
            padding: 0;
            font-size: 1.25rem;
        }

        .hamsvic-toast .toast-close:hover {
            color: #6b7280;
        }

        .hamsvic-error-modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10001;
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .hamsvic-error-modal-overlay.show {
            opacity: 1;
        }

        .hamsvic-error-modal {
            background: white;
            border-radius: 16px;
            max-width: 480px;
            width: 90%;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }

        .hamsvic-error-modal .modal-header {
            padding: 24px;
            text-align: center;
        }

        .hamsvic-error-modal .modal-header.error {
            background: linear-gradient(135deg, #fee2e2, #fecaca);
        }

        .hamsvic-error-modal .modal-header i {
            font-size: 3rem;
            color: #ef4444;
            margin-bottom: 12px;
            display: block;
        }

        .hamsvic-error-modal .modal-header h3 {
            margin: 0;
            color: #991b1b;
            font-size: 1.25rem;
        }

        .hamsvic-error-modal .modal-body {
            padding: 24px;
        }

        .hamsvic-error-modal .modal-body p {
            margin: 0;
            color: #4b5563;
            line-height: 1.6;
        }

        .hamsvic-error-modal .modal-body details {
            margin-top: 16px;
            background: #f3f4f6;
            border-radius: 8px;
            padding: 12px;
        }

        .hamsvic-error-modal .modal-body details summary {
            cursor: pointer;
            color: #6b7280;
            font-size: 0.875rem;
        }

        .hamsvic-error-modal .modal-body details pre {
            margin: 12px 0 0;
            font-size: 0.75rem;
            color: #6b7280;
            white-space: pre-wrap;
        }

        .hamsvic-error-modal .modal-footer {
            padding: 16px 24px;
            background: #f9fafb;
            display: flex;
            justify-content: flex-end;
            gap: 12px;
        }

        .hamsvic-error-modal .btn-retry {
            background: #6366f1;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
        }

        .hamsvic-error-modal .btn-close-modal {
            background: #e5e7eb;
            color: #374151;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
        }

        .hamsvic-loading-overlay {
            position: fixed;
            inset: 0;
            background: rgba(255,255,255,0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10002;
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .hamsvic-loading-overlay.show {
            opacity: 1;
        }

        .hamsvic-loading-content {
            text-align: center;
        }

        .hamsvic-loading-content .loading-spinner {
            width: 48px;
            height: 48px;
            border: 4px solid #e5e7eb;
            border-top-color: #6366f1;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 16px;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .hamsvic-loading-content p {
            color: #6b7280;
            margin: 0;
            font-size: 1rem;
        }
    `;
    document.head.appendChild(style);

    // Export to global scope
    window.HamsvicErrors = HamsvicErrors;

})(window);

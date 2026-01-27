/**
 * job-polling.js - Async job status polling and result handling
 * 
 * Usage in templates:
 * 1. Include <script src="{% static 'js/job-polling.js' %}"></script>
 * 2. Convert form submission to async:
 *    form.addEventListener('submit', async (e) => {
 *        e.preventDefault();
 *        const job = await JobPoller.submitFormAsync(form);
 *        if (job) {
 *            JobPoller.pollUntilComplete(job.job_id, job.status_url, {
 *                onProgress: (data) => console.log(`Progress: ${data.progress}%`),
 *                onComplete: (data) => console.log('Done!', data),
 *                onError: (error) => console.error('Failed:', error),
 *            });
 *        }
 *    });
 */

const JobPoller = {
    /**
     * Submit form asynchronously and get job ID
     * @param {HTMLFormElement} form - The form to submit
     * @returns {Promise} Resolves to {job_id, status_url, message} or null on error
     */
    async submitFormAsync(form) {
        try {
            const formData = new FormData(form);
            const method = form.method?.toUpperCase() || 'POST';
            const url = form.action;

            const response = await fetch(url, {
                method: method,
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });

            if (!response.ok) {
                const error = await response.json();
                console.error('Form submission error:', error);
                return null;
            }

            const data = await response.json();
            return {
                job_id: data.job_id,
                status_url: data.status_url,
                message: data.message,
            };
        } catch (error) {
            console.error('Form submission failed:', error);
            return null;
        }
    },

    /**
     * Poll job status until completion
     * @param {number} jobId - Job ID to poll
     * @param {string} statusUrl - API endpoint to check status
     * @param {Object} callbacks - {onProgress, onComplete, onError, onCancel}
     * @param {number} pollInterval - Milliseconds between polls (default 1000)
     */
    async pollUntilComplete(jobId, statusUrl, callbacks = {}, pollInterval = 1000) {
        const {
            onProgress = () => {},
            onComplete = () => {},
            onError = () => {},
            onCancel = () => {},
        } = callbacks;

        let pollCount = 0;
        const maxPolls = 3600; // 1 hour at 1 second intervals

        const poll = async () => {
            try {
                const response = await fetch(statusUrl);

                if (!response.ok) {
                    onError(`HTTP ${response.status}: ${response.statusText}`);
                    return false;
                }

                const data = await response.json();

                // Call progress callback on every poll
                onProgress(data);

                // Check status
                const { status, progress, current_step, error_message, is_complete } = data;

                if (is_complete) {
                    if (status === 'completed' || data.is_success) {
                        onComplete(data);
                    } else if (status === 'failed') {
                        onError(error_message || 'Job failed');
                    } else if (status === 'cancelled') {
                        onCancel(data);
                    }
                    return false; // Stop polling
                }

                // Continue polling if not complete
                if (pollCount++ < maxPolls) {
                    setTimeout(poll, pollInterval);
                } else {
                    onError('Job polling timeout (1 hour exceeded)');
                    return false;
                }

            } catch (error) {
                onError(`Polling error: ${error.message}`);
                return false;
            }
        };

        // Start polling
        poll();
    },

    /**
     * Show loading modal while job is processing
     * @param {string} jobId - Job ID being processed
     * @returns {Object} Modal with show(), hide(), setProgress(), setMessage()
     */
    createLoadingModal(jobId) {
        // Check if modal already exists
        let modal = document.getElementById(`job-modal-${jobId}`);
        if (modal) {
            return {
                show: () => modal.style.display = 'flex',
                hide: () => modal.style.display = 'none',
                setProgress: (percent) => {
                    const bar = modal.querySelector('.progress-bar');
                    if (bar) bar.style.width = percent + '%';
                },
                setMessage: (msg) => {
                    const el = modal.querySelector('.progress-message');
                    if (el) el.textContent = msg;
                },
                remove: () => modal.remove(),
            };
        }

        // Create new modal
        const modalHTML = `
            <div id="job-modal-${jobId}" class="job-loading-modal">
                <div class="job-loading-content">
                    <h2>Processing Job</h2>
                    <p class="job-id">Job ID: ${jobId}</p>
                    <div class="progress-container">
                        <div class="progress-bar" style="width: 0%"></div>
                    </div>
                    <p class="progress-message">Starting...</p>
                    <p class="progress-percent">0%</p>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        modal = document.getElementById(`job-modal-${jobId}`);

        // Add default styles if not already in CSS
        if (!document.getElementById('job-polling-styles')) {
            const style = document.createElement('style');
            style.id = 'job-polling-styles';
            style.textContent = `
                .job-loading-modal {
                    display: flex;
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.5);
                    justify-content: center;
                    align-items: center;
                    z-index: 10000;
                }

                .job-loading-content {
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    text-align: center;
                    min-width: 400px;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                }

                .job-loading-content h2 {
                    margin: 0 0 10px 0;
                    font-size: 20px;
                }

                .job-id {
                    color: #888;
                    font-size: 12px;
                    margin: 0 0 20px 0;
                }

                .progress-container {
                    width: 100%;
                    height: 30px;
                    background: #e0e0e0;
                    border-radius: 15px;
                    overflow: hidden;
                    margin: 20px 0;
                }

                .progress-bar {
                    height: 100%;
                    background: linear-gradient(90deg, #0d6efd, #0ca678);
                    transition: width 0.3s ease;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 12px;
                }

                .progress-message {
                    margin: 10px 0;
                    color: #555;
                    font-size: 14px;
                    min-height: 20px;
                }

                .progress-percent {
                    margin: 5px 0 0 0;
                    color: #888;
                    font-size: 12px;
                }

                .job-result-modal {
                    display: flex;
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.5);
                    justify-content: center;
                    align-items: center;
                    z-index: 10000;
                }

                .job-result-content {
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    min-width: 500px;
                    max-height: 80vh;
                    overflow-y: auto;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                }

                .job-result-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 20px;
                    border-bottom: 2px solid #e0e0e0;
                    padding-bottom: 10px;
                }

                .job-result-header h2 {
                    margin: 0;
                    font-size: 20px;
                }

                .job-result-close {
                    cursor: pointer;
                    font-size: 24px;
                    color: #999;
                }

                .job-result-close:hover {
                    color: #333;
                }

                .job-status-badge {
                    display: inline-block;
                    padding: 5px 15px;
                    border-radius: 20px;
                    font-weight: bold;
                    font-size: 12px;
                }

                .job-status-badge.success {
                    background: #d4edda;
                    color: #155724;
                }

                .job-status-badge.failed {
                    background: #f8d7da;
                    color: #721c24;
                }

                .job-status-badge.cancelled {
                    background: #e2e3e5;
                    color: #383d41;
                }

                .job-output-files {
                    margin: 20px 0;
                }

                .job-output-files h3 {
                    margin-top: 0;
                    font-size: 14px;
                    color: #555;
                }

                .job-file-item {
                    padding: 10px;
                    background: #f5f5f5;
                    border-radius: 5px;
                    margin: 10px 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }

                .job-file-name {
                    font-weight: 500;
                    color: #333;
                }

                .job-file-download {
                    background: #0d6efd;
                    color: white;
                    padding: 5px 15px;
                    border-radius: 5px;
                    text-decoration: none;
                    font-size: 12px;
                    cursor: pointer;
                }

                .job-file-download:hover {
                    background: #0b5ed7;
                }

                .job-error-message {
                    background: #f8d7da;
                    color: #721c24;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 15px 0;
                }
            `;
            document.head.appendChild(style);
        }

        return {
            show: () => {
                modal.style.display = 'flex';
            },
            hide: () => {
                modal.style.display = 'none';
            },
            setProgress: (percent) => {
                const bar = modal.querySelector('.progress-bar');
                if (bar) {
                    bar.style.width = percent + '%';
                    bar.textContent = percent + '%';
                }
                const percentEl = modal.querySelector('.progress-percent');
                if (percentEl) percentEl.textContent = percent + '%';
            },
            setMessage: (msg) => {
                const el = modal.querySelector('.progress-message');
                if (el) el.textContent = msg;
            },
            remove: () => {
                modal.remove();
            },
        };
    },

    /**
     * Show result modal with job output
     * @param {Object} jobData - Job response data
     */
    showResultModal(jobData) {
        const { status, result, error_message, outputs = [] } = jobData;
        const isSuccess = status === 'completed';
        const isFailed = status === 'failed';

        const statusBadgeClass = isSuccess ? 'success' : (isFailed ? 'failed' : 'cancelled');
        const statusText = status.charAt(0).toUpperCase() + status.slice(1);

        let outputsHTML = '';
        if (outputs.length > 0) {
            outputsHTML = `
                <div class="job-output-files">
                    <h3>Generated Files</h3>
                    ${outputs.map(file => `
                        <div class="job-file-item">
                            <span class="job-file-name">${file.filename}</span>
                            <a href="${file.download_url}" class="job-file-download">Download</a>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        let errorHTML = '';
        if (error_message) {
            errorHTML = `
                <div class="job-error-message">
                    <strong>Error:</strong> ${error_message}
                </div>
            `;
        }

        const modalHTML = `
            <div class="job-result-modal">
                <div class="job-result-content">
                    <div class="job-result-header">
                        <h2>Job Complete</h2>
                        <span class="job-result-close">&times;</span>
                    </div>
                    <div>
                        <p>
                            Status: <span class="job-status-badge ${statusBadgeClass}">${statusText}</span>
                        </p>
                        ${errorHTML}
                        ${outputsHTML}
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);

        const modal = document.querySelector('.job-result-modal');
        const closeBtn = modal.querySelector('.job-result-close');

        closeBtn.addEventListener('click', () => {
            modal.remove();
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    },
};

// Export for modules if available
if (typeof module !== 'undefined' && module.exports) {
    module.exports = JobPoller;
}

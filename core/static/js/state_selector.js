/**
 * State Selector Component
 * 
 * Provides a dropdown for selecting SOR (Schedule of Rates) state.
 * Integrates with the backend API to fetch available states and save preferences.
 * 
 * Usage:
 * 1. Include this script on the page
 * 2. Add a container element: <div id="state-selector"></div>
 * 3. Initialize: StateSelector.init({ moduleCode: 'estimate', workType: 'electrical' });
 */

const StateSelector = {
    container: null,
    currentState: null,
    states: [],
    options: {
        moduleCode: '',
        workType: '',
        onStateChange: null,
        showLabel: true,
        size: 'normal' // 'small', 'normal', 'large'
    },

    /**
     * Initialize the state selector
     * @param {Object} opts - Configuration options
     */
    init: function(opts) {
        this.options = { ...this.options, ...opts };
        this.container = document.getElementById('state-selector');
        
        if (!this.container) {
            console.warn('State selector container not found');
            return;
        }

        this.loadStates();
    },

    /**
     * Fetch available states from the API
     */
    loadStates: async function() {
        try {
            const params = new URLSearchParams();
            if (this.options.moduleCode) params.append('module_code', this.options.moduleCode);
            if (this.options.workType) params.append('work_type', this.options.workType);
            
            const response = await fetch(`/datasets/api/states/?${params.toString()}`, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                this.states = data.states || [];
                this.currentState = data.user_preference || data.default || 'TS';
                this.render();
            }
        } catch (error) {
            console.error('Error loading states:', error);
            // Default to Telangana if API fails
            this.states = [{ code: 'TS', name: 'Telangana', is_default: true }];
            this.currentState = 'TS';
            this.render();
        }
    },

    /**
     * Render the state selector dropdown
     */
    render: function() {
        const sizeClass = {
            'small': 'form-select-sm',
            'normal': '',
            'large': 'form-select-lg'
        }[this.options.size] || '';

        let html = '';
        
        if (this.options.showLabel) {
            html += `
                <label for="state-select" class="form-label">
                    <i class="fas fa-map-marker-alt me-1"></i>
                    SOR State
                </label>
            `;
        }
        
        html += `
            <div class="input-group">
                <select id="state-select" class="form-select ${sizeClass}" onchange="StateSelector.onChange(this.value)">
                    ${this.states.map(state => `
                        <option value="${state.code}" ${state.code === this.currentState ? 'selected' : ''}>
                            ${state.name} (${state.code})
                            ${state.is_default ? ' ★' : ''}
                        </option>
                    `).join('')}
                </select>
                ${this.states.length > 1 ? `
                    <button class="btn btn-outline-secondary" type="button" onclick="StateSelector.showInfo()" title="About SOR States">
                        <i class="fas fa-info-circle"></i>
                    </button>
                ` : ''}
            </div>
            <small class="text-muted mt-1 d-block">
                Using ${this.getCurrentStateName()} SOR rates
            </small>
        `;
        
        this.container.innerHTML = html;
    },

    /**
     * Get the current state name
     */
    getCurrentStateName: function() {
        const state = this.states.find(s => s.code === this.currentState);
        return state ? state.name : 'Telangana';
    },

    /**
     * Handle state change
     */
    onChange: async function(stateCode) {
        const oldState = this.currentState;
        this.currentState = stateCode;
        
        // Update the display
        const small = this.container.querySelector('small');
        if (small) {
            small.textContent = `Using ${this.getCurrentStateName()} SOR rates`;
        }
        
        // Save preference to backend
        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                             document.cookie.match(/csrftoken=([^;]+)/)?.[1];
            
            const response = await fetch('/datasets/api/states/set/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    state_code: stateCode,
                    module_code: this.options.moduleCode || undefined
                })
            });
            
            if (response.ok) {
                // Show success toast/notification
                this.showToast(`Switched to ${this.getCurrentStateName()} SOR rates`, 'success');
                
                // Call the callback if provided
                if (this.options.onStateChange) {
                    this.options.onStateChange(stateCode, oldState);
                }
            }
        } catch (error) {
            console.error('Error saving state preference:', error);
            this.showToast('Failed to save preference', 'error');
        }
    },

    /**
     * Show info modal about states
     */
    showInfo: function() {
        const modalHtml = `
            <div class="modal fade" id="stateInfoModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fas fa-info-circle me-2"></i>
                                About SOR States
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>
                                <strong>Schedule of Rates (SOR)</strong> are standardized rate lists published 
                                by state governments for public works projects.
                            </p>
                            <p>
                                Each state has its own SOR with different rates for:
                            </p>
                            <ul>
                                <li>Materials (cement, steel, electrical items, etc.)</li>
                                <li>Labor charges</li>
                                <li>Equipment and machinery</li>
                                <li>Overheads and contingencies</li>
                            </ul>
                            <h6 class="mt-3">Available States:</h6>
                            <ul class="list-group">
                                ${this.states.map(state => `
                                    <li class="list-group-item d-flex justify-content-between align-items-center">
                                        ${state.name}
                                        ${state.is_default ? '<span class="badge bg-primary">Default</span>' : ''}
                                        ${state.code === this.currentState ? '<span class="badge bg-success">Selected</span>' : ''}
                                    </li>
                                `).join('')}
                            </ul>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if any
        const existing = document.getElementById('stateInfoModal');
        if (existing) existing.remove();
        
        // Add modal to body
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('stateInfoModal'));
        modal.show();
    },

    /**
     * Show a toast notification
     */
    showToast: function(message, type) {
        // Try to use existing toast system or create simple notification
        if (typeof showToast === 'function') {
            showToast(message, type);
            return;
        }
        
        // Simple fallback
        const toast = document.createElement('div');
        toast.className = `alert alert-${type === 'success' ? 'success' : 'danger'} position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 300px;';
        toast.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'} me-2"></i>
            ${message}
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.remove(), 3000);
    },

    /**
     * Get current state code
     */
    getState: function() {
        return this.currentState;
    },

    /**
     * Set state programmatically
     */
    setState: function(stateCode) {
        const select = document.getElementById('state-select');
        if (select) {
            select.value = stateCode;
            this.onChange(stateCode);
        }
    }
};

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StateSelector;
}

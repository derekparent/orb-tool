/**
 * Oil Record Book Tool - Core JavaScript
 * Handles common functionality across pages
 */

// API helper
const api = {
    async get(endpoint) {
        const response = await fetch(`/api${endpoint}`);
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        return response.json();
    },

    async post(endpoint, data) {
        const response = await fetch(`/api${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return {
            ok: response.ok,
            status: response.status,
            data: await response.json()
        };
    }
};

// Format helpers
const format = {
    date(isoString) {
        const date = new Date(isoString);
        return date.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric',
            year: 'numeric'
        });
    },

    dateShort(isoString) {
        const date = new Date(isoString);
        return date.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric'
        });
    },

    sounding(feet, inches) {
        return `${feet}' ${inches}"`;
    },

    volume(gallons, m3) {
        return {
            gallons: `${gallons} gal`,
            m3: `${m3.toFixed(2)} m³`
        };
    },

    delta(value, unit = '') {
        const prefix = value >= 0 ? '+' : '';
        return `${prefix}${value}${unit}`;
    }
};

// Storage helpers for offline resilience
const storage = {
    set(key, value) {
        try {
            localStorage.setItem(`orb_${key}`, JSON.stringify(value));
        } catch (e) {
            console.warn('localStorage not available:', e);
        }
    },

    get(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(`orb_${key}`);
            return item ? JSON.parse(item) : defaultValue;
        } catch (e) {
            console.warn('localStorage not available:', e);
            return defaultValue;
        }
    },

    remove(key) {
        try {
            localStorage.removeItem(`orb_${key}`);
        } catch (e) {
            console.warn('localStorage not available:', e);
        }
    }
};

// Toast notifications (simple version)
const toast = {
    show(message, type = 'info') {
        // Simple alert for now, can be enhanced later
        console.log(`[${type}] ${message}`);
    }
};

// Export for use in templates
window.ORB = { api, format, storage, toast };


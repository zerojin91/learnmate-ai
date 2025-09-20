/* =============================================================================
   Utility Functions and Storage Manager
   ============================================================================= */

// Constants
const USER_NAME = "신민수"; // 원하는 이름으로 변경
let isGeneratingCurriculum = false;

// User Management
let currentUser = {
    name: USER_NAME,
    profile: {}
};

// Local Storage Manager
const StorageManager = {
    keys: {
        CURRENT_PROFILE: 'currentProfile',
        GENERATED_CURRICULUM: 'generatedCurriculum',
        CURRICULUM_PROGRESS: 'curriculumProgress',
        LAST_SESSION_ID: 'lastSessionId',
        USER_INFO: 'learnai_user'
    },

    // Data storage
    set(key, value) {
        try {
            const serializedValue = typeof value === 'string' ? value : JSON.stringify(value);
            localStorage.setItem(key, serializedValue);
            console.log(`💾 LocalStorage 저장: ${key}`, value);
        } catch (error) {
            console.error(`❌ LocalStorage 저장 실패: ${key}`, error);
        }
    },

    // Data retrieval
    get(key, defaultValue = null) {
        try {
            const value = localStorage.getItem(key);
            if (value === null) return defaultValue;
            
            // Try JSON parsing
            try {
                return JSON.parse(value);
            } catch {
                // Return original string if not JSON
                return value;
            }
        } catch (error) {
            console.error(`❌ LocalStorage 읽기 실패: ${key}`, error);
            return defaultValue;
        }
    },

    // Data removal
    remove(key) {
        try {
            localStorage.removeItem(key);
            console.log(`🗑️ LocalStorage 삭제: ${key}`);
        } catch (error) {
            console.error(`❌ LocalStorage 삭제 실패: ${key}`, error);
        }
    },

    // Multiple key removal
    removeMultiple(keys) {
        keys.forEach(key => this.remove(key));
    },

    // Clear all storage
    clear() {
        try {
            localStorage.clear();
            console.log('🧹 LocalStorage 전체 초기화');
        } catch (error) {
            console.error('❌ LocalStorage 초기화 실패', error);
        }
    },

    // Profile management methods
    profile: {
        set(topic, constraints, goal) {
            const profileData = { topic, constraints, goal };
            StorageManager.set(StorageManager.keys.CURRENT_PROFILE, profileData);
            return profileData;
        },
        
        get() {
            return StorageManager.get(StorageManager.keys.CURRENT_PROFILE, { 
                topic: '', 
                constraints: '', 
                goal: '' 
            });
        },
        
        clear() {
            StorageManager.remove(StorageManager.keys.CURRENT_PROFILE);
        }
    },

    // Curriculum management methods
    curriculum: {
        set(data) {
            StorageManager.set(StorageManager.keys.GENERATED_CURRICULUM, data);
        },
        
        get() {
            return StorageManager.get(StorageManager.keys.GENERATED_CURRICULUM, null);
        },
        
        clear() {
            StorageManager.remove(StorageManager.keys.GENERATED_CURRICULUM);
        },

        progress: {
            set(data) {
                StorageManager.set(StorageManager.keys.CURRICULUM_PROGRESS, data);
            },
            
            get() {
                return StorageManager.get(StorageManager.keys.CURRICULUM_PROGRESS, []);
            },
            
            clear() {
                StorageManager.remove(StorageManager.keys.CURRICULUM_PROGRESS);
            },

            updateModule(moduleId, completed) {
                const progress = this.get();
                progress[moduleId] = completed;
                this.set(progress);
            },

            isCompleted(moduleId) {
                const progress = this.get();
                return progress[moduleId] || false;
            }
        }
    },

};

// Utility Functions
function showNotification(message, type = 'success', duration = 3000) {
    const notification = document.getElementById('notification');
    if (!notification) return;

    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.classList.add('show');

    setTimeout(() => {
        notification.classList.remove('show');
    }, duration);
}

function formatDate(date) {
    return new Intl.DateTimeFormat('ko-KR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    }).format(date);
}

function sanitizeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Export for use in other modules
window.StorageManager = StorageManager;
window.showNotification = showNotification;
window.formatDate = formatDate;
window.sanitizeHtml = sanitizeHtml;
window.debounce = debounce;
window.throttle = throttle;
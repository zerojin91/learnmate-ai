/* =============================================================================
   Main Application Entry Point
   ============================================================================= */

// Global variables
const SESSION_ID = document.currentScript?.dataset?.sessionId || '';

// Application initialization
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 LearningMate 애플리케이션 시작');
    console.log('📱 세션 ID:', SESSION_ID);
    
    // Initialize all modules
    initializeApplication();
});

// Initialize application modules
function initializeApplication() {
    try {
        // 1. Initialize chat system
        if (!initializeChat()) {
            console.error('❌ 채팅 시스템 초기화 실패');
            return;
        }
        
        // 2. Initialize navigation
        initializeNavigation();
        
        // 3. Initialize profile from stored data
        initializeProfile();
        
        // 4. Setup example card handlers
        setupExampleHandlers();
        
        // 5. Setup curriculum generation button
        setupCurriculumButton();
        
        // 6. Initialize session management
        initializeSession();
        
        console.log('✅ 모든 모듈 초기화 완료');
        
    } catch (error) {
        console.error('❌ 애플리케이션 초기화 실패:', error);
        showNotification('애플리케이션 초기화 중 오류가 발생했습니다', 'error');
    }
}

// Setup example card handlers
function setupExampleHandlers() {
    const exampleCards = document.querySelectorAll('.example-card');
    exampleCards.forEach(card => {
        card.addEventListener('click', function() {
            const exampleMessage = this.dataset.message || this.querySelector('.example-title')?.textContent;
            if (exampleMessage && messageInput) {
                messageInput.value = exampleMessage;
                messageInput.focus();
                
                // Auto-send the message
                setTimeout(() => {
                    if (sendButton && !sendButton.disabled) {
                        sendMessage();
                    }
                }, 100);
            }
        });
    });
}

// Setup curriculum generation button
function setupCurriculumButton() {
    const generateBtn = document.getElementById('generateCurriculumBtn');
    if (generateBtn) {
        generateBtn.addEventListener('click', generateCurriculum);
    }
}

// Initialize session management
function initializeSession() {
    const sessionId = getSessionId();
    if (sessionId) {
        StorageManager.set(StorageManager.keys.LAST_SESSION_ID, sessionId);
        console.log('💾 세션 ID 저장:', sessionId);
    }
    
    // Check for session changes
    const lastSessionId = StorageManager.get(StorageManager.keys.LAST_SESSION_ID);
    if (lastSessionId && sessionId && lastSessionId !== sessionId) {
        console.log('🔄 새 세션 감지 - 데이터 초기화');
        // Clear old session data but keep curriculum and progress
        StorageManager.profile.clear();
        // Don't clear curriculum data as it might be valuable across sessions
    }
}

// Handle application errors globally
window.addEventListener('error', function(event) {
    console.error('❌ 전역 오류:', event.error);
    showNotification('예상치 못한 오류가 발생했습니다', 'error');
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', function(event) {
    console.error('❌ Promise 오류:', event.reason);
    showNotification('요청 처리 중 오류가 발생했습니다', 'error');
});

// Utility function to check if application is ready
function isApplicationReady() {
    return !!(
        chatMessages && 
        messageInput && 
        sendButton &&
        typeof StorageManager !== 'undefined'
    );
}

// Periodic health check
setInterval(() => {
    if (!isApplicationReady()) {
        console.warn('⚠️ 애플리케이션 상태 확인 필요');
        // Try to reinitialize critical components
        if (!chatMessages || !messageInput || !sendButton) {
            initializeChat();
        }
    }
}, 30000); // Check every 30 seconds

// Export for debugging
window.LearningMate = {
    version: '1.0.0',
    modules: {
        chat: { initialized: !!chatMessages },
        profile: { initialized: typeof updateLearningProfile !== 'undefined' },
        curriculum: { initialized: typeof generateCurriculum !== 'undefined' },
        navigation: { initialized: typeof switchToTab !== 'undefined' }
    },
    storage: StorageManager,
    session: SESSION_ID,
    debug: {
        reinitialize: initializeApplication,
        checkHealth: isApplicationReady
    }
};

console.log('🎯 LearningMate 글로벌 객체 등록 완료:', window.LearningMate);
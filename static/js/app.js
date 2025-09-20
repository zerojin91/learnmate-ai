/* =============================================================================
   Main Application Entry Point
   ============================================================================= */

// Global variables
// SESSION_ID is already declared in index.html template

// Application initialization
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 LearningMate 애플리케이션 시작');
    console.log('📱 세션 ID:', SESSION_ID);

    // 페이지 새로고침 시 스크롤 위치 초기화
    if ('scrollRestoration' in history) {
        history.scrollRestoration = 'manual';
    }

    // Initialize all modules
    initializeApplication();
});

// Initialize application modules
function initializeApplication() {
    try {
        // 0. 페이지 로드 시 맨 위로 스크롤
        window.scrollTo(0, 0);

        // 1. Initialize chat system
        if (!initializeChat()) {
            console.error('❌ 채팅 시스템 초기화 실패');
            return;
        }

        // 2. Initialize navigation
        initializeNavigation();
        
        
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
        // Profile data cleared since profile functionality was removed
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

    // 커리큘럼 관련 오류는 정상적인 상황일 수 있으므로 알림 표시 안함
    const errorMessage = event.reason?.message || event.reason?.toString() || '';
    const isExpectedError = errorMessage.includes('curriculum') ||
                          errorMessage.includes('커리큘럼') ||
                          errorMessage.includes('get_curriculum') ||
                          errorMessage.includes('HTTP error! status: 500') ||
                          errorMessage.includes('도구를 찾을 수 없습니다');

    if (isExpectedError) {
        console.log('📝 예상된 오류 - 정상적인 상황으로 판단됨:', errorMessage);
        event.preventDefault(); // 기본 오류 처리 방지
        return;
    }

    // 네트워크 관련 오류도 조건부로 처리
    if (errorMessage.includes('fetch') || errorMessage.includes('네트워크')) {
        console.log('🌐 네트워크 관련 오류 감지');
        showNotification('네트워크 연결을 확인해주세요', 'error');
        return;
    }

    // 기타 중요한 오류만 표시
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
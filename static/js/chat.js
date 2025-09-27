/* =============================================================================
   Chat Management Functions
   ============================================================================= */

// DOM elements
let chatMessages, messageInput, sendButton;

// Initialize chat elements
function initializeChat() {
    chatMessages = document.getElementById('chatMessages');
    messageInput = document.getElementById('messageInput');
    sendButton = document.getElementById('sendButton');

    if (!chatMessages || !messageInput || !sendButton) {
        console.error('Chat elements not found');
        return false;
    }

    setupChatEventListeners();
    loadChatHistory();
    return true;
}

// Load chat history from session
async function loadChatHistory() {
    try {
        const sessionId = getSessionId();
        if (!sessionId) return;

        const response = await fetch(`/api/session/${sessionId}`, {
            credentials: 'include'
        });

        if (!response.ok) return;

        const sessionData = await response.json();

        // 프로필 정보 복원
        if (sessionData.topic || sessionData.constraints || sessionData.goal) {
            console.log('🔄 프로필 정보 복원 중...');
            const profileData = {
                topic: sessionData.topic || '',
                constraints: sessionData.constraints || '',
                goal: sessionData.goal || ''
            };

            // 프로필 정보가 있는 것만 필터링
            const validProfileData = Object.fromEntries(
                Object.entries(profileData).filter(([key, value]) => value)
            );

            if (Object.keys(validProfileData).length > 0) {
                updateProfileDisplay(validProfileData);
                console.log('✅ 프로필 정보 복원 완료:', validProfileData);
            }
        }

        if (sessionData.messages && sessionData.messages.length > 0) {
            console.log('🔄 채팅 내역 복원 중...');

            // Clear existing messages
            chatMessages.innerHTML = '';

            // Restore messages
            sessionData.messages.forEach(msg => {
                if (msg.role === 'user') {
                    addUserMessage(msg.content);
                } else if (msg.role === 'assistant') {
                    addAIMessage(msg.content);
                }
            });

            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
            console.log('✅ 채팅 내역 복원 완료');
        }
    } catch (error) {
        console.error('❌ 채팅 내역 로드 실패:', error);
    }
}

// Add user message to chat
function addUserMessage(content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    messageDiv.innerHTML = `
        <div class="message-avatar user-avatar">You</div>
        <div class="message-content">${content}</div>
    `;
    chatMessages.appendChild(messageDiv);
}

// Add AI message to chat
function addAIMessage(content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ai-message';
    messageDiv.innerHTML = `
        <div class="message-avatar ai-avatar-small">AI</div>
        <div class="message-content">${formatSimpleMarkdown(content)}</div>
    `;
    chatMessages.appendChild(messageDiv);
}

// Setup chat event listeners
function setupChatEventListeners() {
    // Send button click
    sendButton.addEventListener('click', sendMessage);
    
    // Enter key press
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Auto-resize textarea
    messageInput.addEventListener('input', autoResizeTextarea);
    
    
    // Clear chat button
    const clearButton = document.getElementById('clearButton');
    if (clearButton) {
        clearButton.addEventListener('click', clearChat);
    }
}

// Auto-resize textarea
function autoResizeTextarea() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
}

// Send message function
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message || sendButton.disabled) return;

    console.log(`📤 메시지 전송: ${message}`);

    // Add user message to chat
    addMessageToChat(message, 'user');

    // Clear input and disable send button
    messageInput.value = '';
    messageInput.style.height = 'auto';
    sendButton.disabled = true;
    sendButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    try {
        const SESSION_ID = getSessionId();
        console.log(`🔗 사용할 세션 ID: ${SESSION_ID}`);

        if (!SESSION_ID) {
            throw new Error('세션 ID를 찾을 수 없습니다');
        }

        console.log('📡 요청 전송 중...');
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Session-ID': SESSION_ID
            },
            credentials: 'include',
            body: JSON.stringify({
                message: message,
                session_id: SESSION_ID
            })
        });

        console.log(`📡 응답 상태: ${response.status} ${response.statusText}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Handle streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let aiMessageElement = null;
        let fullAiResponse = '';
        let buffer = ''; // Buffer for incomplete JSON

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            console.log('📥 받은 청크:', chunk);
            buffer += chunk;
            const lines = buffer.split('\n');

            // Keep the last line in buffer if it doesn't end with newline
            buffer = lines.pop() || '';

            for (const line of lines) {
                console.log('📄 처리 중인 라인:', line);
                if (line.startsWith('data: ')) {
                    const data = line.slice(6).trim();
                    console.log('📦 SSE 데이터:', data);
                    if (data === '[DONE]' || data === '') continue;

                    try {
                        const parsed = JSON.parse(data);
                        console.log('✅ JSON 파싱 성공:', parsed);
                        console.log('  - content:', parsed.content ? 'Y' : 'N');
                        console.log('  - profile:', parsed.profile ? 'Y' : 'N');
                        console.log('  - done:', parsed.done ? 'Y' : 'N');
                        console.log('  - error:', parsed.error ? 'Y' : 'N');

                        if (parsed.error) {
                            console.error('❌ 서버 오류:', parsed.error);
                            showNotification(`오류: ${parsed.error}`, 'error');
                            continue;
                        }

                        if (parsed.done) {
                            console.log('✅ AI 응답 완료');
                            break;
                        }

                        if (parsed.content) {
                            console.log('📝 콘텐츠 수신:', parsed.content);

                            // 커리큘럼 JSON 응답 감지 및 처리
                            if (isCurriculumJsonResponse(parsed.content)) {
                                console.log('📚 커리큘럼 JSON 응답 감지 - 데이터 저장 중');

                                // 커리큘럼 데이터 누적
                                fullAiResponse += parsed.content;

                                // JSON이 완성되었는지 확인하고 저장
                                try {
                                    const curriculumData = JSON.parse(fullAiResponse);
                                    console.log('✅ 커리큘럼 JSON 파싱 성공:', curriculumData);

                                    // 커리큘럼 데이터를 localStorage에 저장
                                    StorageManager.curriculum.set(curriculumData);
                                    console.log('💾 커리큘럼 데이터 저장 완료');

                                    // 대화창에는 간단한 메시지만 표시
                                    if (!aiMessageElement) {
                                        console.log('🆕 새 AI 메시지 요소 생성 (커리큘럼용)');
                                        aiMessageElement = addMessageToChat('', 'ai');
                                    }

                                    const friendlyMessage = '✅ 맞춤형 커리큘럼이 생성되었습니다! 상단의 "나의 커리큘럼" 탭에서 확인해보세요.';
                                    updateMessageContent(aiMessageElement, friendlyMessage);

                                    // Check if we're in generation mode with progress tracking
                                    if (isGeneratingCurriculum && window.curriculumGenerationStartTime) {
                                        console.log('📊 진행 상황 추적 중이므로 자동 전환을 생략하고 폴링 완료를 기다립니다');
                                        // Let the progress polling handle the completion
                                        return; // 일반 처리 로직 건너뛰기
                                    }

                                    // Legacy behavior for non-tracked generation
                                    console.log('🔄 기존 방식으로 즉시 탭 전환 (진행 상황 추적 없음)');
                                    // 커리큘럼 생성 상태 해제
                                    isGeneratingCurriculum = false;

                                    // 커리큘럼 탭으로 자동 전환 (레거시 동작)
                                    setTimeout(() => {
                                        if (typeof switchToTab === 'function') {
                                            switchToTab('curriculum');
                                            // 커리큘럼 콘텐츠 즉시 업데이트
                                            const curriculumContent = document.getElementById('curriculumContent');
                                            if (curriculumContent && typeof displayCurriculumCards === 'function') {
                                                displayCurriculumCards(curriculumContent, curriculumData);
                                            }
                                        }
                                    }, 1000);

                                    return; // 일반 처리 로직 건너뛰기
                                } catch (jsonError) {
                                    // JSON이 아직 완성되지 않았거나 파싱 오류 - 계속 누적
                                    console.log('⏳ JSON 아직 미완성 - 계속 수신 중');
                                }
                            }

                            // 일반 응답 처리
                            if (!aiMessageElement) {
                                console.log('🆕 새 AI 메시지 요소 생성');
                                aiMessageElement = addMessageToChat('', 'ai');
                            }

                            // user_profiling 노드의 응답인 경우 타이핑 애니메이션 처리
                            console.log('🔍 노드 확인:', parsed.node);
                            if (parsed.node === 'user_profiling' || (!parsed.node && parsed.profile)) {
                                console.log('⌨️ user_profiling 타이핑 애니메이션 시작');

                                // 타이핑 애니메이션 함수
                                const typeMessage = async (text, element) => {
                                    let currentText = '';
                                    for (let i = 0; i < text.length; i++) {
                                        currentText += text[i];
                                        updateMessageContent(element, currentText);
                                        await new Promise(resolve => setTimeout(resolve, 30)); // 30ms 간격
                                    }
                                };

                                // 비동기로 타이핑 애니메이션 실행
                                typeMessage(parsed.content, aiMessageElement);
                                fullAiResponse = parsed.content; // 전체 응답 저장
                            } else if (parsed.node && parsed.node !== 'user_profiling') {
                                // user_profiling이 아닌 다른 노드의 경우 기존 방식대로 처리
                                fullAiResponse += parsed.content;
                                console.log('📊 전체 응답 길이:', fullAiResponse.length);

                                // 큰 JSON의 경우 UI 업데이트를 디바운스
                                if (fullAiResponse.length > 5000) {
                                    // 큰 응답의 경우 500ms마다 업데이트
                                    clearTimeout(window.updateTimeout);
                                    window.updateTimeout = setTimeout(() => {
                                        updateMessageContent(aiMessageElement, fullAiResponse);
                                    }, 500);
                                } else {
                                    // 작은 응답은 즉시 업데이트
                                    updateMessageContent(aiMessageElement, fullAiResponse);
                                }
                            }
                        }

                        // 프로필 데이터 처리
                        if (parsed.profile) {
                            console.log('📊 프로필 데이터 수신:', parsed.profile);
                            updateProfileDisplay(parsed.profile);
                        }
                    } catch (e) {
                        // 큰 JSON이 여러 청크로 나뉠 수 있으므로 더 관대하게 처리
                        if (!data.includes('{') && !data.includes('}')) {
                            // JSON이 아닌 일반 텍스트라면 직접 추가
                            if (!aiMessageElement) {
                                aiMessageElement = addMessageToChat('', 'ai');
                            }
                            fullAiResponse += data;
                            updateMessageContent(aiMessageElement, fullAiResponse);
                        } else {
                            console.warn('JSON 파싱 건너뛰기 (불완전한 데이터):', e.message);
                        }
                    }
                }
            }
        }

        // 마지막 업데이트 보장
        if (fullAiResponse && aiMessageElement) {
            clearTimeout(window.updateTimeout);
            updateMessageContent(aiMessageElement, fullAiResponse);
        }

        if (fullAiResponse) {
            // Profile extraction removed

            // Check for curriculum generation completion (only if not already handled)
            if (typeof isGeneratingCurriculum !== 'undefined' && isGeneratingCurriculum) {
                // Check if curriculum data was already saved in the streaming process
                const existingCurriculum = StorageManager.curriculum.get();
                if (!existingCurriculum) {
                    setTimeout(() => {
                        if (typeof checkCurriculumCompletion === 'function') {
                            checkCurriculumCompletion();
                        }
                    }, 1000); // Give some time for data to be processed
                } else {
                    console.log('📚 커리큘럼 이미 저장됨 - 추가 체크 생략');
                    isGeneratingCurriculum = false;
                }
            }
        }

    } catch (error) {
        console.error('메시지 전송 오류:', error);
        addMessageToChat(`오류가 발생했습니다: ${error.message}`, 'ai');
        showNotification(`오류: ${error.message}`, 'error');
    } finally {
        // Re-enable send button
        sendButton.disabled = false;
        sendButton.innerHTML = '<i class="fas fa-paper-plane"></i>';
    }
}

// Add message to chat
function addMessageToChat(content, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    
    const avatarDiv = document.createElement('div');
    avatarDiv.className = `message-avatar ${type}-avatar${type === 'ai' ? '-small' : ''}`;
    avatarDiv.textContent = type === 'ai' ? 'AI' : currentUser.name.charAt(0);
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = formatSimpleMarkdown(content);
    
    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);
    
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageDiv;
}

// Update message content
function updateMessageContent(messageElement, content) {
    const contentElement = messageElement.querySelector('.message-content');
    if (contentElement) {
        contentElement.innerHTML = formatSimpleMarkdown(content);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}


// Clear chat function
async function clearChat() {
    try {
        const response = await fetch('/clear-chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Update session ID if provided
            if (data.new_session_id) {
                const oldSessionId = window.SESSION_ID;
                window.SESSION_ID = data.new_session_id;
                console.log(`🔄 세션 ID 변경: ${oldSessionId} → ${data.new_session_id}`);
                console.log(`📋 서버 응답 정보 - 이전: ${data.old_session_id}, 신규: ${data.new_session_id}`);
            }

            // Clear chat messages
            const initialMsg = '안녕하세요! LearningMate의 학습 멘토입니다. 어떤 주제에 대해 배우고 싶으신지 알려주세요. 맞춤형 학습 계획을 함께 만들어보겠습니다.';

            chatMessages.innerHTML = `
                <div class="message ai-message">
                    <div class="message-avatar ai-avatar-small">AI</div>
                    <div class="message-content" id="initialMessage">
                        ${initialMsg}
                    </div>
                </div>
            `;

            // Clear profile and curriculum data
            StorageManager.profile.clear();
            StorageManager.curriculum.clear();
            StorageManager.curriculum.progress.clear();

            // Reset profile UI to initial state
            resetProfileUI();

            // Reset generation state
            isGeneratingCurriculum = false;

            // Refresh curriculum page if active
            const curriculumContent = document.getElementById('curriculumContent');
            if (curriculumContent && curriculumContent.style.display === 'block') {
                showCurriculumContent(curriculumContent);
            }

            showNotification('대화가 초기화되었습니다');
        } else {
            showNotification('대화 초기화에 실패했습니다', 'error');
        }
    } catch (error) {
        showNotification(`오류: ${error.message}`, 'error');
    }
}

// Get session ID from various sources
function getSessionId() {
    console.log('🔍 세션 ID 조회 시작');

    // Try to get from cookie first (most reliable after clear-chat)
    const cookieSessionId = getCookie('session_id');
    if (cookieSessionId) {
        console.log('✅ 세션 ID 발견 (쿠키):', cookieSessionId);

        // Update window.SESSION_ID to sync with cookie (avoid const reassignment)
        if (typeof window !== 'undefined' && window.SESSION_ID !== cookieSessionId) {
            console.log('🔄 window.SESSION_ID 동기화 필요');
            const oldWindowSession = window.SESSION_ID;
            window.SESSION_ID = cookieSessionId;
            console.log(`📋 window.SESSION_ID 업데이트: ${oldWindowSession} → ${cookieSessionId}`);
        }

        return cookieSessionId;
    }

    // Try to get from window.SESSION_ID (fallback)
    if (typeof window !== 'undefined' && window.SESSION_ID) {
        console.log('✅ 세션 ID 발견 (window 객체):', window.SESSION_ID);
        return window.SESSION_ID;
    }

    // Try to get from const global variable (read-only fallback)
    if (typeof SESSION_ID !== 'undefined' && SESSION_ID) {
        console.log('✅ 세션 ID 발견 (글로벌 const):', SESSION_ID);
        // Sync to window for future use
        if (typeof window !== 'undefined') {
            window.SESSION_ID = SESSION_ID;
            console.log('🔄 window.SESSION_ID에 동기화됨');
        }
        return SESSION_ID;
    }

    console.error('❌ 세션 ID를 찾을 수 없습니다');
    console.log('🔍 현재 상태 상세 정보:');
    console.log('  - SESSION_ID:', typeof SESSION_ID !== 'undefined' ? SESSION_ID : 'undefined');
    console.log('  - window.SESSION_ID:', typeof window.SESSION_ID !== 'undefined' ? window.SESSION_ID : 'undefined');
    console.log('  - 쿠키:', document.cookie);
    console.log('  - localStorage:', typeof StorageManager !== 'undefined' ? StorageManager.get(StorageManager.keys.LAST_SESSION_ID) : 'StorageManager undefined');
    return null;
}

// Get cookie value
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

// Simple markdown formatting
function formatSimpleMarkdown(text) {
    return text
        // **bold text** -> <strong>bold text</strong>
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Line breaks
        .replace(/\n/g, '<br>')
        // Bullet points
        .replace(/^- (.*$)/gim, '• $1')
        .replace(/^\* (.*$)/gim, '• $1');
}

// 커리큘럼 JSON 응답 감지 함수
function isCurriculumJsonResponse(content) {
    // JSON 형태이고 커리큘럼 관련 키워드가 포함된 경우
    const trimmedContent = content.trim();

    // JSON 시작 감지
    if (trimmedContent.startsWith('{') || trimmedContent.includes('"title"') ||
        trimmedContent.includes('"modules"') || trimmedContent.includes('"duration_weeks"') ||
        trimmedContent.includes('"Learning Path"') || trimmedContent.includes('"level"')) {

        console.log('🎯 커리큘럼 JSON 패턴 감지됨');
        return true;
    }

    // 여러 줄의 JSON 시작 부분 감지
    if (trimmedContent.includes('{\n"title"') || trimmedContent.includes('{ "title"')) {
        console.log('🎯 커리큘럼 JSON 시작 감지됨');
        return true;
    }

    return false;
}

// Reset profile UI to initial state
function resetProfileUI() {
    console.log('🔄 프로필 UI 초기화');

    // 주제 초기화
    const topicElement = document.getElementById('profileTopic');
    const stepTopic = document.getElementById('stepTopic');
    if (topicElement) {
        topicElement.textContent = '설정 필요';
        topicElement.classList.remove('completed');
    }
    if (stepTopic) {
        stepTopic.classList.remove('completed');
    }

    // 조건 초기화
    const constraintsElement = document.getElementById('profileConstraints');
    const stepConstraints = document.getElementById('stepConstraints');
    if (constraintsElement) {
        constraintsElement.textContent = '설정 필요';
        constraintsElement.classList.remove('completed');
    }
    if (stepConstraints) {
        stepConstraints.classList.remove('completed');
    }

    // 목표 초기화
    const goalElement = document.getElementById('profileGoal');
    const stepGoal = document.getElementById('stepGoal');
    if (goalElement) {
        goalElement.textContent = '설정 필요';
        goalElement.classList.remove('completed');
    }
    if (stepGoal) {
        stepGoal.classList.remove('completed');
    }

    // 커리큘럼 섹션 숨기기
    const curriculumSection = document.getElementById('curriculumSection');
    if (curriculumSection) {
        curriculumSection.style.display = 'none';
        console.log('✅ 커리큘럼 섹션 숨김');
    }

    console.log('✅ 프로필 UI 초기화 완료');
}

// Profile display update function
function updateProfileDisplay(profileData) {
    console.log('🔄 프로필 UI 업데이트:', profileData);

    // 주제 업데이트
    if (profileData.topic) {
        const topicElement = document.getElementById('profileTopic');
        const stepTopic = document.getElementById('stepTopic');
        if (topicElement) {
            topicElement.textContent = profileData.topic;
            topicElement.classList.add('completed');
        }
        if (stepTopic) {
            stepTopic.classList.add('completed');
        }
        console.log('✅ 주제 업데이트:', profileData.topic);
    }

    // 조건 업데이트
    if (profileData.constraints) {
        const constraintsElement = document.getElementById('profileConstraints');
        const stepConstraints = document.getElementById('stepConstraints');
        if (constraintsElement) {
            constraintsElement.textContent = profileData.constraints;
            constraintsElement.classList.add('completed');
        }
        if (stepConstraints) {
            stepConstraints.classList.add('completed');
        }
        console.log('✅ 조건 업데이트:', profileData.constraints);
    }

    // 목표 업데이트
    if (profileData.goal) {
        const goalElement = document.getElementById('profileGoal');
        const stepGoal = document.getElementById('stepGoal');
        if (goalElement) {
            goalElement.textContent = profileData.goal;
            goalElement.classList.add('completed');
        }
        if (stepGoal) {
            stepGoal.classList.add('completed');
        }
        console.log('✅ 목표 업데이트:', profileData.goal);
    }

    // 모든 단계가 완료되면 커리큘럼 섹션 표시
    const hasAllData = profileData.topic && profileData.constraints && profileData.goal;
    if (hasAllData) {
        const curriculumSection = document.getElementById('curriculumSection');
        if (curriculumSection) {
            curriculumSection.style.display = 'block';
            console.log('✅ 커리큘럼 섹션 표시');
        }
    }

    // localStorage에 저장
    if (typeof StorageManager !== 'undefined') {
        StorageManager.profile.set(
            profileData.topic || '',
            profileData.constraints || '',
            profileData.goal || ''
        );
    }
}

// Export functions for global use
window.initializeChat = initializeChat;
window.sendMessage = sendMessage;
window.addMessageToChat = addMessageToChat;
window.clearChat = clearChat;
window.getSessionId = getSessionId;
window.getCookie = getCookie;
window.formatSimpleMarkdown = formatSimpleMarkdown;
window.updateProfileDisplay = updateProfileDisplay;
window.resetProfileUI = resetProfileUI;
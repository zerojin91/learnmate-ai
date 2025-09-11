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
    return true;
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
    
    // File attach button
    const attachButton = document.getElementById('attachButton');
    if (attachButton) {
        attachButton.addEventListener('click', () => {
            document.getElementById('fileInput').click();
        });
    }
    
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

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Handle streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let aiMessageElement = null;
        let fullAiResponse = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') continue;

                    try {
                        const parsed = JSON.parse(data);
                        
                        if (parsed.error) {
                            showNotification(`오류: ${parsed.error}`, 'error');
                            continue;
                        }

                        if (parsed.done) {
                            console.log('✅ AI 응답 완료');
                            break;
                        }

                        if (parsed.content) {
                            if (!aiMessageElement) {
                                aiMessageElement = addMessageToChat('', 'ai');
                            }
                            
                            fullAiResponse += parsed.content;
                            updateMessageContent(aiMessageElement, fullAiResponse);
                            
                            // Handle profile updates
                            if (parsed.profile) {
                                handleProfileUpdate(parsed.profile);
                            }
                        }
                    } catch (e) {
                        console.error('JSON 파싱 오류:', e);
                    }
                }
            }
        }

        if (fullAiResponse) {
            extractAndUpdateProfile(fullAiResponse);
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

// Handle profile update from server
function handleProfileUpdate(profileData) {
    console.log('📊 프로필 업데이트 수신:', profileData);
    
    if (profileData.topic || profileData.constraints || profileData.goal) {
        updateLearningProfile(
            profileData.topic || '',
            profileData.constraints || '', 
            profileData.goal || ''
        );
        
        // Store in localStorage
        StorageManager.profile.set(
            profileData.topic || '',
            profileData.constraints || '',
            profileData.goal || ''
        );
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
            // Clear chat messages
            const activeTab = document.querySelector('.nav-link.active').dataset.page;
            const initialMsg = activeTab === 'profile' 
                ? '안녕하세요! 사내 지식이 풍부한 전문분야별 AI 멘토들이 여러분의 질문에 답변해드립니다. 궁금한 분야나 주제를 말씀해주시면, 해당 영역의 멘토들이 각자의 전문성을 살려 도움을 드리겠습니다.'
                : '안녕하세요! LearningMate의 학습 멘토입니다. 어떤 주제에 대해 배우고 싶으신지 알려주세요. 맞춤형 학습 계획을 함께 만들어보겠습니다.';
            
            chatMessages.innerHTML = `
                <div class="message ai-message">
                    <div class="message-avatar ai-avatar-small">AI</div>
                    <div class="message-content" id="initialMessage">
                        ${initialMsg}
                    </div>
                </div>
            `;
            
            // Clear profile and curriculum data
            updateLearningProfile('', '', '');
            StorageManager.profile.clear();
            StorageManager.curriculum.clear();
            StorageManager.curriculum.progress.clear();
            
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
    // Try to get from template variable first
    if (typeof SESSION_ID !== 'undefined' && SESSION_ID) {
        return SESSION_ID;
    }
    
    // Try to get from cookie
    const cookieSessionId = getCookie('session_id');
    if (cookieSessionId) {
        return cookieSessionId;
    }
    
    // Try to get from localStorage
    const storedSessionId = StorageManager.get(StorageManager.keys.LAST_SESSION_ID);
    if (storedSessionId) {
        return storedSessionId;
    }
    
    console.warn('세션 ID를 찾을 수 없습니다');
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

// Export functions for global use
window.initializeChat = initializeChat;
window.sendMessage = sendMessage;
window.addMessageToChat = addMessageToChat;
window.clearChat = clearChat;
window.getSessionId = getSessionId;
window.getCookie = getCookie;
window.formatSimpleMarkdown = formatSimpleMarkdown;
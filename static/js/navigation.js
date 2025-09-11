/* =============================================================================
   Navigation and Tab Management
   ============================================================================= */

// Global variables for mentor management
let selectedMentors = [];
let finalSelectedMentors = [];

// Navigation and content switching
function switchToTab(page) {
    console.log(`🔄 탭 전환: ${page}`);

    // Update navigation state
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    
    const activeTab = document.querySelector(`[data-page="${page}"]`);
    if (activeTab) {
        activeTab.classList.add('active');
    }

    // Update welcome subtitle and content
    const welcomeSubtitle = document.querySelector('.welcome-subtitle');
    const chatWithProfile = document.querySelector('.chat-with-profile');
    const examplesSection = document.querySelector('.examples-section');
    
    // Hide all content sections first
    const contentSections = [
        'curriculumContent',
        'mentorContent', 
        'datasourceContent',
        'chatWithProfile',
        'examplesSection'
    ];
    
    contentSections.forEach(sectionId => {
        const element = document.getElementById(sectionId) || document.querySelector(`.${sectionId}`);
        if (element) {
            element.style.display = 'none';
        }
    });

    // Remove mentor profile section when switching away from profile page
    const mentorProfileSection = document.getElementById('mentorProfileSection');
    if (mentorProfileSection) {
        mentorProfileSection.remove();
    }
    
    // Clear mentor selection when not on profile page
    if (page !== 'profile') {
        clearMentorSelection();
    }
    
    // Handle different page types
    switch (page) {
        case 'datasource':
            handleDatasourcePage(welcomeSubtitle);
            break;
        case 'mentor':
            handleMentorPage(welcomeSubtitle);
            break;
        case 'curriculum':
            handleCurriculumPage(welcomeSubtitle);
            break;
        case 'profile':
            handleProfilePage(welcomeSubtitle, chatWithProfile, examplesSection);
            break;
        default:
            handleChatPage(welcomeSubtitle, chatWithProfile, examplesSection);
            break;
    }
}

// Clear mentor selection
function clearMentorSelection() {
    selectedMentors = [];
    finalSelectedMentors = [];
    
    StorageManager.mentors.clear();
    
    const selectedMentorsDisplay = document.getElementById('selectedMentors');
    if (selectedMentorsDisplay) {
        selectedMentorsDisplay.innerHTML = '<div style="color: #6b7280; font-size: 14px;">선택된 멘토들이 여기에 표시됩니다</div>';
    }
    
    // Clear mentor card selection state
    const mentorCards = document.querySelectorAll('.mentor-card');
    mentorCards.forEach(card => {
        card.style.borderColor = '#e5e7eb';
        card.style.background = 'white';
    });
}

// Handle datasource page
function handleDatasourcePage(welcomeSubtitle) {
    welcomeSubtitle.innerHTML = '<span class="highlight">학습 데이터 원천</span> 관리';
    
    let datasourceContent = document.getElementById('datasourceContent');
    if (!datasourceContent) {
        datasourceContent = createDatasourceContent();
    }
    
    datasourceContent.style.display = 'block';
}

// Handle mentor page  
function handleMentorPage(welcomeSubtitle) {
    welcomeSubtitle.innerHTML = '<span class="highlight">AI 멘토</span>와 상담하기';
    
    let mentorContent = document.getElementById('mentorContent');
    if (!mentorContent) {
        mentorContent = createMentorContent();
    }
    
    mentorContent.style.display = 'block';
}

// Handle curriculum page
function handleCurriculumPage(welcomeSubtitle) {
    welcomeSubtitle.innerHTML = '나의 <span class="highlight">개인화 커리큘럼</span>';
    
    let curriculumContent = document.getElementById('curriculumContent');
    if (!curriculumContent) {
        curriculumContent = createCurriculumContent();
    }
    
    showCurriculumContent(curriculumContent);
}

// Handle profile page
function handleProfilePage(welcomeSubtitle, chatWithProfile, examplesSection) {
    welcomeSubtitle.innerHTML = '<span class="highlight">전문 분야별 AI 멘토</span>들과 상담하기';
    
    if (chatWithProfile) chatWithProfile.style.display = 'flex';
    if (examplesSection) examplesSection.style.display = 'block';
    
    // Update initial message for mentor consultation
    const initialMessage = document.getElementById('initialMessage');
    if (initialMessage) {
        initialMessage.innerHTML = '안녕하세요! 사내 지식이 풍부한 전문분야별 AI 멘토들이 여러분의 질문에 답변해드립니다. 궁금한 분야나 주제를 말씀해주시면, 해당 영역의 멘토들이 각자의 전문성을 살려 도움을 드리겠습니다.';
    }
}

// Handle chat page (default)
function handleChatPage(welcomeSubtitle, chatWithProfile, examplesSection) {
    welcomeSubtitle.innerHTML = '<span class="highlight">맞춤형 학습</span> 멘토';
    
    if (chatWithProfile) chatWithProfile.style.display = 'flex';
    if (examplesSection) examplesSection.style.display = 'block';
    
    // Update initial message for learning
    const initialMessage = document.getElementById('initialMessage');
    if (initialMessage) {
        initialMessage.innerHTML = '안녕하세요! LearningMate의 학습 멘토입니다. 어떤 주제에 대해 배우고 싶으신지 알려주세요. 맞춤형 학습 계획을 함께 만들어보겠습니다.';
    }
}

// Create datasource content
function createDatasourceContent() {
    const datasourceContent = document.createElement('div');
    datasourceContent.id = 'datasourceContent';
    datasourceContent.className = 'content-section';
    datasourceContent.innerHTML = `
        <div class="section-header">
            <h2>커리큘럼 생성 데이터 원천</h2>
            <p>AI가 맞춤형 커리큘럼을 생성할 때 참고하는 데이터 소스를 관리합니다.</p>
        </div>
        
        <div class="datasource-grid">
            <div class="datasource-card">
                <i class="fas fa-file-alt datasource-icon"></i>
                <h3>사내 문서</h3>
                <p>기술 문서, 가이드라인, 매뉴얼</p>
                <div class="file-types">
                    <div class="file-type-icon"><i class="fas fa-file-pdf"></i></div>
                    <div class="file-type-icon"><i class="fas fa-file-powerpoint"></i></div>
                </div>
                <div class="status-badge active">
                    <i class="fas fa-check-circle"></i> 127개 연동됨
                </div>
            </div>
            
            <div class="datasource-card">
                <i class="fas fa-video datasource-icon"></i>
                <h3>교육 영상</h3>
                <p>사내 교육 콘텐츠, 웨비나</p>
                <div class="kmooc-badge">K-MOOC</div>
                <div class="status-badge active">
                    <i class="fas fa-check-circle"></i> 42개 연동됨
                </div>
            </div>
            
            <div class="datasource-card">
                <i class="fas fa-database datasource-icon"></i>
                <h3>외부 지식베이스</h3>
                <p>업계 표준, 참고 자료</p>
                <div class="status-badge inactive">
                    <i class="fas fa-times-circle"></i> 연동 대기중
                </div>
            </div>
        </div>
    `;
    
    const welcomeSection = document.querySelector('.welcome-section');
    welcomeSection.parentNode.insertBefore(datasourceContent, welcomeSection.nextSibling);
    
    return datasourceContent;
}

// Initialize navigation
function initializeNavigation() {
    // Set up navigation click handlers
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const page = link.dataset.page;
            if (page) {
                switchToTab(page);
            }
        });
    });
    
    // Initialize with chat tab
    switchToTab('chat');
}

// Export functions for global use
window.switchToTab = switchToTab;
window.clearMentorSelection = clearMentorSelection;
window.initializeNavigation = initializeNavigation;
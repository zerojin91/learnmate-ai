/* =============================================================================
   Navigation and Tab Management
   ============================================================================= */


// Navigation and content switching
function switchToTab(page) {
    console.log(`🔄 탭 전환: ${page}`);

    // 페이지 상단으로 스크롤
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });

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
 
        'datasourceContent'
    ];
    
    contentSections.forEach(sectionId => {
        const element = document.getElementById(sectionId);
        if (element) {
            element.style.display = 'none';
        }
    });
    
    // Hide chat and examples sections properly
    if (chatWithProfile) chatWithProfile.style.display = 'none';
    if (examplesSection) examplesSection.style.display = 'none';

    
    // Handle different page types
    switch (page) {
        case 'datasource':
            handleDatasourcePage(welcomeSubtitle);
            break;
        case 'curriculum':
            handleCurriculumPage(welcomeSubtitle);
            break;
        default:
            handleChatPage(welcomeSubtitle, chatWithProfile, examplesSection);
            break;
    }
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


// Handle curriculum page
function handleCurriculumPage(welcomeSubtitle) {
    welcomeSubtitle.innerHTML = '나의 <span class="highlight">개인화 커리큘럼</span>';

    let curriculumContent = document.getElementById('curriculumContent');
    if (!curriculumContent) {
        curriculumContent = createCurriculumContent();
    }

    // 커리큘럼 생성 중인지 확인
    const isGenerating = window.isGeneratingCurriculum || false;
    const hasGenerationStartTime = window.curriculumGenerationStartTime || false;

    console.log('🔍 커리큘럼 탭 전환 - 생성 상태:', isGenerating, '시작 시간:', hasGenerationStartTime ? ' 있음' : '없음');

    // 진행 상황 추적 중이면 로딩 상태 표시
    if (isGenerating && hasGenerationStartTime) {
        console.log('📊 커리큘럼 생성 진행 중 - 로딩 상태 유지');
        // 로딩 상태가 이미 표시되어 있으므로 showCurriculumContent 호출하지 않음
        curriculumContent.style.display = 'block';
        return;
    }

    // 안전하게 커리큘럼 콘텐츠 표시 (생성 중이 아닐 때만)
    try {
        if (typeof showCurriculumContent === 'function') {
            console.log('📚 일반 커리큘럼 콘텐츠 표시 시도');
            showCurriculumContent(curriculumContent).catch(error => {
                console.log('📝 커리큘럼 로드 중 예상된 오류:', error.message);
                // 기본 빈 상태 표시
                curriculumContent.innerHTML = `
                    <div class="empty-curriculum">
                        <div class="empty-icon">📚</div>
                        <h3>아직 생성된 커리큘럼이 없습니다</h3>
                        <p>채팅 탭에서 학습 프로필을 완성한 후 커리큘럼을 생성해보세요.</p>
                    </div>
                `;
            });
        } else {
            console.warn('showCurriculumContent 함수를 찾을 수 없습니다');
        }
    } catch (error) {
        console.log('📝 커리큘럼 페이지 처리 중 오류:', error.message);
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
    datasourceContent.style.cssText = `
        width: 900px;
        background: white;
        border-radius: 16px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.1);
        padding: 40px;
        margin: 20px 0;
    `;

    // 원본 HTML에서 가져온 완전한 데이터 원천 UI
    datasourceContent.innerHTML = `
        <div style="margin-bottom: 30px;">
            <h2 style="font-size: 24px; font-weight: 700; color: #1f2937; margin-bottom: 10px;">
                커리큘럼 생성 데이터 원천
            </h2>
            <p style="color: #6b7280; font-size: 14px;">
                AI가 맞춤형 커리큘럼을 생성할 때 참고하는 데이터 소스를 관리합니다.
            </p>
        </div>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px;">
            <!-- 사내 문서 -->
            <div style="
                background: white;
                padding: 25px;
                border-radius: 12px;
                border: 1px solid #e5e7eb;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                position: relative;
                overflow: hidden;
            ">
                <i class="fas fa-file-alt" style="font-size: 32px; margin-bottom: 15px; color: #667eea;"></i>
                <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 8px; color: #1f2937;">사내 문서</h3>
                <p style="font-size: 13px; color: #6b7280; margin-bottom: 15px;">기술 문서, 가이드라인, 매뉴얼</p>

                <!-- 파일 형식 아이콘들 -->
                <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                    <div style="
                        width: 45px;
                        height: 45px;
                        background: #f3f4f6;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                    ">
                        <i class="fas fa-file-pdf" style="color: #DC2626; font-size: 20px;"></i>
                    </div>
                    <div style="
                        width: 45px;
                        height: 45px;
                        background: #f3f4f6;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                    ">
                        <i class="fas fa-file-powerpoint" style="color: #EA580C; font-size: 20px;"></i>
                    </div>
                </div>

                <div style="
                    background: #f3f4f6;
                    padding: 8px 12px;
                    border-radius: 8px;
                    font-size: 12px;
                    display: inline-block;
                    color: #4b5563;
                ">
                    <i class="fas fa-check-circle" style="color: #10b981;"></i> 127개 연동됨
                </div>
            </div>

            <!-- 교육 영상 -->
            <div style="
                background: white;
                padding: 25px;
                border-radius: 12px;
                border: 1px solid #e5e7eb;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            ">
                <i class="fas fa-video" style="font-size: 32px; margin-bottom: 15px; color: #8b5cf6;"></i>
                <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 8px; color: #1f2937;">교육 영상</h3>
                <p style="font-size: 13px; color: #6b7280; margin-bottom: 15px;">사내 교육 콘텐츠, 웨비나</p>

                <!-- K-MOOC 로고 -->
                <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                    <div style="
                        width: 45px;
                        height: 45px;
                        background: #f3f4f6;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                        font-weight: 700;
                        font-size: 10px;
                        color: #1E40AF;
                    ">
                        K-MOOC
                    </div>
                </div>

                <div style="
                    background: #f3f4f6;
                    padding: 8px 12px;
                    border-radius: 8px;
                    font-size: 12px;
                    display: inline-block;
                    color: #4b5563;
                ">
                    <i class="fas fa-check-circle" style="color: #10b981;"></i> 1개 연동됨
                </div>
            </div>

            <!-- 외부 웹 -->
            <div style="
                background: white;
                padding: 25px;
                border-radius: 12px;
                border: 1px solid #e5e7eb;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            ">
                <i class="fas fa-globe" style="font-size: 32px; margin-bottom: 15px; color: #a78bfa;"></i>
                <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 8px; color: #1f2937;">외부 웹</h3>
                <p style="font-size: 13px; color: #6b7280; margin-bottom: 15px;">공식 문서, 튜토리얼, 블로그</p>

                <!-- DuckDuckGo 로고 -->
                <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                    <div style="
                        width: 45px;
                        height: 45px;
                        background: #f3f4f6;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                        padding: 8px;
                    ">
                        <img src="https://upload.wikimedia.org/wikipedia/en/thumb/8/88/DuckDuckGo_logo.svg/1200px-DuckDuckGo_logo.svg.png"
                             alt="DuckDuckGo"
                             style="width: 100%; height: 100%; object-fit: contain;"
                        />
                    </div>
                </div>

                <div style="
                    background: #f3f4f6;
                    padding: 8px 12px;
                    border-radius: 8px;
                    font-size: 12px;
                    display: inline-block;
                    color: #4b5563;
                ">
                    <i class="fas fa-check-circle" style="color: #10b981;"></i> 1개 연동됨
                </div>
            </div>
        </div>

        <!-- 최근 업데이트 -->
        <div style="
            background: #f9fafb;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #e5e7eb;
        ">
            <h3 style="font-size: 16px; font-weight: 600; color: #374151; margin-bottom: 15px;">
                <i class="fas fa-sync-alt" style="margin-right: 8px; color: #6366f1;"></i>
                최근 업데이트된 데이터
            </h3>
            <div style="space-y: 10px;">
                <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e5e7eb;">
                    <span style="color: #4b5563; font-size: 14px;">
                        <i class="fas fa-file-alt" style="color: #667eea; margin-right: 8px;"></i>
                        Python 개발 가이드 v2.1
                    </span>
                    <span style="color: #9ca3af; font-size: 12px;">2시간 전</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e5e7eb;">
                    <span style="color: #4b5563; font-size: 14px;">
                        <i class="fas fa-video" style="color: #f5576c; margin-right: 8px;"></i>
                        React 18 마이그레이션 웨비나
                    </span>
                    <span style="color: #9ca3af; font-size: 12px;">5시간 전</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 10px 0;">
                    <span style="color: #4b5563; font-size: 14px;">
                        <i class="fas fa-globe" style="color: #00f2fe; margin-right: 8px;"></i>
                        AWS Lambda 공식 문서
                    </span>
                    <span style="color: #9ca3af; font-size: 12px;">1일 전</span>
                </div>
            </div>
        </div>

        <!-- 액션 버튼들 -->
        <div style="margin-top: 30px; text-align: center; display: flex; gap: 15px; justify-content: center;">
            <button style="
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                padding: 12px 30px;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s;
                width: 220px;
            " onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                <i class="fas fa-plus-circle" style="margin-right: 8px;"></i>
                새 데이터 원천 추가
            </button>

            <button onclick="switchToTab('chat')" style="
                background: linear-gradient(135deg, #a855f7, #ec4899);
                color: white;
                border: none;
                padding: 12px 30px;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s;
                width: 220px;
            " onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                <i class="fas fa-bullseye" style="margin-right: 8px;"></i>
                맞춤형 학습 추천 시작
            </button>
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
window.initializeNavigation = initializeNavigation;
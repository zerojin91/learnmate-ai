/* =============================================================================
   Curriculum Management Functions
   ============================================================================= */

// Curriculum generation function
async function generateCurriculum() {
    const generateBtn = document.getElementById('generateCurriculumBtn');
    const durationSelect = document.getElementById('learningDuration');
    
    if (!generateBtn || !durationSelect) {
        console.error('커리큘럼 생성 요소를 찾을 수 없습니다.');
        return;
    }
    
    const selectedDuration = durationSelect.value;
    console.log(`🚀 커리큘럼 생성 시작 - 기간: ${selectedDuration}개월`);
    
    // 1. Set generation state
    isGeneratingCurriculum = true;
    
    // 2. Switch to curriculum tab first
    switchToTab('curriculum');
    
    // 3. Show loading state
    const curriculumContent = document.getElementById('curriculumContent');
    if (curriculumContent) {
        displayLoadingState(curriculumContent);
    }
    
    // 4. Disable button and show loading state
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 커리큘럼 생성 중...';
    
    try {
        // Send curriculum generation request message
        const curriculumMessage = `${selectedDuration}개월 학습 기간으로 맞춤형 커리큘럼을 생성해주세요.`;
        messageInput.value = curriculumMessage;
        
        // Call general sendMessage function
        await sendMessage();
        
        // Real-time data reception flag
        window.curriculumDataReceived = false;
        
        console.log('✅ 커리큘럼 생성 요청 완료');
        
    } catch (error) {
        console.error('❌ 커리큘럼 생성 오류:', error);
        isGeneratingCurriculum = false;
        showNotification('커리큘럼 생성 중 오류가 발생했습니다. 다시 시도해주세요.', 'error');
        
        // Restore curriculum page on error
        const curriculumContent = document.getElementById('curriculumContent');
        if (curriculumContent) {
            showCurriculumContent(curriculumContent);
        }
        
    } finally {
        // Restore button
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i class="fas fa-magic"></i> 맞춤형 커리큘럼 생성';
    }
}

// Check curriculum completion status
async function checkCurriculumCompletion() {
    console.log('🔍 커리큘럼 완료 상태 재확인 시작');
    
    try {
        // Check recently generated curriculum
        const curriculumData = StorageManager.curriculum.get();
        if (curriculumData) {
            console.log('✅ 커리큘럼 발견 - 생성 완료 처리');
            
            // Clear generation completion flag
            isGeneratingCurriculum = false;
            
            // Display curriculum
            const curriculumContent = document.getElementById('curriculumContent');
            if (curriculumContent) {
                displayCurriculumCards(curriculumContent, curriculumData);
                showNotification('커리큘럼이 완성되었습니다!', 'success');
            }
            
            return;
        }
        
        // Only perform real-time checking (remove timeout)
        console.log('⏳ 커리큘럼 생성을 계속 기다립니다 (타임아웃 없음)');
        
    } catch (error) {
        console.error('커리큘럼 완료 확인 오류:', error);
        isGeneratingCurriculum = false;
    }
}

// Show curriculum content
async function showCurriculumContent(curriculumContent) {
    // Check existing curriculum in localStorage first
    const existingCurriculum = StorageManager.curriculum.get();

    if (existingCurriculum) {
        console.log('📚 기존 커리큘럼 표시');
        displayCurriculumCards(curriculumContent, existingCurriculum);
    } else {
        // Try to load curriculum from server
        console.log('🔄 서버에서 커리큘럼 데이터 로드 시도');
        const sessionId = getSessionId();

        if (sessionId) {
            try {
                const response = await fetch(`/api/curriculum/${sessionId}`);
                const curriculumData = await response.json();

                if (response.ok && curriculumData && !curriculumData.error) {
                    console.log('✅ 서버에서 커리큘럼 데이터 로드 성공');

                    // Save to localStorage for future use
                    StorageManager.curriculum.set(curriculumData);

                    // Display curriculum
                    displayCurriculumCards(curriculumContent, curriculumData);
                    return;
                } else {
                    console.log('📝 아직 생성된 커리큘럼이 없습니다:', curriculumData.error || 'No curriculum found');
                }
            } catch (error) {
                console.log('📝 커리큘럼 로드 시도 실패 (정상적임):', error.message);
                // 이는 정상적인 상황입니다 - 아직 커리큘럼이 생성되지 않은 경우
            }
        }

        // Fallback: show loading or empty state
        if (isGeneratingCurriculum) {
            console.log('⏳ 커리큘럼 생성 중 - 로딩 표시');
            displayLoadingState(curriculumContent);
        } else {
            console.log('📝 커리큘럼 없음 - 안내 메시지 표시');
            displayEmptyState(curriculumContent);
        }
    }

    curriculumContent.style.display = 'block';
}

// Display loading state
function displayLoadingState(container) {
    container.innerHTML = `
        <div class="curriculum-loading">
            <div class="loading-spinner">
                <i class="fas fa-spinner fa-spin"></i>
            </div>
            <h3>맞춤형 커리큘럼 생성 중...</h3>
            <p>사용자의 학습 프로필을 바탕으로 최적의 학습 계획을 만들고 있습니다.</p>
            <div class="loading-steps">
                <div class="loading-step active">
                    <i class="fas fa-user-check"></i>
                    <span>학습 프로필 분석</span>
                </div>
                <div class="loading-step active">
                    <i class="fas fa-book-open"></i>
                    <span>학습 자료 매칭</span>
                </div>
                <div class="loading-step">
                    <i class="fas fa-calendar-alt"></i>
                    <span>주차별 계획 수립</span>
                </div>
            </div>
        </div>
    `;
}

// Display empty state
function displayEmptyState(container) {
    container.innerHTML = `
        <div class="curriculum-empty">
            <div class="empty-icon">
                <i class="fas fa-graduation-cap"></i>
            </div>
            <h3>아직 생성된 커리큘럼이 없습니다</h3>
            <p>학습 프로필을 완성한 후, 프로필 카드에서 "맞춤형 커리큘럼 생성" 버튼을 클릭하여 개인화된 학습 계획을 만들어보세요.</p>
            
            <div class="profile-status">
                ${(() => {
                    const status = getProfileStatus();
                    return `
                        <div class="status-header">
                            <h4>학습 프로필 현황</h4>
                            <span class="completion-badge ${status.isComplete ? 'complete' : 'incomplete'}">
                                ${status.completed}/${status.total} 완료
                            </span>
                        </div>
                        <div class="status-steps">
                            ${['topic', 'constraints', 'goal'].map((step, index) => {
                                const isCompleted = status.completedSteps.includes(step);
                                const labels = {
                                    topic: '학습 주제',
                                    constraints: '학습 조건', 
                                    goal: '학습 목표'
                                };
                                return `
                                    <div class="status-step ${isCompleted ? 'completed' : ''}">
                                        <i class="fas ${isCompleted ? 'fa-check-circle' : 'fa-circle'}"></i>
                                        <span>${labels[step]}</span>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    `;
                })()}
            </div>
            
            ${!getProfileStatus().isComplete ? `
                <div class="empty-actions">
                    <button onclick="switchToTab('chat')" class="btn btn-primary">
                        <i class="fas fa-comments"></i>
                        학습 프로필 완성하기
                    </button>
                </div>
            ` : ''}
        </div>
    `;
}

// Display curriculum cards
function displayCurriculumCards(container, data) {
    const modules = data.modules || [];
    let cardsHtml = '';

    // 진행도 상태 가져오기
    const completedWeeks = StorageManager.curriculum.progress.get() || [];
    const totalWeeks = modules.length;
    const completedCount = completedWeeks.length;
    const progressPercentage = totalWeeks > 0 ? (completedCount / totalWeeks) * 100 : 0;

    // 헤더 정보
    cardsHtml += `
        <div style="margin-bottom: 24px;">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                <div style="
                    background: linear-gradient(135deg, #a855f7, #ec4899);
                    color: white;
                    padding: 6px 12px;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    text-transform: uppercase;
                ">
                    ${data.level || 'Beginner'}
                </div>
                <div style="color: #6b7280; font-size: 14px;">
                    ${data.duration_weeks || 0}주 과정
                </div>
                <div style="
                    background: ${progressPercentage > 0 ? '#10b981' : '#f3f4f6'};
                    color: ${progressPercentage > 0 ? 'white' : '#6b7280'};
                    padding: 4px 8px;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: 600;
                    margin-left: auto;
                ">
                    ${completedCount}/${totalWeeks} 완료
                </div>
            </div>
            <h2 style="
                font-size: 18px;
                font-weight: 700;
                color: #1f2937;
                margin: 0 0 16px 0;
            ">
                ${data.title || '커리큘럼'}
            </h2>

            <!-- 학습 진행도 트래커 -->
            <div style="
                background: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 20px;
            ">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                    <h3 style="
                        font-size: 14px;
                        font-weight: 600;
                        color: #374151;
                        margin: 0;
                    ">학습 진행도</h3>
                    <span style="
                        font-size: 12px;
                        color: #6b7280;
                        font-weight: 500;
                    ">${Math.round(progressPercentage)}% 완료</span>
                </div>

                <!-- 진행바 -->
                <div style="
                    background: #e5e7eb;
                    height: 6px;
                    border-radius: 3px;
                    overflow: hidden;
                    margin-bottom: 16px;
                ">
                    <div style="
                        background: linear-gradient(90deg, #a855f7, #ec4899);
                        height: 100%;
                        width: ${progressPercentage}%;
                        transition: width 0.3s ease;
                        border-radius: 3px;
                    "></div>
                </div>

                <!-- 주차별 단계 표시 -->
                <div style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    gap: 4px;
                    overflow-x: auto;
                    padding: 4px 0;
                ">
                    ${modules.map((module, index) => {
                        const isCompleted = completedWeeks.includes(index);
                        const weekColor = index < 4 ? '#a855f7' : index < 8 ? '#ec4899' : '#10b981';
                        return `
                            <div style="
                                display: flex;
                                flex-direction: column;
                                align-items: center;
                                min-width: 50px;
                                position: relative;
                            ">
                                <div style="
                                    width: 32px;
                                    height: 32px;
                                    border-radius: 50%;
                                    background: ${isCompleted ? weekColor : '#e5e7eb'};
                                    color: ${isCompleted ? 'white' : '#9ca3af'};
                                    display: flex;
                                    align-items: center;
                                    justify-content: center;
                                    font-size: 12px;
                                    font-weight: 600;
                                    transition: all 0.3s ease;
                                    cursor: pointer;
                                    border: 2px solid ${isCompleted ? weekColor : '#e5e7eb'};
                                    box-shadow: ${isCompleted ? '0 2px 8px rgba(168, 85, 247, 0.3)' : 'none'};
                                " onclick="toggleModuleDetail(${index})">
                                    ${isCompleted ? '✓' : (index + 1)}
                                </div>
                                <div style="
                                    font-size: 9px;
                                    color: #6b7280;
                                    text-align: center;
                                    margin-top: 4px;
                                    max-width: 40px;
                                    overflow: hidden;
                                    text-overflow: ellipsis;
                                    white-space: nowrap;
                                ">
                                    ${index + 1}주차
                                </div>
                                ${index < modules.length - 1 ? `
                                    <div style="
                                        position: absolute;
                                        top: 16px;
                                        right: -27px;
                                        width: 20px;
                                        height: 2px;
                                        background: ${index < completedCount - 1 ? weekColor : '#e5e7eb'};
                                        z-index: 1;
                                    "></div>
                                ` : ''}
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        </div>
    `;

    // 모듈 카드들을 그리드로 배치 (고정 높이 카드)
    const rows = Math.ceil(modules.length / 4);
    const gridHeight = rows * 160 + (rows - 1) * 12; // 카드 높이 160px + 간격 12px
    cardsHtml += `<div id="curriculumGrid" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; min-height: ${gridHeight}px; height: auto;">`;

    modules.forEach((module, index) => {
        const weekColor = index < 4 ? '#a855f7' : index < 8 ? '#ec4899' : '#10b981';
        cardsHtml += `
            <div id="card-${index}" class="curriculum-card" style="
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 12px;
                cursor: pointer;
                transition: all 0.3s ease;
                height: 160px;
                position: relative;
                overflow: hidden;
                display: flex;
                flex-direction: column;
            "
            onmouseover="this.style.borderColor='${weekColor}'; this.style.boxShadow='0 2px 8px rgba(168, 85, 247, 0.1)'"
            onmouseout="this.style.borderColor='#e5e7eb'; this.style.boxShadow='none'"
            onclick="toggleModuleDetail(${index})">

                <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
                    <div style="
                        background: ${weekColor};
                        color: white;
                        width: 20px;
                        height: 20px;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 10px;
                        font-weight: 600;
                    ">
                        ${module.week || index + 1}
                    </div>
                    <div style="color: #6b7280; font-size: 10px; font-weight: 500;">
                        ${module.estimated_hours || 8}시간
                    </div>
                </div>

                <h3 style="
                    font-size: 12px;
                    font-weight: 600;
                    color: #1f2937;
                    margin: 0 0 6px 0;
                    line-height: 1.3;
                    display: -webkit-box;
                    -webkit-line-clamp: 2;
                    -webkit-box-orient: vertical;
                    overflow: hidden;
                ">
                    ${module.title || `${index + 1}주차 학습`}
                </h3>

                <p id="description-${index}" style="
                    font-size: 10px;
                    color: #6b7280;
                    margin: 0 0 8px 0;
                    line-height: 1.3;
                    display: -webkit-box;
                    -webkit-line-clamp: 3;
                    -webkit-box-orient: vertical;
                    overflow: hidden;
                    flex: 1;
                    min-height: 0;
                ">
                    ${module.description || '이번 주차의 학습 내용을 다룹니다.'}
                </p>

                ${module.key_concepts && module.key_concepts.length > 0 ? `
                    <div id="concepts-${index}" style="margin-top: 4px; display: flex; gap: 2px; flex-wrap: wrap;">
                        ${module.key_concepts.slice(0, 2).map(concept => `
                            <span style="
                                background: #f3f4f6;
                                color: #6b7280;
                                padding: 2px 4px;
                                border-radius: 3px;
                                font-size: 8px;
                                font-weight: 500;
                                max-width: 80px;
                                overflow: hidden;
                                text-overflow: ellipsis;
                                white-space: nowrap;
                                display: inline-block;
                            ">${concept}</span>
                        `).join('')}
                        ${module.key_concepts.length > 2 ? `<span style="color: #9ca3af; font-size: 8px;">+${module.key_concepts.length - 2}</span>` : ''}
                    </div>
                ` : ''}
            </div>
        `;
    });

    cardsHtml += '</div>';
    container.innerHTML = cardsHtml;
}

// Create module card
function createModuleCard(module, index, completedWeeks) {
    const isCompleted = completedWeeks.includes(index);
    
    return `
        <div class="module-card ${isCompleted ? 'completed' : ''}">
            <div class="module-header">
                <div class="module-number">${index + 1}주차</div>
                <div class="module-title">
                    <h3>${module.title}</h3>
                    <p>${module.description || '이번 주차의 학습 내용을 다룹니다.'}</p>
                </div>
                <div class="module-status">
                    ${isCompleted ? 
                        '<i class="fas fa-check-circle completed"></i>' : 
                        '<i class="far fa-circle pending"></i>'
                    }
                </div>
            </div>
            
            <div class="module-content">
                ${module.topics ? `
                    <div class="module-topics">
                        <h4><i class="fas fa-list"></i> 학습 주제</h4>
                        <ul>
                            ${module.topics.map(topic => `<li>${topic}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
                
                ${module.resources ? createResourceSection(module.resources) : ''}
            </div>
            
            <div class="module-actions">
                <button onclick="toggleModuleCompletion(${index})" class="btn ${isCompleted ? 'btn-outline' : 'btn-primary'}">
                    <i class="fas ${isCompleted ? 'fa-undo' : 'fa-check'}"></i>
                    ${isCompleted ? '완료 취소' : '학습 완료'}
                </button>
            </div>
        </div>
    `;
}

// Create resource section
function createResourceSection(resources) {
    let resourcesHtml = '<div class="module-resources"><h4><i class="fas fa-folder-open"></i> 학습 자료</h4>';
    
    if (resources.videos && resources.videos.length > 0) {
        resourcesHtml += `
            <div class="resource-group">
                <h5><i class="fas fa-play-circle"></i> 동영상 강의</h5>
                <div class="resource-list">
                    ${resources.videos.map((video, idx) => `
                        <a href="${video.url}" target="_blank" class="resource-item video">
                            <div class="resource-icon">${idx + 1}</div>
                            <div class="resource-info">
                                <div class="resource-title">${video.title}</div>
                                <div class="resource-duration">${video.duration || '60분'}</div>
                            </div>
                            <div class="resource-action">▶️ 재생</div>
                        </a>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    if (resources.documents && resources.documents.length > 0) {
        resourcesHtml += `
            <div class="resource-group">
                <h5><i class="fas fa-file-alt"></i> 문서 자료</h5>
                <div class="resource-list">
                    ${resources.documents.map((doc, idx) => `
                        <a href="${doc.url}" target="_blank" class="resource-item document">
                            <div class="resource-icon">${idx + 1}</div>
                            <div class="resource-info">
                                <div class="resource-title">${doc.title}</div>
                            </div>
                            <div class="resource-action">📁 다운로드</div>
                        </a>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    if (resources.links && resources.links.length > 0) {
        resourcesHtml += `
            <div class="resource-group">
                <h5><i class="fas fa-external-link-alt"></i> 참고 링크</h5>
                <div class="resource-list">
                    ${resources.links.map((link, idx) => `
                        <a href="${link.url}" target="_blank" class="resource-item link">
                            <div class="resource-icon">${idx + 1}</div>
                            <div class="resource-info">
                                <div class="resource-title">${link.title}</div>
                            </div>
                            <div class="resource-action">🔗 링크</div>
                        </a>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    resourcesHtml += '</div>';
    return resourcesHtml;
}

// Toggle module completion
function toggleModuleCompletion(moduleIndex) {
    const completedWeeks = StorageManager.curriculum.progress.get() || [];
    const isCompleted = completedWeeks.includes(moduleIndex);
    
    let updatedWeeks;
    if (isCompleted) {
        // Remove from completed
        updatedWeeks = completedWeeks.filter(week => week !== moduleIndex);
        StorageManager.curriculum.progress.set(updatedWeeks);
        showNotification(`${moduleIndex + 1}주차 완료를 취소했습니다`);
    } else {
        // Add to completed
        updatedWeeks = [...completedWeeks, moduleIndex].sort((a, b) => a - b);
        StorageManager.curriculum.progress.set(updatedWeeks);
        showNotification(`${moduleIndex + 1}주차를 완료했습니다! 🎉`);
    }
    
    // Update progress bar immediately
    updateProgressBar(updatedWeeks);
    
    // Update module card state
    updateModuleCardState(moduleIndex, !isCompleted);
    
    // Optionally refresh entire display (can be commented out for better performance)
    // const curriculumContent = document.getElementById('curriculumContent');
    // const curriculumData = StorageManager.curriculum.get();
    // if (curriculumContent && curriculumData) {
    //     displayCurriculumCards(curriculumContent, curriculumData);
    // }
}

// Update progress bar
function updateProgressBar(completedWeeks) {
    const curriculumData = StorageManager.curriculum.get();
    if (!curriculumData || !curriculumData.modules) return;
    
    const totalModules = curriculumData.modules.length;
    const completedCount = completedWeeks.length;
    const progressPercent = (completedCount / totalModules) * 100;
    
    // Update progress bar
    const progressFill = document.querySelector('.progress-fill');
    const progressText = document.querySelector('.progress-summary p');
    
    if (progressFill) {
        progressFill.style.width = `${progressPercent}%`;
    }
    
    if (progressText) {
        progressText.textContent = `전체 진도: ${completedCount}/${totalModules} 주차 완료`;
    }
    
    // Update header progress indicator if exists
    const headerProgress = document.querySelector('.curriculum-meta .progress');
    if (headerProgress) {
        headerProgress.innerHTML = `<i class="fas fa-chart-line"></i> ${completedCount}/${totalModules} 완료`;
    }
}

// Update individual module card state
function updateModuleCardState(moduleIndex, isCompleted) {
    const moduleCards = document.querySelectorAll('.module-card');
    const targetCard = moduleCards[moduleIndex];
    
    if (!targetCard) return;
    
    // Update card appearance
    if (isCompleted) {
        targetCard.classList.add('completed');
    } else {
        targetCard.classList.remove('completed');
    }
    
    // Update status icon
    const statusIcon = targetCard.querySelector('.module-status i');
    if (statusIcon) {
        if (isCompleted) {
            statusIcon.className = 'fas fa-check-circle completed';
        } else {
            statusIcon.className = 'far fa-circle pending';
        }
    }
    
    // Update button
    const actionButton = targetCard.querySelector('.module-actions button');
    if (actionButton) {
        if (isCompleted) {
            actionButton.className = 'btn btn-outline';
            actionButton.innerHTML = '<i class="fas fa-undo"></i> 완료 취소';
        } else {
            actionButton.className = 'btn btn-primary';
            actionButton.innerHTML = '<i class="fas fa-check"></i> 학습 완료';
        }
    }
}

// Download curriculum
function downloadCurriculum() {
    const curriculumData = StorageManager.curriculum.get();
    if (!curriculumData) return;
    
    const dataStr = JSON.stringify(curriculumData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    
    const link = document.createElement('a');
    link.href = URL.createObjectURL(dataBlob);
    link.download = `curriculum_${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    
    showNotification('커리큘럼을 다운로드했습니다');
}

// Share curriculum
async function shareCurriculum() {
    const curriculumData = StorageManager.curriculum.get();
    if (!curriculumData) return;
    
    if (navigator.share) {
        try {
            await navigator.share({
                title: curriculumData.title || '맞춤형 학습 커리큘럼',
                text: `${curriculumData.modules.length}주 과정의 맞춤형 학습 커리큘럼입니다.`,
                url: window.location.href
            });
            showNotification('커리큘럼을 공유했습니다');
        } catch (error) {
            console.log('공유 취소됨');
        }
    } else {
        // Fallback: copy to clipboard
        const shareText = `${curriculumData.title}\n\n${curriculumData.modules.map((module, index) => 
            `${index + 1}주차: ${module.title}`
        ).join('\n')}`;
        
        navigator.clipboard.writeText(shareText).then(() => {
            showNotification('커리큘럼 정보를 클립보드에 복사했습니다');
        });
    }
}

// Create curriculum content container
function createCurriculumContent() {
    const curriculumContent = document.createElement('div');
    curriculumContent.id = 'curriculumContent';
    curriculumContent.className = 'content-section curriculum-section';
    
    const welcomeSection = document.querySelector('.welcome-section');
    welcomeSection.parentNode.insertBefore(curriculumContent, welcomeSection.nextSibling);
    
    return curriculumContent;
}

// Toggle module detail modal - using exact original unified HTML file modal style
function toggleModuleDetail(moduleIndex) {
    const curriculumData = StorageManager.curriculum.get();
    if (!curriculumData || !curriculumData.modules) return;

    const module = curriculumData.modules[moduleIndex];
    if (!module) return;

    // Check if modal already exists
    let modal = document.getElementById('moduleModal');
    if (modal) {
        modal.remove();
    }

    // Get completion status
    const completedWeeks = StorageManager.curriculum.progress.get() || [];
    const isCompleted = completedWeeks.includes(moduleIndex);

    const weekColor = moduleIndex < 4 ? '#a855f7' : moduleIndex < 8 ? '#ec4899' : '#10b981';

    // Create modern, refined modal HTML
    const modalHtml = `
        <div id="moduleModal" style="
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(12px);
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: center;
            animation: fadeIn 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            padding: 20px;
        " onclick="closeModuleModal(event)">
            <div style="
                background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
                border-radius: 24px;
                width: 100%;
                max-width: 1000px;
                max-height: 92vh;
                overflow: hidden;
                box-shadow:
                    0 32px 64px rgba(0, 0, 0, 0.12),
                    0 0 0 1px rgba(255, 255, 255, 0.8),
                    inset 0 1px 0 rgba(255, 255, 255, 0.9);
                animation: slideUp 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
                position: relative;
            " onclick="event.stopPropagation()">
                <!-- 헤더 -->
                <div style="
                    background: linear-gradient(135deg, ${weekColor}15 0%, ${weekColor}08 50%, transparent 100%);
                    border-bottom: 1px solid rgba(148, 163, 184, 0.1);
                    padding: 20px 28px;
                    position: relative;
                    overflow: hidden;
                ">
                    <!-- 배경 장식 -->
                    <div style="
                        position: absolute;
                        top: -50%;
                        right: -20%;
                        width: 200px;
                        height: 200px;
                        background: radial-gradient(circle, ${weekColor}12 0%, transparent 70%);
                        border-radius: 50%;
                        pointer-events: none;
                    "></div>

                    <button onclick="closeModuleModal()" style="
                        position: absolute;
                        top: 24px;
                        right: 24px;
                        background: rgba(255, 255, 255, 0.9);
                        backdrop-filter: blur(8px);
                        border: 1px solid rgba(148, 163, 184, 0.2);
                        color: #64748b;
                        font-size: 18px;
                        width: 40px;
                        height: 40px;
                        border-radius: 12px;
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                        font-weight: 300;
                        z-index: 10;
                    " onmouseover="this.style.background='rgba(255, 255, 255, 1)'; this.style.color='#374151'; this.style.transform='scale(1.05)'" onmouseout="this.style.background='rgba(255, 255, 255, 0.9)'; this.style.color='#64748b'; this.style.transform='scale(1)'">
                        ×
                    </button>

                    <div style="
                        background: linear-gradient(135deg, ${weekColor} 0%, ${weekColor}cc 100%);
                        color: white;
                        padding: 6px 12px;
                        border-radius: 50px;
                        font-size: 12px;
                        font-weight: 600;
                        margin-bottom: 12px;
                        display: inline-flex;
                        align-items: center;
                        gap: 6px;
                        box-shadow:
                            0 4px 12px ${weekColor}30,
                            0 0 0 1px rgba(255, 255, 255, 0.2);
                        position: relative;
                        z-index: 5;
                    ">
                        <span style="font-size: 12px;">📅</span>
                        Week ${moduleIndex + 1}
                    </div>

                    <h2 style="
                        margin: 0;
                        font-size: 22px;
                        font-weight: 700;
                        line-height: 1.2;
                        color: #0f172a;
                        letter-spacing: -0.01em;
                        position: relative;
                        z-index: 5;
                        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                        background-clip: text;
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                    ">
                        ${module.title}
                    </h2>

                    <p style="
                        margin: 10px 0 0 0;
                        color: #475569;
                        font-size: 14px;
                        line-height: 1.4;
                        font-weight: 400;
                        position: relative;
                        z-index: 5;
                    ">
                        ${module.description}
                    </p>
                </div>

                <!-- 컨텐츠 -->
                <div style="
                    padding: 0;
                    background: white;
                    max-height: calc(92vh - 140px);
                    overflow-y: auto;
                ">
                    <div style="padding: 24px;">
                    ${module.objectives ? `
                        <div style="
                            background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
                            border-radius: 16px;
                            padding: 20px;
                            margin-bottom: 20px;
                            border: 1px solid rgba(148, 163, 184, 0.1);
                            box-shadow:
                                0 8px 32px rgba(0, 0, 0, 0.04),
                                0 0 0 1px rgba(255, 255, 255, 0.8),
                                inset 0 1px 0 rgba(255, 255, 255, 0.9);
                            position: relative;
                            overflow: hidden;
                        ">
                            <!-- 배경 장식 -->
                            <div style="
                                position: absolute;
                                top: -30px;
                                right: -30px;
                                width: 100px;
                                height: 100px;
                                background: radial-gradient(circle, ${weekColor}08 0%, transparent 70%);
                                border-radius: 50%;
                                pointer-events: none;
                            "></div>

                            <h3 style="
                                font-size: 18px;
                                font-weight: 700;
                                color: #0f172a;
                                margin-bottom: 16px;
                                display: flex;
                                align-items: center;
                                gap: 10px;
                                position: relative;
                                z-index: 5;
                            ">
                                <span style="
                                    background: linear-gradient(135deg, ${weekColor} 0%, ${weekColor}cc 100%);
                                    color: white;
                                    width: 36px;
                                    height: 36px;
                                    border-radius: 12px;
                                    display: flex;
                                    align-items: center;
                                    justify-content: center;
                                    font-size: 16px;
                                    box-shadow:
                                        0 6px 12px ${weekColor}30,
                                        0 0 0 1px rgba(255, 255, 255, 0.2);
                                ">🎯</span>
                                학습 목표
                            </h3>
                            <div style="
                                display: grid;
                                gap: 12px;
                            ">
                                ${module.objectives.map((obj, idx) => `
                                    <div style="
                                        background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
                                        border: 1px solid rgba(148, 163, 184, 0.1);
                                        border-left: 4px solid ${weekColor};
                                        padding: 16px;
                                        border-radius: 12px;
                                        color: #334155;
                                        line-height: 1.5;
                                        font-weight: 500;
                                        position: relative;
                                        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                                        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
                                    " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 8px 32px rgba(0, 0, 0, 0.08)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0, 0, 0, 0.02)'">
                                        <div style="
                                            position: absolute;
                                            top: -10px;
                                            left: 12px;
                                            background: linear-gradient(135deg, ${weekColor} 0%, ${weekColor}cc 100%);
                                            color: white;
                                            width: 24px;
                                            height: 24px;
                                            border-radius: 50%;
                                            display: flex;
                                            align-items: center;
                                            justify-content: center;
                                            font-size: 11px;
                                            font-weight: 700;
                                            box-shadow:
                                                0 3px 8px ${weekColor}40,
                                                0 0 0 2px white;
                                        ">${idx + 1}</div>
                                        <div style="margin-top: 8px; font-size: 14px;">
                                            ${obj}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${module.key_concepts && module.key_concepts.length > 0 ? `
                        <div style="
                            background: white;
                            border-radius: 16px;
                            padding: 24px;
                            margin-bottom: 24px;
                            border: 1px solid #e2e8f0;
                            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
                        ">
                            <h3 style="
                                font-size: 20px;
                                font-weight: 700;
                                color: #1e293b;
                                margin-bottom: 20px;
                                display: flex;
                                align-items: center;
                                gap: 12px;
                            ">
                                <span style="
                                    background: linear-gradient(135deg, ${weekColor}20, ${weekColor}10);
                                    color: ${weekColor};
                                    width: 36px;
                                    height: 36px;
                                    border-radius: 12px;
                                    display: flex;
                                    align-items: center;
                                    justify-content: center;
                                    font-size: 16px;
                                ">🔑</span>
                                핵심 개념
                            </h3>
                            <div style="
                                display: grid;
                                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                                gap: 16px;
                            ">
                                ${module.key_concepts.map((concept, idx) => `
                                    <div style="
                                        background: linear-gradient(135deg, ${weekColor}08, ${weekColor}03);
                                        border: 2px solid ${weekColor}15;
                                        color: #475569;
                                        padding: 16px 20px;
                                        border-radius: 12px;
                                        font-size: 15px;
                                        font-weight: 600;
                                        text-align: center;
                                        position: relative;
                                        transition: all 0.2s ease;
                                        cursor: default;
                                    " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 8px 25px ${weekColor}20'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                                        <div style="
                                            position: absolute;
                                            top: -10px;
                                            right: 8px;
                                            background: ${weekColor};
                                            color: white;
                                            width: 20px;
                                            height: 20px;
                                            border-radius: 50%;
                                            display: flex;
                                            align-items: center;
                                            justify-content: center;
                                            font-size: 11px;
                                            font-weight: 700;
                                        ">${idx + 1}</div>
                                        ${concept}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${module.learning_outcomes && module.learning_outcomes.length > 0 ? `
                        <div style="
                            background: white;
                            border-radius: 16px;
                            padding: 24px;
                            margin-bottom: 24px;
                            border: 1px solid #e2e8f0;
                            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
                        ">
                            <h3 style="
                                font-size: 20px;
                                font-weight: 700;
                                color: #1e293b;
                                margin-bottom: 20px;
                                display: flex;
                                align-items: center;
                                gap: 12px;
                            ">
                                <span style="
                                    background: linear-gradient(135deg, ${weekColor}20, ${weekColor}10);
                                    color: ${weekColor};
                                    width: 36px;
                                    height: 36px;
                                    border-radius: 12px;
                                    display: flex;
                                    align-items: center;
                                    justify-content: center;
                                    font-size: 16px;
                                ">🏆</span>
                                학습 성과
                            </h3>
                            <div style="
                                display: grid;
                                gap: 12px;
                            ">
                                ${module.learning_outcomes.map((outcome, idx) => `
                                    <div style="
                                        background: #f8fafc;
                                        border: 1px solid #f1f5f9;
                                        border-left: 4px solid ${weekColor};
                                        padding: 16px;
                                        border-radius: 0 12px 12px 0;
                                        color: #475569;
                                        line-height: 1.6;
                                        font-weight: 500;
                                        position: relative;
                                    ">
                                        <div style="
                                            position: absolute;
                                            top: -8px;
                                            left: 12px;
                                            background: ${weekColor};
                                            color: white;
                                            width: 24px;
                                            height: 24px;
                                            border-radius: 50%;
                                            display: flex;
                                            align-items: center;
                                            justify-content: center;
                                            font-size: 12px;
                                            font-weight: 700;
                                        ">${idx + 1}</div>
                                        <div style="margin-top: 8px;">
                                            ${outcome}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${module.estimated_hours ? `
                        <div style="
                            background: white;
                            border-radius: 16px;
                            padding: 24px;
                            margin-bottom: 24px;
                            border: 1px solid #e2e8f0;
                            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
                        ">
                            <h3 style="
                                font-size: 20px;
                                font-weight: 700;
                                color: #1e293b;
                                margin-bottom: 20px;
                                display: flex;
                                align-items: center;
                                gap: 12px;
                            ">
                                <span style="
                                    background: linear-gradient(135deg, ${weekColor}20, ${weekColor}10);
                                    color: ${weekColor};
                                    width: 36px;
                                    height: 36px;
                                    border-radius: 12px;
                                    display: flex;
                                    align-items: center;
                                    justify-content: center;
                                    font-size: 16px;
                                ">⏰</span>
                                학습 시간
                            </h3>
                            <div style="
                                background: linear-gradient(135deg, ${weekColor}08, ${weekColor}03);
                                border: 2px solid ${weekColor}15;
                                color: #475569;
                                padding: 20px;
                                border-radius: 12px;
                                text-align: center;
                                font-size: 24px;
                                font-weight: 700;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                gap: 8px;
                            ">
                                <span style="font-size: 20px;">📚</span>
                                ${module.estimated_hours}시간
                            </div>
                            <div style="
                                text-align: center;
                                color: #64748b;
                                font-size: 14px;
                                margin-top: 12px;
                                font-weight: 500;
                            ">
                                예상 학습 소요 시간
                            </div>
                        </div>
                    ` : ''}

                    ${module.resources ? `
                        <div style="
                            background: white;
                            border-radius: 16px;
                            padding: 24px;
                            border: 1px solid #e2e8f0;
                            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
                        ">
                            <h3 style="
                                font-size: 20px;
                                font-weight: 700;
                                color: #1e293b;
                                margin-bottom: 24px;
                                display: flex;
                                align-items: center;
                                gap: 12px;
                            ">
                                <span style="
                                    background: linear-gradient(135deg, ${weekColor}20, ${weekColor}10);
                                    color: ${weekColor};
                                    width: 36px;
                                    height: 36px;
                                    border-radius: 12px;
                                    display: flex;
                                    align-items: center;
                                    justify-content: center;
                                    font-size: 16px;
                                ">📚</span>
                                학습 자료
                            </h3>

                            <!-- 탭 네비게이션 -->
                            <div style="
                                display: flex;
                                gap: 8px;
                                margin-bottom: 20px;
                                border-bottom: 1px solid #f1f5f9;
                                padding-bottom: 16px;
                            ">
                                ${module.resources.videos && module.resources.videos.length > 0 ? `
                                    <div style="
                                        background: linear-gradient(135deg, #fef3c7, #fde68a);
                                        color: #92400e;
                                        padding: 8px 16px;
                                        border-radius: 8px;
                                        font-size: 13px;
                                        font-weight: 600;
                                        display: flex;
                                        align-items: center;
                                        gap: 6px;
                                    ">
                                        📹 동영상 ${module.resources.videos.length}개
                                    </div>
                                ` : ''}
                                ${module.resources.web_links && module.resources.web_links.length > 0 ? `
                                    <div style="
                                        background: linear-gradient(135deg, #dbeafe, #bfdbfe);
                                        color: #1e40af;
                                        padding: 8px 16px;
                                        border-radius: 8px;
                                        font-size: 13px;
                                        font-weight: 600;
                                        display: flex;
                                        align-items: center;
                                        gap: 6px;
                                    ">
                                        🌐 웹자료 ${module.resources.web_links.length}개
                                    </div>
                                ` : ''}
                                ${module.resources.documents && module.resources.documents.length > 0 ? `
                                    <div style="
                                        background: linear-gradient(135deg, #ecfdf5, #d1fae5);
                                        color: #065f46;
                                        padding: 8px 16px;
                                        border-radius: 8px;
                                        font-size: 13px;
                                        font-weight: 600;
                                        display: flex;
                                        align-items: center;
                                        gap: 6px;
                                    ">
                                        📄 문서 ${module.resources.documents.length}개
                                    </div>
                                ` : ''}
                            </div>

                            <!-- 리소스 리스트 -->
                            <div style="display: grid; gap: 20px;">
                                ${module.resources.videos && module.resources.videos.length > 0 ? `
                                    <div>
                                        <h4 style="
                                            font-size: 17px;
                                            font-weight: 700;
                                            color: #374151;
                                            margin-bottom: 12px;
                                            display: flex;
                                            align-items: center;
                                            gap: 8px;
                                        ">
                                            <span style="color: #f59e0b;">📹</span>
                                            동영상 강의
                                        </h4>
                                        <div style="display: grid; gap: 10px;">
                                            ${module.resources.videos.map((video, idx) => `
                                                <a href="${video.url}" target="_blank" style="
                                                    display: flex;
                                                    align-items: center;
                                                    gap: 12px;
                                                    background: linear-gradient(135deg, #fffbeb, #fef3c7);
                                                    border: 1px solid #fed7aa;
                                                    border-radius: 12px;
                                                    padding: 16px;
                                                    text-decoration: none;
                                                    color: #92400e;
                                                    transition: all 0.2s ease;
                                                    position: relative;
                                                    overflow: hidden;
                                                " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 8px 25px rgba(245, 158, 11, 0.15)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                                                    <div style="
                                                        background: #f59e0b;
                                                        color: white;
                                                        width: 40px;
                                                        height: 40px;
                                                        border-radius: 10px;
                                                        display: flex;
                                                        align-items: center;
                                                        justify-content: center;
                                                        font-size: 12px;
                                                        font-weight: 700;
                                                        flex-shrink: 0;
                                                    ">${idx + 1}</div>
                                                    <div style="flex: 1;">
                                                        <div style="font-weight: 600; margin-bottom: 4px; font-size: 14px;">
                                                            ${video.title}
                                                        </div>
                                                        <div style="font-size: 12px; color: #a16207;">
                                                            ${video.duration || '약 30분'} • 동영상 강의
                                                        </div>
                                                    </div>
                                                    <div style="
                                                        background: rgba(245, 158, 11, 0.2);
                                                        color: #92400e;
                                                        padding: 4px 8px;
                                                        border-radius: 6px;
                                                        font-size: 11px;
                                                        font-weight: 600;
                                                    ">▶ 재생</div>
                                                </a>
                                            `).join('')}
                                        </div>
                                    </div>
                                ` : ''}

                                ${module.resources.web_links && module.resources.web_links.length > 0 ? `
                                    <div>
                                        <h4 style="
                                            font-size: 17px;
                                            font-weight: 700;
                                            color: #374151;
                                            margin-bottom: 12px;
                                            display: flex;
                                            align-items: center;
                                            gap: 8px;
                                        ">
                                            <span style="color: #3b82f6;">🌐</span>
                                            웹 자료
                                        </h4>
                                        <div style="display: grid; gap: 10px;">
                                            ${module.resources.web_links.map((link, idx) => `
                                                <a href="${link.url}" target="_blank" style="
                                                    display: flex;
                                                    align-items: center;
                                                    gap: 12px;
                                                    background: linear-gradient(135deg, #eff6ff, #dbeafe);
                                                    border: 1px solid #93c5fd;
                                                    border-radius: 12px;
                                                    padding: 16px;
                                                    text-decoration: none;
                                                    color: #1e40af;
                                                    transition: all 0.2s ease;
                                                " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 8px 25px rgba(59, 130, 246, 0.15)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                                                    <div style="
                                                        background: #3b82f6;
                                                        color: white;
                                                        width: 40px;
                                                        height: 40px;
                                                        border-radius: 10px;
                                                        display: flex;
                                                        align-items: center;
                                                        justify-content: center;
                                                        font-size: 12px;
                                                        font-weight: 700;
                                                        flex-shrink: 0;
                                                    ">${idx + 1}</div>
                                                    <div style="flex: 1;">
                                                        <div style="font-weight: 600; margin-bottom: 4px; font-size: 14px;">
                                                            ${link.title}
                                                        </div>
                                                        <div style="font-size: 12px; color: #1e40af;">
                                                            웹 자료 • 온라인 참고자료
                                                        </div>
                                                    </div>
                                                    <div style="
                                                        background: rgba(59, 130, 246, 0.2);
                                                        color: #1e40af;
                                                        padding: 4px 8px;
                                                        border-radius: 6px;
                                                        font-size: 11px;
                                                        font-weight: 600;
                                                    ">🔗 링크</div>
                                                </a>
                                            `).join('')}
                                        </div>
                                    </div>
                                ` : ''}

                                ${module.resources.documents && module.resources.documents.length > 0 ? `
                                    <div>
                                        <h4 style="
                                            font-size: 17px;
                                            font-weight: 700;
                                            color: #374151;
                                            margin-bottom: 12px;
                                            display: flex;
                                            align-items: center;
                                            gap: 8px;
                                        ">
                                            <span style="color: #10b981;">📄</span>
                                            문서 자료
                                        </h4>
                                        <div style="display: grid; gap: 10px;">
                                            ${module.resources.documents.map((doc, idx) => `
                                                <a href="${doc.url}" target="_blank" style="
                                                    display: flex;
                                                    align-items: center;
                                                    gap: 12px;
                                                    background: linear-gradient(135deg, #f0fdf4, #dcfce7);
                                                    border: 1px solid #86efac;
                                                    border-radius: 12px;
                                                    padding: 16px;
                                                    text-decoration: none;
                                                    color: #065f46;
                                                    transition: all 0.2s ease;
                                                " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 8px 25px rgba(16, 185, 129, 0.15)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                                                    <div style="
                                                        background: #10b981;
                                                        color: white;
                                                        width: 40px;
                                                        height: 40px;
                                                        border-radius: 10px;
                                                        display: flex;
                                                        align-items: center;
                                                        justify-content: center;
                                                        font-size: 12px;
                                                        font-weight: 700;
                                                        flex-shrink: 0;
                                                    ">${idx + 1}</div>
                                                    <div style="flex: 1;">
                                                        <div style="font-weight: 600; margin-bottom: 4px; font-size: 14px;">
                                                            ${doc.title}
                                                        </div>
                                                        <div style="font-size: 12px; color: #065f46;">
                                                            ${doc.type || 'PDF'} • ${doc.pages || '10'}페이지
                                                        </div>
                                                    </div>
                                                    <div style="
                                                        background: rgba(16, 185, 129, 0.2);
                                                        color: #065f46;
                                                        padding: 4px 8px;
                                                        border-radius: 6px;
                                                        font-size: 11px;
                                                        font-weight: 600;
                                                    ">📁 다운로드</div>
                                                </a>
                                            `).join('')}
                                        </div>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    ` : ''}

                    <!-- 학습 완료 섹션 -->
                    <div style="
                        margin-top: 20px;
                        background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
                        border-radius: 16px;
                        padding: 20px;
                        border: 1px solid rgba(148, 163, 184, 0.1);
                        box-shadow:
                            0 8px 32px rgba(0, 0, 0, 0.04),
                            0 0 0 1px rgba(255, 255, 255, 0.8),
                            inset 0 1px 0 rgba(255, 255, 255, 0.9);
                        position: relative;
                        overflow: hidden;
                    ">
                        <!-- 배경 장식 -->
                        <div style="
                            position: absolute;
                            top: -30px;
                            right: -30px;
                            width: 100px;
                            height: 100px;
                            background: radial-gradient(circle, ${isCompleted ? '#10b98108' : weekColor + '08'} 0%, transparent 70%);
                            border-radius: 50%;
                            pointer-events: none;
                        "></div>

                        <h3 style="
                            font-size: 18px;
                            font-weight: 700;
                            color: #0f172a;
                            margin-bottom: 16px;
                            display: flex;
                            align-items: center;
                            gap: 10px;
                            position: relative;
                            z-index: 5;
                        ">
                            <span style="
                                background: linear-gradient(135deg, ${isCompleted ? '#10b981' : weekColor} 0%, ${isCompleted ? '#059669' : weekColor + 'cc'} 100%);
                                color: white;
                                width: 36px;
                                height: 36px;
                                border-radius: 12px;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                font-size: 16px;
                                box-shadow:
                                    0 6px 12px ${isCompleted ? '#10b98130' : weekColor + '30'},
                                    0 0 0 1px rgba(255, 255, 255, 0.2);
                            ">${isCompleted ? '✅' : '📚'}</span>
                            학습 진행 상태
                        </h3>

                        <div style="
                            display: flex;
                            align-items: center;
                            gap: 12px;
                            padding: 16px;
                            background: ${isCompleted ?
                                'linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)' :
                                'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)'
                            };
                            border: 1px solid ${isCompleted ? '#86efac' : 'rgba(148, 163, 184, 0.2)'};
                            border-radius: 12px;
                            cursor: pointer;
                            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                            position: relative;
                            z-index: 5;
                        " onclick="toggleWeekCompletion(${moduleIndex})"
                           onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 4px 12px rgba(0, 0, 0, 0.1)'"
                           onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'">

                            <input
                                type="checkbox"
                                id="completeWeek-${moduleIndex}"
                                ${isCompleted ? 'checked' : ''}
                                onclick="event.stopPropagation()"
                                onchange="toggleWeekCompletion(${moduleIndex})"
                                style="
                                    width: 20px;
                                    height: 20px;
                                    accent-color: ${weekColor};
                                    cursor: pointer;
                                    border-radius: 4px;
                                "
                            />

                            <div style="flex: 1;">
                                <div style="
                                    font-size: 16px;
                                    font-weight: 600;
                                    color: ${isCompleted ? '#065f46' : '#334155'};
                                    margin-bottom: 2px;
                                ">
                                    ${isCompleted ? '학습 완료됨' : '학습 완료 표시'}
                                </div>
                                <div style="
                                    font-size: 13px;
                                    color: ${isCompleted ? '#059669' : '#64748b'};
                                    font-weight: 500;
                                ">
                                    ${isCompleted ? '이 주차 학습을 완료했습니다' : '모든 학습을 마치면 체크해주세요'}
                                </div>
                            </div>

                            ${isCompleted ? `
                                <button
                                    onclick="event.stopPropagation(); toggleWeekCompletion(${moduleIndex})"
                                    style="
                                        background: rgba(239, 68, 68, 0.1);
                                        border: 1px solid #fca5a5;
                                        color: #dc2626;
                                        padding: 6px 12px;
                                        border-radius: 8px;
                                        font-size: 12px;
                                        font-weight: 600;
                                        cursor: pointer;
                                        transition: all 0.2s;
                                    "
                                    onmouseover="this.style.background='rgba(239, 68, 68, 0.2)'"
                                    onmouseout="this.style.background='rgba(239, 68, 68, 0.1)'"
                                >
                                    완료 취소
                                </button>
                            ` : ''}
                        </div>
                    </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // 모달을 body에 추가
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

// 모달 닫기 - original unified file function
function closeModuleModal(event) {
    if (event && event.target !== event.currentTarget) return;

    const modal = document.getElementById('moduleModal');
    if (modal) {
        modal.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => {
            modal.remove();
        }, 300);
    }
}

// 주차 완료 상태 토글 - original unified file function
function toggleWeekCompletion(moduleIndex) {
    const completedWeeks = StorageManager.curriculum.progress.get() || [];
    const isCurrentlyCompleted = completedWeeks.includes(moduleIndex);

    if (isCurrentlyCompleted) {
        // 완료 해제
        const updatedWeeks = completedWeeks.filter(week => week !== moduleIndex);
        StorageManager.curriculum.progress.set(updatedWeeks);
        showNotification(`${moduleIndex + 1}주차 완료 상태가 해제되었습니다.`, 'info');
    } else {
        // 완료 추가
        const updatedWeeks = [...completedWeeks, moduleIndex].sort((a, b) => a - b);
        StorageManager.curriculum.progress.set(updatedWeeks);
        showNotification(`🎉 ${moduleIndex + 1}주차를 완료하셨습니다!`, 'success');

        // 완료 효과 애니메이션
        setTimeout(() => {
            const checkbox = document.getElementById(`completeWeek-${moduleIndex}`);
            if (checkbox) {
                checkbox.style.transform = 'scale(1.2)';
                setTimeout(() => {
                    checkbox.style.transform = 'scale(1)';
                }, 200);
            }
        }, 100);
    }

    // 완료 처리 후 모달 닫기 및 전체 커리큘럼으로 복귀
    setTimeout(() => {
        closeModuleModal();

        // 커리큘럼 페이지로 이동하여 업데이트된 진행률 표시
        const curriculumContent = document.getElementById('curriculumContent');
        const curriculumData = StorageManager.curriculum.get();
        if (curriculumContent && curriculumData) {
            displayCurriculumCards(curriculumContent, curriculumData);
        }
    }, 1000);
}

// Export functions for global use
window.generateCurriculum = generateCurriculum;
window.checkCurriculumCompletion = checkCurriculumCompletion;
window.showCurriculumContent = showCurriculumContent;
window.displayLoadingState = displayLoadingState;
window.displayEmptyState = displayEmptyState;
window.displayCurriculumCards = displayCurriculumCards;
window.toggleModuleCompletion = toggleModuleCompletion;
window.toggleModuleDetail = toggleModuleDetail;
window.closeModuleModal = closeModuleModal;
window.toggleWeekCompletion = toggleWeekCompletion;
window.updateProgressBar = updateProgressBar;
window.updateModuleCardState = updateModuleCardState;
window.downloadCurriculum = downloadCurriculum;
window.shareCurriculum = shareCurriculum;
window.createCurriculumContent = createCurriculumContent;
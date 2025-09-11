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
function showCurriculumContent(curriculumContent) {
    // Check existing curriculum
    const existingCurriculum = StorageManager.curriculum.get();
    
    if (existingCurriculum) {
        console.log('📚 기존 커리큘럼 표시');
        displayCurriculumCards(curriculumContent, existingCurriculum);
    } else if (isGeneratingCurriculum) {
        console.log('⏳ 커리큘럼 생성 중 - 로딩 표시');
        displayLoadingState(curriculumContent);
    } else {
        console.log('📝 커리큘럼 없음 - 안내 메시지 표시');
        displayEmptyState(curriculumContent);
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
function displayCurriculumCards(container, curriculumData) {
    if (!curriculumData || !curriculumData.modules) {
        displayEmptyState(container);
        return;
    }

    const completedWeeks = StorageManager.curriculum.progress.get();
    
    container.innerHTML = `
        <div class="curriculum-header">
            <div class="curriculum-title">
                <h2>${curriculumData.title || '맞춤형 학습 커리큘럼'}</h2>
                <div class="curriculum-meta">
                    <span class="duration"><i class="fas fa-calendar"></i> ${curriculumData.duration || '8주'} 과정</span>
                    <span class="progress"><i class="fas fa-chart-line"></i> ${completedWeeks.length || 0}/${curriculumData.modules.length} 완료</span>
                </div>
            </div>
            <div class="curriculum-actions">
                <button onclick="downloadCurriculum()" class="btn btn-outline">
                    <i class="fas fa-download"></i> 다운로드
                </button>
                <button onclick="shareCurriculum()" class="btn btn-outline">
                    <i class="fas fa-share"></i> 공유
                </button>
            </div>
        </div>
        
        <div class="curriculum-modules">
            ${curriculumData.modules.map((module, index) => createModuleCard(module, index, completedWeeks)).join('')}
        </div>
        
        <div class="curriculum-footer">
            <div class="progress-summary">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${(completedWeeks.length / curriculumData.modules.length) * 100}%"></div>
                </div>
                <p>전체 진도: ${completedWeeks.length}/${curriculumData.modules.length} 주차 완료</p>
            </div>
        </div>
    `;
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

// Export functions for global use
window.generateCurriculum = generateCurriculum;
window.checkCurriculumCompletion = checkCurriculumCompletion;
window.showCurriculumContent = showCurriculumContent;
window.displayLoadingState = displayLoadingState;
window.displayEmptyState = displayEmptyState;
window.displayCurriculumCards = displayCurriculumCards;
window.toggleModuleCompletion = toggleModuleCompletion;
window.updateProgressBar = updateProgressBar;
window.updateModuleCardState = updateModuleCardState;
window.downloadCurriculum = downloadCurriculum;
window.shareCurriculum = shareCurriculum;
window.createCurriculumContent = createCurriculumContent;
/* =============================================================================
   Profile Management Functions
   ============================================================================= */

// Learning Profile Management
function updateLearningProfile(topic, constraints, goal) {
    const profileTopic = document.getElementById('profileTopic');
    const profileConstraints = document.getElementById('profileConstraints');
    const profileGoal = document.getElementById('profileGoal');
    
    const stepTopic = document.getElementById('stepTopic');
    const stepConstraints = document.getElementById('stepConstraints');
    const stepGoal = document.getElementById('stepGoal');
    
    // Update topic
    if (topic) {
        profileTopic.textContent = topic;
        stepTopic.classList.add('completed');
    } else {
        profileTopic.textContent = '설정 필요';
        stepTopic.classList.remove('completed');
    }
    
    // Update constraints
    if (constraints) {
        profileConstraints.textContent = constraints;
        stepConstraints.classList.add('completed');
    } else {
        profileConstraints.textContent = '설정 필요';
        stepConstraints.classList.remove('completed');
    }
    
    // Update goal
    if (goal) {
        profileGoal.textContent = goal;
        stepGoal.classList.add('completed');
    } else {
        profileGoal.textContent = '설정 필요';
        stepGoal.classList.remove('completed');
    }

    // Check if profile is complete and show/hide curriculum section
    const profileComplete = topic && constraints && goal;
    const curriculumSection = document.getElementById('curriculumSection');
    const profileCard = document.querySelector('.profile-card');
    
    if (profileComplete && curriculumSection) {
        curriculumSection.style.display = 'block';
        profileCard.classList.add('with-curriculum');
        console.log('✅ 프로필 완성 - 커리큘럼 섹션 표시, 카드 높이 조정');
    } else if (curriculumSection) {
        curriculumSection.style.display = 'none';
        profileCard.classList.remove('with-curriculum');
        console.log('❌ 프로필 미완성 - 커리큘럼 섹션 숨김, 카드 기본 높이');
    }
}

// Extract and update profile information from AI response
function extractAndUpdateProfile(message) {
    // Attempt to extract profile information from Assessment messages
    if (message.includes('파이썬 학습 조건') || 
        message.includes('파이썬 학습 목표') || 
        message.includes('학습 프로필 분석 완료')) {
        // Actually should be received from server, but temporarily use stored profile
        const profile = StorageManager.profile.get();
        if (profile.topic || profile.constraints || profile.goal) {
            updateLearningProfile(profile.topic, profile.constraints, profile.goal);
        }
    }
}

// Initialize profile from stored data
function initializeProfile() {
    const profile = StorageManager.profile.get();
    if (profile && (profile.topic || profile.constraints || profile.goal)) {
        updateLearningProfile(profile.topic, profile.constraints, profile.goal);
        console.log('📊 저장된 프로필 복원:', profile);
    }
}

// Clear profile data
function clearProfile() {
    StorageManager.profile.clear();
    updateLearningProfile('', '', '');
    console.log('🧹 프로필 데이터 초기화됨');
}

// Validate profile completion
function isProfileComplete() {
    const profile = StorageManager.profile.get();
    return profile.topic && profile.constraints && profile.goal;
}

// Get current profile status
function getProfileStatus() {
    const profile = StorageManager.profile.get();
    const steps = ['topic', 'constraints', 'goal'];
    const completed = steps.filter(step => profile[step] && profile[step].trim());
    
    return {
        total: steps.length,
        completed: completed.length,
        isComplete: completed.length === steps.length,
        completedSteps: completed,
        profile: profile
    };
}

// Export functions for global use
window.updateLearningProfile = updateLearningProfile;
window.extractAndUpdateProfile = extractAndUpdateProfile;
window.initializeProfile = initializeProfile;
window.clearProfile = clearProfile;
window.isProfileComplete = isProfileComplete;
window.getProfileStatus = getProfileStatus;
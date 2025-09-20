/* =============================================================================
   Dataset Map - Simple Neo4j Graph Visualization
   ============================================================================= */

// 전역 변수
let datasetNetwork = null;
let datasetGraphData = { nodes: [], edges: [] };
let datasetFilteredData = { nodes: [], edges: [] };

// 노드 타입별 색상 설정 (Procedure 제외)
const NODE_COLORS = {
    'Document': '#4dc0b5',
    'Person': '#c990c0',
    'Skill': '#57c7e3',
    'Unknown': '#6b7280'
};

/**
 * 데이터셋 지도 초기화
 */
async function initializeDatasetMap() {
    console.log('🗺️ 데이터셋 지도 초기화 시작');

    // 컨테이너 요소 확인
    const container = document.getElementById('datasetGraphContainer');
    if (!container) {
        console.error('❌ datasetGraphContainer 요소를 찾을 수 없습니다');
        showDatasetError('그래프 컨테이너를 찾을 수 없습니다.');
        return;
    }

    try {
        // 로딩 상태 표시
        showDatasetLoading(true);

        // Neo4j 그래프 데이터 로드
        await loadDatasetGraphData();

        // 이벤트 리스너 설정
        setupDatasetEventListeners();

        console.log('✅ 데이터셋 지도 초기화 완료');

    } catch (error) {
        console.error('❌ 데이터셋 지도 초기화 실패:', error);
        showDatasetError('데이터셋 지도를 초기화하는 중 오류가 발생했습니다.');
    }
}

/**
 * Neo4j 그래프 데이터 로드
 */
async function loadDatasetGraphData() {
    try {
        const response = await fetch('/api/neo4j/graph-data');
        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        // 데이터 변환 및 저장
        datasetGraphData = transformDatasetGraphData(data);
        datasetFilteredData = { ...datasetGraphData };

        // 그래프 생성
        createDatasetGraph();

        // 로딩 상태 해제
        showDatasetLoading(false);

        console.log(`📊 그래프 데이터 로드 완료: 노드 ${data.nodes.length}개, 관계 ${data.edges.length}개`);

    } catch (error) {
        console.error('❌ 그래프 데이터 로드 실패:', error);
        showDatasetError(`그래프 데이터를 불러오는데 실패했습니다: ${error.message}`);
        showDatasetLoading(false);
    }
}

/**
 * 데이터를 Vis.js 네트워크 형식으로 변환
 */
function transformDatasetGraphData(data) {
    const transformedNodes = data.nodes.map(node => ({
        id: node.id,
        label: node.label,
        title: createNodeTooltip(node),
        group: node.group,
        color: NODE_COLORS[node.group] || NODE_COLORS['Unknown'],
        font: {
            size: 14,
            color: '#333'
        },
        properties: node.properties
    }));

    const transformedEdges = data.edges.map(edge => ({
        from: edge.from,
        to: edge.to,
        label: edge.label,
        title: `관계: ${edge.label}`,
        color: { color: '#666', highlight: '#3b82f6' },
        arrows: { to: { enabled: true, scaleFactor: 0.5 } },
        font: { size: 10, color: '#666' },
        properties: edge.properties
    }));

    return {
        nodes: new vis.DataSet(transformedNodes),
        edges: new vis.DataSet(transformedEdges)
    };
}

/**
 * 노드 툴팁 생성
 */
function createNodeTooltip(node) {
    let tooltip = `<strong>${node.group}: ${node.label}</strong><br>`;
    tooltip += `ID: ${node.id}<br>`;

    if (node.properties) {
        const props = Object.entries(node.properties)
            .filter(([key, value]) => key !== 'name' && key !== 'title' && value)
            .slice(0, 3);

        props.forEach(([key, value]) => {
            const displayValue = typeof value === 'string' && value.length > 50
                ? value.substring(0, 50) + '...'
                : value;
            tooltip += `${key}: ${displayValue}<br>`;
        });
    }

    return tooltip;
}

/**
 * Vis.js 네트워크 그래프 생성
 */
function createDatasetGraph() {
    const container = document.getElementById('datasetGraphContainer');

    if (!container) {
        console.error('❌ 그래프 컨테이너를 찾을 수 없습니다');
        return;
    }

    const options = {
        layout: {
            improvedLayout: true,
            randomSeed: 42
        },
        physics: {
            enabled: true,
            stabilization: { iterations: 150 },
            barnesHut: {
                gravitationalConstant: -8000,
                centralGravity: 0.3,
                springLength: 95,
                springConstant: 0.04,
                damping: 0.09
            }
        },
        interaction: {
            dragNodes: true,
            dragView: true,
            zoomView: true,
            hover: true
        },
        nodes: {
            borderWidth: 2,
            shadow: true,
            size: 25
        },
        edges: {
            width: 1,
            shadow: true,
            smooth: {
                type: 'continuous',
                roundness: 0.2
            }
        }
    };

    // 기존 네트워크 제거
    if (datasetNetwork) {
        datasetNetwork.destroy();
    }

    // 새 네트워크 생성
    try {
        datasetNetwork = new vis.Network(container, datasetFilteredData, options);

        // 이벤트 리스너 설정
        setupNetworkEventListeners();

        console.log('✅ Vis.js 네트워크 그래프 생성 완료');

    } catch (error) {
        console.error('❌ 네트워크 생성 실패:', error);
        showDatasetError('그래프를 생성하는데 실패했습니다.');
    }
}

/**
 * 네트워크 이벤트 리스너 설정
 */
function setupNetworkEventListeners() {
    if (!datasetNetwork) return;

    // 노드 클릭 이벤트
    datasetNetwork.on('click', function(params) {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            showNodeDetails(nodeId);
        } else {
            hideNodeDetails();
        }
    });

    // 안정화 완료 시 자동 맞춤
    datasetNetwork.on('stabilizationIterationsDone', function() {
        datasetNetwork.fit();
    });
}

/**
 * 데이터셋 이벤트 리스너 설정
 */
function setupDatasetEventListeners() {
    // 검색 입력
    const searchInput = document.getElementById('datasetSearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(handleDatasetSearch, 300));
    }

    // 필터 체크박스들
    const filterCheckboxes = document.querySelectorAll('[id^="filter"]');
    filterCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', handleDatasetFilter);
    });
}

/**
 * 검색 처리
 */
function handleDatasetSearch(event) {
    const query = event.target.value.toLowerCase().trim();

    if (query === '') {
        // 검색어가 없으면 원본 데이터로 복원
        applyDatasetFilters();
        return;
    }

    console.log('🔍 데이터셋 검색:', query);

    // 노드 필터링
    const filteredNodes = datasetGraphData.nodes.get().filter(node => {
        return node.label.toLowerCase().includes(query) ||
               node.group.toLowerCase().includes(query) ||
               (node.properties && JSON.stringify(node.properties).toLowerCase().includes(query));
    });

    const filteredNodeIds = new Set(filteredNodes.map(node => node.id));

    // 관련 엣지 필터링
    const filteredEdges = datasetGraphData.edges.get().filter(edge => {
        return filteredNodeIds.has(edge.from) || filteredNodeIds.has(edge.to);
    });

    // 데이터 업데이트
    datasetFilteredData.nodes.update(filteredNodes);
    datasetFilteredData.edges.update(filteredEdges);

    // 검색 결과에 맞춰 뷰 조정
    if (filteredNodes.length > 0) {
        setTimeout(() => {
            datasetNetwork.fit({
                nodes: filteredNodeIds,
                animation: {
                    duration: 1000,
                    easingFunction: 'easeInOutQuad'
                }
            });
        }, 100);
    }
}

/**
 * 필터 처리
 */
function handleDatasetFilter() {
    applyDatasetFilters();
}

/**
 * 필터 적용
 */
function applyDatasetFilters() {
    const activeFilters = {
        Document: document.getElementById('filterDocument')?.checked ?? true,
        Person: document.getElementById('filterPerson')?.checked ?? true,
        Skill: document.getElementById('filterSkill')?.checked ?? true
    };

    console.log('🔧 필터 적용:', activeFilters);

    // 노드 필터링
    const filteredNodes = datasetGraphData.nodes.get().filter(node => {
        return activeFilters[node.group] !== false;
    });

    const filteredNodeIds = new Set(filteredNodes.map(node => node.id));

    // 관련 엣지 필터링
    const filteredEdges = datasetGraphData.edges.get().filter(edge => {
        return filteredNodeIds.has(edge.from) && filteredNodeIds.has(edge.to);
    });

    // 데이터 업데이트
    datasetFilteredData.nodes.clear();
    datasetFilteredData.edges.clear();
    datasetFilteredData.nodes.add(filteredNodes);
    datasetFilteredData.edges.add(filteredEdges);

    console.log(`📊 필터 결과: 노드 ${filteredNodes.length}개, 엣지 ${filteredEdges.length}개`);
}

/**
 * 노드 상세 정보 표시
 */
function showNodeDetails(nodeId) {
    const node = datasetGraphData.nodes.get(nodeId);
    if (!node) return;

    const panel = document.getElementById('nodeInfoPanel');
    const content = document.getElementById('nodeInfoContent');

    if (!panel || !content) return;

    // 노드 정보 생성
    let html = `
        <div class="node-property">
            <strong>노드 ID:</strong> ${node.id}
        </div>
        <div class="node-property">
            <strong>타입:</strong> ${node.group}
        </div>
        <div class="node-property">
            <strong>이름:</strong> ${node.label}
        </div>
    `;

    // 추가 속성들
    if (node.properties) {
        Object.entries(node.properties).forEach(([key, value]) => {
            if (key !== 'name' && key !== 'title' && value) {
                html += `
                    <div class="node-property">
                        <strong>${key}:</strong> ${value}
                    </div>
                `;
            }
        });
    }

    content.innerHTML = html;
    panel.style.display = 'block';
}

/**
 * 노드 상세 정보 숨기기
 */
function hideNodeDetails() {
    const panel = document.getElementById('nodeInfoPanel');
    if (panel) {
        panel.style.display = 'none';
    }
}

/**
 * 그래프 전체 보기
 */
function fitDatasetGraph() {
    if (datasetNetwork) {
        datasetNetwork.fit({
            animation: {
                duration: 1000,
                easingFunction: 'easeInOutQuad'
            }
        });
    }
}

/**
 * 그래프 리셋
 */
function resetDatasetGraph() {
    if (datasetNetwork) {
        // 필터 초기화
        document.querySelectorAll('[id^="filter"]').forEach(checkbox => {
            checkbox.checked = true;
        });

        // 검색 입력 초기화
        const searchInput = document.getElementById('datasetSearchInput');
        if (searchInput) {
            searchInput.value = '';
        }

        // 데이터 초기화
        datasetFilteredData.nodes.clear();
        datasetFilteredData.edges.clear();
        datasetFilteredData.nodes.add(datasetGraphData.nodes.get());
        datasetFilteredData.edges.add(datasetGraphData.edges.get());

        // 뷰 리셋
        fitDatasetGraph();

        // 노드 정보 패널 숨기기
        hideNodeDetails();

        showNotification('그래프가 초기화되었습니다.', 'success');
    }
}

/**
 * 그래프 새로고침
 */
async function refreshDatasetGraph() {
    showNotification('데이터를 새로고침하고 있습니다...', 'info');

    try {
        showDatasetLoading(true);
        await loadDatasetGraphData();
        showNotification('데이터 새로고침이 완료되었습니다.', 'success');
    } catch (error) {
        console.error('❌ 새로고침 실패:', error);
        showNotification('새로고침 중 오류가 발생했습니다.', 'error');
        showDatasetLoading(false);
    }
}

/**
 * 로딩 상태 표시/숨김
 */
function showDatasetLoading(show) {
    const loadingElement = document.getElementById('datasetGraphLoading');
    if (loadingElement) {
        loadingElement.style.display = show ? 'block' : 'none';
    } else {
        console.warn('⚠️ datasetGraphLoading 요소를 찾을 수 없습니다');
    }
}

/**
 * 에러 메시지 표시
 */
function showDatasetError(message) {
    const container = document.getElementById('datasetGraphContainer');
    if (container) {
        container.innerHTML = `
            <div class="dataset-graph-empty">
                <i class="fas fa-exclamation-triangle"></i>
                <div>${message}</div>
            </div>
        `;
    }
}

/**
 * 디바운스 함수
 */
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

/**
 * 알림 표시
 */
function showNotification(message, type = 'info') {
    if (typeof window.showNotification === 'function') {
        window.showNotification(message, type);
    } else {
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
}

// 전역 스코프에 함수들 등록
window.initializeDatasetMap = initializeDatasetMap;
window.fitDatasetGraph = fitDatasetGraph;
window.resetDatasetGraph = resetDatasetGraph;
window.refreshDatasetGraph = refreshDatasetGraph;

console.log('📦 Dataset Map 모듈 로드 완료');
console.log('🔧 등록된 전역 함수:', {
    initializeDatasetMap: typeof window.initializeDatasetMap,
    fitDatasetGraph: typeof window.fitDatasetGraph,
    resetDatasetGraph: typeof window.resetDatasetGraph,
    refreshDatasetGraph: typeof window.refreshDatasetGraph
});
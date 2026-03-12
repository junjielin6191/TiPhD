document.addEventListener('DOMContentLoaded', function() {
    const ROWS_PER_PAGE = 10;
    let currentPage = 1;
    
    // 初始化过滤器和分页
    initializeFilters();
    updatePagination();
    showPage(1);
    
    // 初始化过滤器事件监听
    function initializeFilters() {
        const filters = ['spatialLayerFilter', 'experimentalDesignFilter', 'methodologyFilter'];
        filters.forEach(filterId => {
            document.getElementById(filterId).addEventListener('change', function() {
                filterExperiments();
                updatePagination();
                showPage(1);
            });
        });
    }
    
    // 过滤实验数据
    function filterExperiments() {
        const spatialLayer = document.getElementById('spatialLayerFilter').value;
        const experimentalDesign = document.getElementById('experimentalDesignFilter').value;
        const methodology = document.getElementById('methodologyFilter').value;
        
        const rows = document.querySelectorAll('.experiment-row');
        
        rows.forEach(row => {
            const matchesSpatial = !spatialLayer || row.cells[0].textContent.trim() === spatialLayer;
            const matchesDesign = !experimentalDesign || row.cells[1].textContent.trim() === experimentalDesign;
            const matchesMethod = !methodology || row.cells[2].textContent.trim() === methodology;
            
            if (matchesSpatial && matchesDesign && matchesMethod) {
                row.classList.remove('hidden');
            } else {
                row.classList.add('hidden');
            }
        });
    }
    
    // 更新分页
    function updatePagination() {
        const visibleRows = document.querySelectorAll('.experiment-row:not(.hidden)').length;
        const totalPages = Math.ceil(visibleRows / ROWS_PER_PAGE);
        
        const pagination = document.getElementById('pagination');
        pagination.innerHTML = '';
        
        // Previous button
        const prevLi = document.createElement('li');
        prevLi.className = 'page-item';
        prevLi.innerHTML = `<a class="page-link" href="#" aria-label="Previous">
                             <span aria-hidden="true">&laquo;</span>
                           </a>`;
        pagination.appendChild(prevLi);
        
        // Page numbers
        for (let i = 1; i <= totalPages; i++) {
            const li = document.createElement('li');
            li.className = `page-item ${i === currentPage ? 'active' : ''}`;
            li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
            li.addEventListener('click', (e) => {
                e.preventDefault();
                showPage(i);
            });
            pagination.appendChild(li);
        }
        
        // Next button
        const nextLi = document.createElement('li');
        nextLi.className = 'page-item';
        nextLi.innerHTML = `<a class="page-link" href="#" aria-label="Next">
                             <span aria-hidden="true">&raquo;</span>
                           </a>`;
        pagination.appendChild(nextLi);
    }
    
    // 显示指定页面
    function showPage(pageNum) {
        currentPage = pageNum;
        const visibleRows = document.querySelectorAll('.experiment-row:not(.hidden)');
        
        visibleRows.forEach((row, index) => {
            if (index >= (pageNum - 1) * ROWS_PER_PAGE && index < pageNum * ROWS_PER_PAGE) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
        
        // 更新分页按钮状态
        document.querySelectorAll('.pagination .page-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`.pagination .page-item:nth-child(${pageNum + 1})`).classList.add('active');
    }
    
    // 查看详情按钮事件
    document.querySelectorAll('.view-details').forEach(button => {
        button.addEventListener('click', function() {
            const experimentId = this.getAttribute('data-experiment-id');
            showExperimentDetails(experimentId);
        });
    });
});

async function showExperimentDetails(experimentId) {
    try {
        const row = document.querySelector(`[data-experiment-id="${experimentId}"]`).closest('tr');
        
        // 从表格行获取数据
        const experimentData = {
            title: row.cells[1].textContent,
            purpose: row.cells[3].textContent,
            methodology: row.cells[2].textContent,
            analyses: row.cells[4].textContent
        };

        // 更新模态框内容
        document.getElementById('experimentTitle').textContent = experimentData.title;
        document.getElementById('experimentPurpose').textContent = experimentData.purpose;
        document.getElementById('experimentMethodology').textContent = experimentData.methodology;
        document.getElementById('experimentAnalyses').textContent = experimentData.analyses;

        // 显示模态框
        const modal = new bootstrap.Modal(document.getElementById('experimentModal'));
        modal.show();
    } catch (error) {
        console.error('Error showing experiment details:', error);
    }
}

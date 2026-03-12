document.addEventListener('DOMContentLoaded', function() {
    // 图片点击放大功能
    const images = document.querySelectorAll('.image-item img');
    images.forEach(img => {
        img.addEventListener('click', function() {
            this.classList.toggle('enlarged');
        });
    });

    // 数据集表格排序功能
    const tables = document.querySelectorAll('.dataset-table table');
    tables.forEach(table => {
        const headers = table.querySelectorAll('tr:first-child td');
        headers.forEach((header, index) => {
            header.addEventListener('click', () => {
                sortTable(table, index);
            });
            header.style.cursor = 'pointer';
        });
    });

    // 处理分页点击
    document.querySelectorAll('.page-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const page = parseInt(this.dataset.page);
            const tableType = this.dataset.table;
            
            // 更新表格行的显示
            const rows = document.querySelectorAll(`tr.table-row[data-table="${tableType}"]`);
            rows.forEach((row, index) => {
                if (index >= (page-1)*5 && index < page*5) {
                    row.classList.remove('d-none');
                } else {
                    row.classList.add('d-none');
                }
            });
            
            // 更新分页按钮状态
            const pagination = this.closest('.pagination');
            pagination.querySelectorAll('.page-item').forEach(item => {
                item.classList.remove('active');
            });
            this.parentElement.classList.add('active');
        });
    });

    const searchInput = document.getElementById('searchInput');
    const categoryFilter = document.getElementById('categoryFilter');
    const toolTables = document.getElementById('toolTables');

    // 搜索功能
    function searchTools() {
        const searchTerm = searchInput.value.toLowerCase();
        const selectedCategory = categoryFilter.value;

        document.querySelectorAll('.table-row').forEach(row => {
            const text = row.textContent.toLowerCase();
            const category = row.closest('.table-section').dataset.category;
            const matchesSearch = text.includes(searchTerm);
            const matchesCategory = !selectedCategory || category === selectedCategory;

            if (matchesSearch && matchesCategory) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });

        // 更新表格显示
        document.querySelectorAll('.table-section').forEach(section => {
            const hasVisibleRows = section.querySelectorAll('tr.table-row:not([style*="display: none"])').length > 0;
            section.style.display = hasVisibleRows ? '' : 'none';
        });

        // 重置分页
        updatePagination();
    }

    // 分页功能
    function updatePagination() {
        document.querySelectorAll('.table-section').forEach(section => {
            const visibleRows = Array.from(section.querySelectorAll('tr.table-row:not([style*="display: none"])'));
            const totalPages = Math.ceil(visibleRows.length / 5);
            const category = section.dataset.category;

            // 更新分页按钮
            const pagination = section.querySelector('.pagination');
            if (pagination) {
                pagination.innerHTML = '';
                for (let i = 1; i <= totalPages; i++) {
                    const li = document.createElement('li');
                    li.className = `page-item ${i === 1 ? 'active' : ''}`;
                    li.innerHTML = `<a class="page-link" href="#" data-table="${category}" data-page="${i}">${i}</a>`;
                    pagination.appendChild(li);
                }
            }

            // 显示第一页
            showPage(category, 1);
        });
    }

    // 显示指定页面
    function showPage(category, page) {
        const rows = document.querySelectorAll(`tr.table-row[data-table="${category}"]:not([style*="display: none"])`);
        rows.forEach((row, index) => {
            if (index >= (page - 1) * 5 && index < page * 5) {
                row.classList.remove('d-none');
            } else {
                row.classList.add('d-none');
            }
        });
    }

    // 事件监听
    searchInput.addEventListener('input', searchTools);
    categoryFilter.addEventListener('change', searchTools);

    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('page-link')) {
            e.preventDefault();
            const page = parseInt(e.target.dataset.page);
            const category = e.target.dataset.table;
            
            // 更新分页按钮状态
            const pagination = e.target.closest('.pagination');
            pagination.querySelectorAll('.page-item').forEach(item => {
                item.classList.remove('active');
            });
            e.target.parentElement.classList.add('active');

            // 显示对应页面
            showPage(category, page);
        }
    });
});

// 表格排序函数
function sortTable(table, column) {
    const rows = Array.from(table.querySelectorAll('tr')).slice(1);
    const direction = table.getAttribute('data-sort') === 'asc' ? -1 : 1;
    
    rows.sort((a, b) => {
        const aValue = a.cells[column].textContent;
        const bValue = b.cells[column].textContent;
        return direction * aValue.localeCompare(bValue);
    });

    rows.forEach(row => table.appendChild(row));
    table.setAttribute('data-sort', direction === 1 ? 'asc' : 'desc');
}

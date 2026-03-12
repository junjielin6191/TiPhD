// 当页面加载完成时初始化
document.addEventListener('DOMContentLoaded', function() {
    const tableName = getActiveTable();
    
    // 根据表类型获取对应的字段列表
    const fields = getFieldsByTableName(tableName);
    
    // 初始化所有下拉框
    fields.forEach(field => {
        updateOptions(tableName, field, {});
    });

    // 为所有下拉框添加 change 事件监听
    document.querySelectorAll('select').forEach(select => {
        select.addEventListener('change', function() {
            // 获取当前所有选中的值
            const filters = getSelectedFilters();
            
            // 更新其他所有下拉框的选项
            fields.forEach(field => {
                if (field !== this.id) { // 不更新当前改变的下拉框
                    updateOptions(tableName, field, filters);
                }
            });
        });
    });
});

// 根据表名获取对应的字段列表
function getFieldsByTableName(tableName) {
    if (tableName === 'celltype') {
        return ['major_cancer_type','cancer_type', 'major_cell_type','cell_type', 'Phenotype_type', 'major_Phenotype_label','Phenotype_label'];
    } else if (tableName === 'spatiallayer') {
        return ['major_cancer_type','cancer_type', 'major_spatial_layer', 'spatial_layer', 'Phenotype_type', 'major_Phenotype_label','Phenotype_label'];
    }
    return [];
}

// 获取当前表格名称
function getActiveTable() {
    const pathParts = window.location.pathname.split('/');
    const tableName = pathParts[pathParts.length - 1];
    console.log('Current table name:', tableName);
    return tableName;
}

// 获取所有已选择的筛选条件
function getSelectedFilters() {
    const filters = {};
    document.querySelectorAll('select').forEach(select => {
        if (select.value) {
            filters[select.id] = select.value;
        }
    });
    console.log('Current filters:', filters);
    return filters;
}

// 更新下拉框选项
function updateOptions(tableName, field, filters) {
    const select = document.getElementById(field);
    if (!select) {
        console.log(`Select element not found for field: ${field}`);
        return;
    }

    // 保存当前选中的值
    const currentValue = select.value;

    // 构建查询参数
    const params = new URLSearchParams({
        table: tableName,
        field: field,
        ...filters
    });

    console.log(`Updating ${field} with filters:`, filters);

    fetch(`/api/get_options?${params}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log(`Received options for ${field}:`, data);
            
            // 清空现有选项
            select.innerHTML = `<option value="">Select ${field.replace(/_/g, ' ')}</option>`;
            
            // 添加新选项
            if (Array.isArray(data)) {
                data.forEach(item => {
                    if (item) {  // 确保值不为空
                        const option = document.createElement('option');
                        option.value = item;
                        option.textContent = item;
                        // 如果是之前选中的值，保持选中状态
                        if (item === currentValue) {
                            option.selected = true;
                        }
                        select.appendChild(option);
                    }
                });
            }
        })
        .catch(error => {
            console.error(`Error updating ${field} options:`, error);
            select.innerHTML = `<option value="">Error loading options</option>`;
        });
}

// 清空所有筛选条件
function clearFilters() {
    const tableName = getActiveTable();
    const fields = getFieldsByTableName(tableName);
    
    // 清空所有选择
    document.querySelectorAll('select').forEach(select => {
        select.value = '';
    });
    
    // 重新初始化所有下拉框
    fields.forEach(field => {
        updateOptions(tableName, field, {});
    });

    // 清空结果表格
    document.querySelector('#results-table tbody').innerHTML = '';
}

// 执行搜索
function searchData() {
    const tableName = getActiveTable();
    console.log('Table name for search:', tableName); // 添加调试日志
    
    if (!tableName) {
        console.error('Table name is not defined');
        return;
    }

    const filters = getSelectedFilters();
    console.log('Search filters:', filters); // 添加调试日志
    
    // 显示加载状态
    const tbody = document.querySelector('#results-table tbody');
    if (!tbody) {
        console.error('Table body element not found');
        return;
    }
    
    tbody.innerHTML = '<tr><td colspan="12" class="text-center">Loading...</td></tr>';
    
    // 构建查询参数
    const params = new URLSearchParams(filters);
    
    // 发送搜索请求
    fetch(`/api/search/${tableName}?${params}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Received data:', data); // 添加调试日志
            if (!Array.isArray(data)) {
                throw new Error('Invalid data format received');
            }
            displayResults(data, tableName);
        })
        .catch(error => {
            console.error('Search error:', error);
            if (tbody) {
                tbody.innerHTML = `<tr><td colspan="12" class="text-center text-danger">Error: ${error.message}</td></tr>`;
            }
        });
}

// 显示搜索结果
function displayResults(data, tableName) {
    console.log('Displaying results for table:', tableName); // 添加调试日志
    
    const table = document.getElementById('results-table');
    const thead = table.querySelector('thead');
    const tbody = table.querySelector('tbody');

    if (!thead || !tbody) {
        console.error('Table elements not found');
        return;
    }

    // 清空现有内容
    thead.innerHTML = '';
    tbody.innerHTML = '';

    // 处理空结果
    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12" class="text-center">No results found</td></tr>';
        return;
    }

    // 定义字段顺序
    const fieldOrder = tableName === "celltype" ? [
        'CTID', 'PMID', 'Paper_Title', 'major_Phenotype_label','Phenotype_label', 'Phenotype_type',
        'cancer_type', 'major_cell_type','cell_type','cell_name', 'journal',  'species',
        'tissue_class', 'year'
    ] : [
        'SLID', 'PMID', 'Paper_Title', 'major_Phenotype_label','Phenotype_label', 'Phenotype_type',
        'cancer_type', 'spatial_layer',  'Cell_type_composition','journal', 'major_spatial_layer','species',
        'tissue_class', 'year'
    ];

    // 创建表头
    const headerRow = document.createElement('tr');
    fieldOrder.forEach(field => {
        const th = document.createElement('th');
        th.textContent = field.replace(/_/g, ' ');
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    // 填充数据行
    data.forEach(row => {
        const tr = document.createElement('tr');
        fieldOrder.forEach(field => {
            const td = document.createElement('td');
            const value = row[field];

            if ((field === "CTID" && tableName === "celltype") || 
                (field === "SLID" && tableName === "spatiallayer")) {
                const link = document.createElement("a");
                link.href = `/details/${tableName}/${value}`;
                link.textContent = value;
                td.appendChild(link);
            }
            else if (field === "PMID") {
                const link = document.createElement("a");
                link.href = `https://pubmed.ncbi.nlm.nih.gov/${value}`;
                link.target = "_blank";
                link.textContent = value;
                td.appendChild(link);
            }
            else {
                td.textContent = value || "-";
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}

// 格式化表头文本：将字段名从全大写改为首字母大写，并去掉下划线
function formatHeader(field) {
    if (field === "CTID" || field === "SLID" || field === "PMID") {
        return field; // 保持这些字段的原样
    }
    return field
        .toLowerCase()
        .replace(/_/g, ' ')
        .replace(/\b\w/g, char => char.toUpperCase());
}

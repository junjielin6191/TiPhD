// 初始化状态
let currentPage = 1;  // 当前页
let rowsPerPage = 10;  // 每页显示的条目数

// 用于加载表格数据的函数
const loadbrowse = (tableName, currentPage = 1, rowsPerPage = 10) => {
    console.log(`loadbrowse called with tableName=${tableName}, currentPage=${currentPage}, rowsPerPage=${rowsPerPage}`);
    if (!tableName) {
        console.error("Table name is required");
        return;
    }

    // 获取数据
    fetch(`/browse/data/${tableName}?page=${currentPage}&limit=${rowsPerPage}`)
        .then((response) => {
            if (!response.ok) {
                throw new Error(`Failed to load data: ${response.statusText}`);
            }
            return response.json();
        })
        .then((data) => {
            const errorMessage = document.getElementById("error-message");
            errorMessage.style.display = 'none';  // 隐藏错误信息
            console.log("Data received from server:", data);

            // 根据表格名称设置字段顺序
            // 根据用户要求，完整配置 Browse 页面的显示列
            const fieldOrder = tableName === "celltype"
            ? [
                "CTID", "species", "tissue_class", "tissue_type", "major_cancer_type", 
                "cancer_type", "cancer_type_detail", "major_cell_type", "cell_type", 
                "cell_name", "cell_marker", "PMID", "Paper_Title", "journal", "year", 
                "Phenotype_type", "major_Phenotype_label", "Phenotype_label", 
                "Phenotype_evidence"
            ]
            : [
                "SLID", "species", "tissue_class", "tissue_type", "major_cancer_type", 
                "cancer_type", "cancer_type_detail", "major_spatial_layer", "spatial_layer", 
                "Cell_type_composition", "PMID", "Paper_Title", "journal", "year", 
                "Phenotype_type", "major_Phenotype_label", "Phenotype_label", 
                "Phenotype_evidence"
            ];
            const tableHeaderFragment = document.createDocumentFragment();
            const tableBodyFragment = document.createDocumentFragment();
            // 格式化函数：将字段名从全大写改为首字母大写，并去掉下划线

            // 格式化函数：将字段名从全大写改为首字母大写，并去掉下划线
            const formatHeader = (field) => {
                if (field === "CTID" || field === "SLID"||field === "PMID") {
                    return field; // 保持原样
                }
                const formatted = field
                    .toLowerCase() // 转为小写
                    .replace(/_/g, ' ') // 用空格替换下划线
                    .replace(/\b\w/g, char => char.toUpperCase()); // 首字母大写
                console.log(field, formatted);
                return formatted;
            };
            

            // 更新表头
            fieldOrder.forEach((field) => {
                const th = document.createElement("th");
                th.textContent = formatHeader(field); // 使用格式化函数
                console.log('Table Header:', th.textContent); // 输出表头内容
                tableHeaderFragment.appendChild(th);
            });
            const tableHeader = document.getElementById("table-header");
            tableHeader.innerHTML = ''; // 清空表头
            tableHeader.appendChild(tableHeaderFragment);

            // 更新表体
            const tableBody = document.getElementById("table-body");
            data.data.forEach((row) => {
                const tr = document.createElement("tr");
                fieldOrder.forEach((field) => {
                    const td = document.createElement("td");

                    if (field === "CTID" || field === "SLID") {
                        // 如果是 CTID 或 SLID，做成超链接
                        const link = document.createElement("a");
                        link.href = `/details/${tableName.toLowerCase()}/${row[field]}`;
                        link.textContent = row[field];
                        td.appendChild(link);
                    }
                    else if (field === "PMID") { // 修改为字符串
                        // 根据PMID链接到PubMed页面
                        const link = document.createElement("a");
                        link.href = `https://pubmed.ncbi.nlm.nih.gov/${row[field]}`; // 使用PMID动态生成URL
                        link.textContent = row[field]; // 显示PMID文本
                        td.appendChild(link);
                    }
                     else {
                        td.textContent = row[field] || "";
                    }

                    tr.appendChild(td);
                });
                tableBodyFragment.appendChild(tr);
            });
            tableBody.innerHTML = ''; // 清空表体
            tableBody.appendChild(tableBodyFragment);

            // 更新分页控件
            document.getElementById('pagination-info').textContent = `Page ${data.page} of ${data.total_pages}`;
            document.getElementById('prev-page').disabled = data.page === 1;
            document.getElementById('next-page').disabled = data.page === data.total_pages;
        })
        .catch((error) => {
            console.error(error);
            const errorMessage = document.getElementById("error-message");
            errorMessage.textContent = 'Failed to load data. Please try again.';
            errorMessage.style.display = 'block';  // 显示错误信息
        });
};

// 处理导航栏点击事件，动态加载不同的表格
document.querySelectorAll('.dropdown-item').forEach(item => {
    item.addEventListener('click', (event) => {
        // 获取当前点击的表格名称
        tableName = event.target.getAttribute('href').split('/').pop();  // 获取表格名称
        currentPage = 1;  // 重置为第一页
        loadbrowse(tableName, currentPage, rowsPerPage);  // 加载选中的表格数据
    });
});

// 分页按钮点击事件
document.getElementById('prev-page').addEventListener('click', () => {
    if (currentPage > 1) {
        currentPage--;  // 当前页减一
        loadbrowse(tableName, currentPage, rowsPerPage);  // 使用当前的 tableName 加载数据
    }
});

document.getElementById('next-page').addEventListener('click', () => {
    currentPage++;  // 当前页加一
    loadbrowse(tableName, currentPage, rowsPerPage);  // 使用当前的 tableName 加载数据
});

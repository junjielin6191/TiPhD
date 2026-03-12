// 定义字段顺序
const CELLTYPE_FIELDS = [
    "CTID", "species", "tissue_class", "cancer_type", "major_cell_type", "cell_type",
    "cell_name", "Phenotype_type", "Phenotype_label", "Paper_Title", "journal", "year","PMID"

];

const SPATIAL_FIELDS = [
    "SLID", "species", "tissue_class", "cancer_type", "spatial_layer", 
    "Cell_type_composition",  "Phenotype_type", "Phenotype_label",  "Paper_Title", "journal", "year","PMID"
];

// 加载表格数据的函数
function loadTableData(apiUrl, tableId, headerId) {
    $(document).ready(function() {
        // 初始化 DataTable
        const table = $(`#${tableId}`).DataTable({
            ajax: {
                url: apiUrl,
                dataSrc: ''
            },
            columns: generateColumns(tableId === 'cellTypeTable' ? CELLTYPE_FIELDS : SPATIAL_FIELDS),
            dom: 'Bfrtip', // 添加按钮到DOM
            buttons: [
                'copy', 
                {
                    extend: 'csv',
                    filename: `${tableId}_export`,
                    text: 'CSV'
                }
            ],
            pageLength: 10, // 每页显示10条记录
            lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "All"]], // 分页选项
            order: [[0, 'asc']], // 默认按第一列升序排序
            responsive: true,
            language: {
                search: "Search:",
                paginate: {
                    first: "First",
                    last: "Last",
                    next: "Next",
                    previous: "Previous"
                },
                info: "Showing _START_ to _END_ of _TOTAL_ entries",
                lengthMenu: "Show _MENU_ entries"
            }
        });
    });
}

// 生成列定义
function generateColumns(fields) {
    return fields.map(field => ({
        data: field,
        title: field,
        render: function(data, type, row) {
            if (field === "CTID" || field === "SLID") {
                // 为 CTID/SLID 创建详情页链接
                const prefix = field === "CTID" ? "celltype" : "spatiallayer";
                return `<a href="/details/${prefix}/${data}">${data}</a>`;
            } 
            else if (field === "PubMedID") {
                // 为 PubMedID 创建 PubMed 链接
                return `<a href="https://pubmed.ncbi.nlm.nih.gov/${data}" target="_blank">${data}</a>`;
            }
            // 其他字段直接显示数据
            return data || '-';
        }
    }));
}

// 为表格添加标题样式
function styleTableHeader(tableId) {
    const titleColor = tableId === 'cellTypeTable' ? '#009da1' : 'lightcoral';
    $(`#${tableId}_wrapper .dataTables_wrapper`).before(
        `<h2 style="color: ${titleColor}">Information of datasets in ${tableId === 'cellTypeTable' ? 'cell type' : 'spatial structure'}</h2>`
    );
}

// 初始化页面
$(document).ready(function() {
    // 加载 Cell Type 表格数据
    loadTableData('/api/get_cell_type_data', 'cellTypeTable', 'cellTableHeader');
    
    // 加载 Spatial Layer 表格数据
    loadTableData('/api/get_spatial_structure_data', 'spatialLayerTable', 'spatialTableHeader');
    
    // 添加表格标题样式
    styleTableHeader('cellTypeTable');
    styleTableHeader('spatialLayerTable');
});
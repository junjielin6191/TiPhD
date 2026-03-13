// 加载统计数据并渲染图表
function loadStatistics(tableName) {
    fetch(`/api/statistics/${tableName}`)
        .then((response) => response.json())
        .then((data) => {
            console.log("Fetched data:", data);

            // 错误处理
            if (data.error) {
                document.getElementById("statistics-container").innerHTML = `
                    <p class="text-danger">${data.error}</p>`;
                return;
            }

            // 渲染图表
            renderCharts(data, tableName);
        })
        .catch((error) => {
            console.error("Error loading statistics data:", error);
        });
}

// 渲染图表
// 渲染图表
function renderCharts(data, tableName) {
    // 根据表名渲染不同的图表
    if (tableName === "celltype") {
        // Cell Type Chart -> 对应 major_cell_type
        if (data["major_cell_type"]) {
            Plotly.newPlot(
                "cells-type-chart",
                [
                    {
                        x: Object.keys(data["major_cell_type"]), // 横坐标
                        y: Object.values(data["major_cell_type"]), // 纵坐标
                        type: "bar", // 图表类型为柱状图
                        marker: {
                            color: getRandomColors(Object.keys(data["major_cell_type"]).length), // 生成随机颜色
                        },
                    },
                ],
                {
                    title: "major cell type", // 图表标题
                    height: 400,
                    xaxis: {
                        title: "major cell type",
                        tickangle: -45, // 标签旋转45度
                        automargin: true, // 自动调整边距
                        tickfont: { size: 10 }, // 调整字体大小
                    },
                    yaxis: { title: "Count" },
                }
            );
        }

        // Phenotype Label Chart -> 对应 major_Phenotype_label
        if (data["major_Phenotype_label"]) {
            Plotly.newPlot(
                "phenotype-label-chart",
                [
                    {
                        labels: Object.keys(data["major_Phenotype_label"]),
                        values: Object.values(data["major_Phenotype_label"]),
                        type: "pie",
                    },
                ],
                { title: "major Phenotype label", height: 430 }
            );
        }

        // major cancer type Chart -> 对应 major_cancer_type
        if (data["major_cancer_type"]) {
            Plotly.newPlot(
                "main-cancer-type-chart",
                [
                    {
                        x: Object.keys(data["major_cancer_type"]),
                        y: Object.values(data["major_cancer_type"]),
                        type: "bar",
                        marker: {
                            color: getRandomColors(Object.keys(data["major_cancer_type"]).length), // 生成随机颜色
                        },                        
                    },
                ],
                {
                    title: "major cancer type",
                    height: 400,
                    xaxis: {
                        title: "major cancer type",
                        tickangle: -45, // 标签旋转45度
                        automargin: true, // 自动调整边距
                        tickfont: { size: 10 }, // 调整字体大小
                    },
                    yaxis: { title: "Count" },
                }
            );            
        }

        // Phenotype Type Chart -> 对应 Phenotype_type
        if (data["Phenotype_type"]) {
            Plotly.newPlot(
                "phenotype-type-chart",
                [
                    {
                        labels: Object.keys(data["Phenotype_type"]),
                        values: Object.values(data["Phenotype_type"]),
                        type: "pie",
                    },
                ],
                { title: "Phenotype Type", height: 400 }
            );
        }

        // Heatmap Chart -> 保持不变
        if (data["heatmap"]) {
            Plotly.newPlot(
                "heatmap-chart",
                [
                    {
                        z: data["heatmap"].z,
                        x: data["heatmap"].x,
                        y: data["heatmap"].y,
                        type: "heatmap",
                        colorscale: [
                            [0, "rgb(0, 0, 102)"],  // 深蓝 (起始点)
                            [0.5, "rgb(0, 0, 204)"], // 中间的较亮蓝色
                            [1, "rgb(173, 216, 230)"] // 浅蓝 (终点)
                        ],
                        reversescale: false, // 不反转颜色
                    },
                ],
                {
                    title: "major cancer type - major cell type Heatmap",
                    xaxis: { title: "major cell type", tickangle: -45, automargin: true },
                    yaxis: { title: "major cancer type", automargin: true },
                    height: 600,
                }
            );
        }
    } 
    
    else if (tableName === "spatiallayer") {
        // Spatial Layer Chart -> 对应 major_spatial_layer
        if (data["major_spatial_layer"]) {
            Plotly.newPlot(
                "spatial-layer-chart",
                [
                    {
                        labels: Object.keys(data["major_spatial_layer"]), // 扇形图的标签
                        values: Object.values(data["major_spatial_layer"]), // 扇形图的值
                        type: "pie", // 图表类型设置为 pie
                    },
                ],
                {
                    title: "major spatial layer", // 图表标题
                    height: 400,
                }
            );
        }
    
        // major cancer type Chart -> 对应 major_cancer_type
        if (data["major_cancer_type"]) {
            Plotly.newPlot(
                "main-cancer-type-chart",
                [
                    {
                        x: Object.keys(data["major_cancer_type"]),
                        y: Object.values(data["major_cancer_type"]),
                        type: "bar",
                        marker: {
                            color: getRandomColors(Object.keys(data["major_cancer_type"]).length), // 生成随机颜色
                        }, 
                    },
                ],
                {
                    title: "major cancer type",
                    height: 400,
                    xaxis: {
                        title: "major cancer type",
                        tickangle: -45, // 标签旋转45度
                        automargin: true, // 自动调整边距
                        tickfont: { size: 10 }, // 调整字体大小
                    },
                    yaxis: { title: "Count" },
                }
            );
        }
    
        // major Phenotype label Chart -> 对应 major_Phenotype_label
        if (data["major_Phenotype_label"]) {
            Plotly.newPlot(
                "phenotype-label-chart",
                [
                    {
                        labels: Object.keys(data["major_Phenotype_label"]),
                        values: Object.values(data["major_Phenotype_label"]),
                        type: "pie",
                    },
                ],
                { title: "major Phenotype label", height: 430 }
            );
        }
    
        // Phenotype Type Chart -> 对应 Phenotype_type
        if (data["Phenotype_type"]) {
            Plotly.newPlot(
                "phenotype-type-chart",
                [
                    {
                        labels: Object.keys(data["Phenotype_type"]),
                        values: Object.values(data["Phenotype_type"]),
                        type: "pie",
                    },
                ],
                { title: "Phenotype Type", height: 400 }
            );
        }
    
        // Heatmap Chart -> 保持不变
        if (data["heatmap"]) {
            Plotly.newPlot(
                "heatmap-chart",
                [
                    {
                        z: data["heatmap"].z,
                        x: data["heatmap"].x,
                        y: data["heatmap"].y,
                        type: "heatmap",
                        colorscale: [
                            [0, "rgb(0, 0, 102)"],  // 深蓝 (起始点)
                            [0.5, "rgb(0, 0, 204)"], // 中间的较亮蓝色
                            [1, "rgb(173, 216, 230)"] // 浅蓝 (终点)
                        ],
                        reversescale: false, // 不反转颜色
                    },
                ],
                {
                    title: "major cancer type - major spatial layer Heatmap",
                    xaxis: { title: "major spatial layer", tickangle: -45, automargin: true },
                    yaxis: { title: "major cancer type", automargin: true },
                    height: 600,
                }
            );
        }
    }
    
    else {
        console.error(`No rendering logic defined for tableName: ${tableName}`);
    }
}

// 随机颜色生成函数
function getRandomColors(length) {
    const colors = [];
    for (let i = 0; i < length; i++) {
        colors.push(`#${Math.floor(Math.random() * 16777215).toString(16)}`);
    }
    return colors;
}
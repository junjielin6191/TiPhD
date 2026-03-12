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
function renderCharts(data, tableName) {
    // 根据表名渲染不同的图表
    if (tableName === "celltype") {
        // Cell Type Chart
        if (data["cells type"]) {
            Plotly.newPlot(
                "cells-type-chart",
                [
                    {
                        x: Object.keys(data["cells type"]), // 横坐标
                        y: Object.values(data["cells type"]), // 纵坐标
                        type: "bar", // 图表类型为柱状图
                        marker: {
                            color: getRandomColors(Object.keys(data["cells type"]).length), // 生成随机颜色
                        },
                    },
                ],
                {
                    title: "Cell Type", // 图表标题
                    height: 400,
                    xaxis: {
                        title: "Cell Type",
                        tickangle: -45, // 标签旋转45度
                        automargin: true, // 自动调整边距
                        tickfont: {
                            size: 10, // 调整字体大小
                        },
                    },
                    yaxis: {
                        title: "Count",
                    },
                }
            );
        }

        // Phenotype Label Chart
        if (data["phenotype label"]) {
            Plotly.newPlot(
                "phenotype-label-chart",
                [
                    {
                        labels: Object.keys(data["phenotype label"]),
                        values: Object.values(data["phenotype label"]),
                        type: "pie",
                    },
                ],
                { title: "Phenotype Label", height: 430 }
            );
        }

        // Main Cancer Type Chart
        if (data["main cancer type"]) {
            Plotly.newPlot(
                "main-cancer-type-chart",
                [
                    {
                        x: Object.keys(data["main cancer type"]),
                        y: Object.values(data["main cancer type"]),
                        type: "bar",
                        marker: {
                            color: getRandomColors(Object.keys(data["main cancer type"]).length), // 生成随机颜色
                        },                        
                    },
                ],
                {
                    title: "Cancer Type",
                    height: 400,
                    xaxis: {
                        title: "Cancer Type",
                        tickangle: -45, // 标签旋转45度
                        automargin: true, // 自动调整边距
                        tickfont: {
                            size: 10, // 调整字体大小
                        },
                    },
                    yaxis: {
                        title: "Count",
                    },
                }
            );            
        }

        // Phenotype Type Chart
        if (data["phenotype type"]) {
            Plotly.newPlot(
                "phenotype-type-chart",
                [
                    {
                        labels: Object.keys(data["phenotype type"]),
                        values: Object.values(data["phenotype type"]),
                        type: "pie",
                    },
                ],
                { title: "Phenotype Type", height: 400 }
            );
        }

        // Heatmap Chart
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
                    title: "Cancer Type - Cell Heatmap",
                    xaxis: { title: "Cell Name", tickangle: -45, automargin: true },
                    yaxis: { title: "Cancer Type", automargin: true },
                    height: 600,
                }
            );
        }
    } 
    
    else if (tableName === "spatiallayer") {
        // Spatial Layer Chart - 使用扇形图展示
        if (data["spatial layer"]) {
            Plotly.newPlot(
                "spatial-layer-chart",
                [
                    {
                        labels: Object.keys(data["spatial layer"]), // 扇形图的标签
                        values: Object.values(data["spatial layer"]), // 扇形图的值
                        type: "pie", // 图表类型设置为 pie
                    },
                ],
                {
                    title: "Spatial Layer", // 图表标题
                    height: 400,
                }
            );
        }
    
        // Main Cancer Type Chart
        if (data["main cancer type"]) {
            Plotly.newPlot(
                "main-cancer-type-chart",
                [
                    {
                        x: Object.keys(data["main cancer type"]),
                        y: Object.values(data["main cancer type"]),
                        type: "bar",
                        marker: {
                            color: getRandomColors(Object.keys(data["main cancer type"]).length), // 生成随机颜色
                        }, 
                    },
                ],
                {
                    title: "Cancer Type",
                    height: 400,
                    xaxis: {
                        title: "Cancer Type",
                        tickangle: -45, // 标签旋转45度
                        automargin: true, // 自动调整边距
                        tickfont: {
                            size: 10, // 调整字体大小
                        },
                    },
                    yaxis: {
                        title: "Count",
                    },
                }
            );
        }
    
        // Phenotype Label Chart
        if (data["phenotype label"]) {
            Plotly.newPlot(
                "phenotype-label-chart",
                [
                    {
                        labels: Object.keys(data["phenotype label"]),
                        values: Object.values(data["phenotype label"]),
                        type: "pie",
                    },
                ],
                { title: "Phenotype Label", height: 430 }
            );
        }
    
        // Phenotype Type Chart
        if (data["phenotype type"]) {
            Plotly.newPlot(
                "phenotype-type-chart",
                [
                    {
                        labels: Object.keys(data["phenotype type"]),
                        values: Object.values(data["phenotype type"]),
                        type: "pie",
                    },
                ],
                { title: "Phenotype Type", height: 400 }
            );
        }
    
        // Heatmap Chart
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
                    title: "Cancer Type - Spatial Layer Heatmap",
                    xaxis: { title: "Spatial Layer", tickangle: -45, automargin: true },
                    yaxis: { title: "Cancer Type", automargin: true },
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
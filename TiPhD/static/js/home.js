//肿瘤微环境
document.addEventListener("DOMContentLoaded", function () {
    const container = document.getElementById("tme-container");
    const images = [
        { src: "/static/tme/tumor_metastasis.png", alt: "Tumor Metastasis" },
        { src: "/static/tme/immune_tolerance.png", alt: "Immune Tolerance" },
        { src: "/static/tme/immune_inflammation.png", alt: "Immune Infiltration" },
        { src: "/static/tme/immune_exclude.png", alt: "Immune Exclude" },
        { src: "/static/tme/immune_suppression.png", alt: "Immune Suppression" },
        { src: "/static/tme/tumor_recurrence.png", alt: "Tumor Recurrence" },
        { src: "/static/tme/drug_response.png", alt: "Drug Response" },
        { src: "/static/tme/overal_survival.png", alt: "Survival" },
        { src: "/static/tme/tumor_growth.png", alt: "Tumor Growth" },
        { src: "/static/tme/tumor_invasion.png", alt: "Tumor Invasion" }
    ];

    const radius = 200; // 环绕元素的半径
    const textOffset = 95; // 文本距离图片的偏移量
    const center = { x: 300, y: 350 }; // 容器中心
    const centerImageSize = { width: 530, height: 530 }; // 中心图像大小

    // 添加中心图片
    const centerImg = document.createElement("img");
    centerImg.src = "/static/tme/tumor.png";
    centerImg.alt = "Tumor";
    centerImg.style.width = `${centerImageSize.width}px`;
    centerImg.style.height = `${centerImageSize.height}px`;
    centerImg.style.position = "absolute";
    centerImg.style.left = `${center.x - centerImageSize.width / 2}px`;
    centerImg.style.top = `${center.y - centerImageSize.height / 2}px`;
    container.appendChild(centerImg);

    // 布局环绕元素和文本
    images.forEach((image, index) => {
        const angleOffset = -Math.PI / 2; // 调整起始角度，让第一个元素位于顶部
        const angle = angleOffset + (index / images.length) * 2 * Math.PI; // 每个元素的角度
        const x = center.x + radius * Math.cos(angle); // 计算 x 坐标
        const y = center.y + radius * Math.sin(angle); // 计算 y 坐标

        // 创建图片元素
        const img = document.createElement("img");
        img.src = image.src;
        img.alt = image.alt;
        img.style.width = "110px"; // 设置环绕图片宽度
        img.style.height = "110px"; // 设置环绕图片高度
        img.style.position = "absolute";
        img.style.left = `${x - 55}px`; // 中心对齐
        img.style.top = `${y - 55}px`;

        // 将图片加入容器
        container.appendChild(img);

        // 创建文本元素
        const text = document.createElement("div");
        text.textContent = image.alt;
        text.style.position = "absolute";
        text.style.color = "#333"; // 设置文本颜色
        text.style.fontSize = "14px"; // 字体大小
        text.style.fontWeight = "bold"; // 加粗
        text.style.textAlign = "center"; // 文本居中
        text.style.width = "90px"; // 固定宽度，支持换行
        text.style.wordWrap = "break-word"; // 换行
        text.style.transform = `translate(-50%, -50%)`;
        text.style.left = `${x + (textOffset * Math.cos(angle))}px`; // 偏移文本的位置
        text.style.top = `${y + (textOffset * Math.sin(angle))}px`;

        // 将文本加入容器
        container.appendChild(text);
    });
});


// 癌型
document.addEventListener("DOMContentLoaded", function () {
    const container = document.getElementById("cancer-section");

    const centerImage = { src: "/static/cancer/human.png", alt: "Human", width: 353.6, height: 605.8 }; // 中心图片配置

    const surroundingImages = [
        { src: "/static/cancer/Brain_cancer.png", alt: "Brain cancer" },
        { src: "/static/cancer/Cervical_cancer.png", alt: "Cervical cancer" },
        { src: "/static/cancer/Esophageal_cancer.png", alt: "Esophageal cancer" },
        { src: "/static/cancer/Gastric_cancer.png", alt: "Gastric cancer" },
        { src: "/static/cancer/Other_cancer.png", alt: "Others" },
        { src: "/static/cancer/Colorectal_cancer.png", alt: "Colorectal cancer" },
        { src: "/static/cancer/Kidney_cancer.png", alt: "Kidney cancer" },
        { src: "/static/cancer/Pancreatic_cancer.png", alt: "Pancreatic cancer" },
        { src: "/static/cancer/Bladder_cancer.png", alt: "Bladder cancer" },
        { src: "/static/cancer/Melanoma.png", alt: "Melanoma" },
        { src: "/static/cancer/Gallbladder_cancer.png", alt: "Gallbladder cancer" },
        { src: "/static/cancer/Ovarian_cancer.png", alt: "Ovarian cancer" },
        { src: "/static/cancer/Lung_cancer.png", alt: "Lung cancer" },
        { src: "/static/cancer/Liver_cancer.png", alt: "Liver cancer" },
        { src: "/static/cancer/Breast_cancer.png", alt: "Breast cancer" },
        { src: "/static/cancer/Thyroid_cancer.png", alt: "Thyroid cancer" },
        { src: "/static/cancer/Leukemia.png", alt: "Leukemia" },
        
    ];

    const center = { x: 200, y: 400 }; // 容器中心点（适当向下调整中心点）
    const ellipse = { rx: 350, ry: 430 }; // 椭圆的长轴和短轴半径，调整为竖直方向

    // 添加中心图片
    const centerImg = document.createElement("img");
    centerImg.src = centerImage.src;
    centerImg.alt = centerImage.alt;
    centerImg.style.width = `${centerImage.width}px`;
    centerImg.style.height = `${centerImage.height}px`;
    centerImg.style.position = "absolute";
    centerImg.style.left = `${center.x - centerImage.width / 2}px`;
    centerImg.style.top = `${center.y - centerImage.height / 2}px`;
    container.appendChild(centerImg);

    // 布局环绕图片
    surroundingImages.forEach((image, index) => {
        const angle = (index / surroundingImages.length) * 2 * Math.PI; // 每个元素的角度
        const x = center.x + ellipse.rx * Math.cos(angle); // 椭圆 x 坐标
        const y = center.y + ellipse.ry * Math.sin(angle); // 椭圆 y 坐标

        const img = document.createElement("img");
        img.src = image.src;
        img.alt = image.alt;
        img.style.width = "106px"; // 缩小到 80%
        img.style.height = "106px";
        img.style.position = "absolute";
        img.style.left = `${x - 53}px`; // 图片中心对齐
        img.style.top = `${y - 53}px`; // 图片中心对齐

        const label = document.createElement("div");
        label.textContent = image.alt;
        label.style.left = `${x - 50}px`; // 标签与图片对齐
        label.style.top = `${y + 60}px`; // 标签放在图片下方
        label.style.width = "120px";
        label.style.position = "absolute";
        label.style.textAlign = "center";
        label.style.fontSize = "16px";
        label.style.color = "#000000";

        container.appendChild(img);
        container.appendChild(label);
    });
});


//统计信息
document.addEventListener("DOMContentLoaded", function () {
    // Cell Type 表格数据
    const cellTableData = [
        { category: "Paper Number", count: 177 },
        { category: "Cancer Type", count: 25 },
        { category: "Cell Type", count: 233 },
        { category: "Clinical Phenotype", count: 221 },
        { category: "Biological Phenotype", count: 140 }
    ];
  
    // Spatial Structure 表格数据
    const spatialTableData = [
        { category: "Paper Number", count: 54 },
        { category: "Cancer Type", count: 20 },
        { category: "Spatial Layer", count: 71 },
        { category: "Clinical Phenotype", count: 31 },
        { category: "Biological Phenotype", count: 44 }
    ];
  
    // 获取表格 body 的 DOM 元素
    const cellTableBody = document.getElementById("cell-table-body");
    const spatialTableBody = document.getElementById("spatial-table-body");
  
    // 动态生成 Cell Type 表格内容
    cellTableData.forEach(row => {
      const tr = document.createElement("tr");
      Object.values(row).forEach(value => {
        const td = document.createElement("td");
        td.textContent = value;
        tr.appendChild(td);
      });
      cellTableBody.appendChild(tr);
    });
  
    // 动态生成 Spatial Structure 表格内容
    spatialTableData.forEach(row => {
      const tr = document.createElement("tr");
      Object.values(row).forEach(value => {
        const td = document.createElement("td");
        td.textContent = value;
        tr.appendChild(td);
      });
      spatialTableBody.appendChild(tr);
    });
});
  
# File: Workflow_Agent/agent/planner_agent.py

import json
from typing import Any, Dict, List, Tuple, Optional 
from langchain_core.prompts import ChatPromptTemplate
from Workflow_Agent.agent.base_agent import base_agent 
from Workflow_Agent.llm import get_llm 
from Workflow_Agent.config import default_config
class PlannerAgent(base_agent):
    """
    Planner Agent: TiAgent 的核心大脑。
    负责生成科学严谨的、干湿闭环的研究方案。
    """

    def __init__(self, llm=default_config.llm, cheap_llm=None, temperature=0.7, api_key: Optional[str] = None):
        super().__init__(llm, cheap_llm, temperature, api_key=api_key) 
        self.configure()

    def configure(self):
        """
        配置 System Prompt。
        策略更新：采用 "Logic-First" (逻辑优先) + "Hybrid Knowledge" (混合知识) 策略。
        """
        self.system_prompt = """
            You are the TiAgent Planner, a Senior Bioinformatics & Experimental Architect.
            Your goal is to design a **highly customized, scientifically profound research workflow** that outperforms standard AI responses.

            ### 🧠 Core Strategy (Hybrid Knowledge):
            1. **Logic-First**: Do not just list steps. For every step, explain the *scientific causality* (e.g., "Why do we need to correct for batch effects here?").
            2. **Hybrid Resource Strategy (Crucial)**:
               - **Retrieved Tools**: When a specific tool in the "Available Resources" fits well (e.g., TiRank, Seurat), you **MUST** use it and explain *why* it fits this specific query.
               - **General Knowledge Fallback**: If the user asks for a standard protocol (e.g., IHC validation, CRISPR cloning, Western Blot) and NO specific tool is retrieved, **USE YOUR INTERNAL BIOLOGICAL KNOWLEDGE** to design a detailed standard protocol. 
               - **Warning**: Do *not* force an irrelevant retrieved tool (e.g., do NOT recommend "Visium" for a simple "IHC" task).
            3. **Wet-Lab Closed Loop**: Always propose concrete validation experiments that directly verify the computational findings.

            ### 📋 Mandatory Output Structure (Markdown):

            ## 1. Strategy Overview
            *Briefly analyze the user's biological intent and outline your high-level strategy.*

            ## 2. Step-by-Step Workflow
            
            ### Step 1: [Actionable Title]
            - **Scientific Logic**: 
                *Deeply explain the rationale. Example: "To distinguish true biological heterogeneity from technical noise, we must first..."*
            - **Methodological Details**: 
                *Describe how to execute this step. Be specific.*
            - **Recommended Resources**:
                *(Select the best fit. If using a standard protocol not in the list, mark Type as "Standard Protocol".)*
                | Resource Name | Type | Specific Role & Rationale |
                | :--- | :--- | :--- |
                | **[Name]** | [Dry/Wet] | **CRITICAL:** Explain strictly why this specific tool/protocol is chosen for *this* step. |
            - **Expected Outcome**: *What is the deliverable? (e.g., "A list of robust marker genes...")*

            ... (Repeat for all necessary steps) ...

            ## 3. Experimental Validation (The "Proof")
            *(Design 1-2 key experiments to validate the computational results)*
            - **Experiment**: [Name, e.g., Multiplex IHC / CRISPR Screen]
                - **Target**: *What specific gene/interaction are we validating?*
                - **Protocol Logic**: *Briefly describe the experimental setup (e.g., "Stain tissue microarrays with antibodies against...")*

            ---
            **--- Historical Session Records ---**
            {history}
            **--- End of Records ---**

            **--- Input to be Analyzed ---**
            User Query: {user_query}
            Retrieved Know-How Content: {retrieved_know_how_content}
            Available Tools/Libraries List: {retrieved_tools_and_libraries} 
        """

        self.planning_prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "Design the research workflow for the query above.")
        ])

    def _format_resources(self, resources: Dict[str, List[Any]]) -> Tuple[str, str]:
        """
        格式化检索到的资源，供 Prompt 使用。
        修改点：从“表格格式”改为“纯文本清单”，减少对模型的结构化干扰，鼓励其灵活调用知识。
        """
        # 1. 格式化 Know-How
        know_how_sections = []
        for doc in resources.get("know_how", []):
            if isinstance(doc, dict):
                # 截取内容预览，避免过长
                content_preview = doc.get('content', '')[:600].replace('\n', ' ')
                know_how_sections.append(f"- **{doc.get('id')}**: {content_preview}...")
        
        know_how_str = "\n".join(know_how_sections) if know_how_sections else "No specific guidelines found."

        # 2. 格式化 Tools/Libraries
        # 将列表平铺，让 LLM 更容易阅读，而不是强制塞进表格里
        tools_list = []
        for cat in ["tools", "libraries"]:
            for item in resources.get(cat, []):
                # 提取干净的名称
                item_str = str(item).strip()
                tools_list.append(f"- {item_str}")
        
        tools_str = "\n".join(tools_list) if tools_list else "No specific tools found."

        return know_how_str, tools_str

    def go(self, user_query: str, retrieved_resources: Dict[str, List[Any]], history: str = "") -> str:
        """
        执行规划。
        """
        know_how_content, tools_and_libraries_str = self._format_resources(retrieved_resources)
        formatted_prompt = self.planning_prompt.format_messages(
            user_query=user_query,
            history=history,
            retrieved_know_how_content=know_how_content,
            retrieved_tools_and_libraries=tools_and_libraries_str,
        )

        try:
            response_message = self.llm.invoke(formatted_prompt) 
            return response_message.content
        except Exception as e:
            return f"**Planning Failed:** {e}"
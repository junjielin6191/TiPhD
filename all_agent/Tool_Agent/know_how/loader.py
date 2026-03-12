"""Loader for know-how documents."""

import glob
import os
from pathlib import Path
# 关键修改：从 typing 导入所有需要的大写类型（Tuple, Dict, List, Optional, Union）
from typing import Optional, List, Dict, Any, Union, Tuple 
import re # 👈 确保 re 模块也导入了，因为 _parse_markdown 中使用了它

class KnowHowLoader:
    """Load and manage know-how documents for the agent."""

    # 兼容 Python < 3.10：使用 Optional[str]
    def __init__(self, know_how_dir: Optional[str] = None): 
        """Initialize the know-how loader.

        Args:
            know_how_dir: Directory containing know-how documents.
                         If None, uses the default know_how directory.

        """
        if know_how_dir is None:
            # Default to the know_how directory in the package
            current_dir = Path(__file__).parent
            know_how_dir = str(current_dir)

        self.know_how_dir = know_how_dir
        # 兼容 Python < 3.9：使用 Dict, List
        self.documents: Dict[str, Dict[str, Any]] = {} 
        self._load_documents()

    def _load_documents(self):
        """Load all markdown documents from the know-how directory."""
        pattern = os.path.join(self.know_how_dir, "*.md")
        md_files = glob.glob(pattern)

        for filepath in md_files:
            filename = os.path.basename(filepath)
            filename_without_ext = os.path.splitext(filename)[0]

            # Skip README, QUICK_START, and other meta documentation (all caps filenames)
            if filename.upper() in ["README.MD", "QUICK_START.MD"] or filename_without_ext.isupper():
                continue

            # Read the document
            with open(filepath) as f:
                content = f.read()

            # Extract title, description, and metadata from the document
            title, description, metadata = self._parse_markdown(content, filename_without_ext)

            doc_id = filename_without_ext.lower()

            self.documents[doc_id] = {
                "id": doc_id,
                "name": title,
                "description": description,
                "content": content,
                "metadata": metadata,
            }

    # 修复：确保 Tuple, Dict, Union 都在 typing 中导入
    def _parse_markdown(self, content: str, filename_without_ext: str) -> Tuple[str, str, Dict[str, Union[str, bool]]]:
        """Parse markdown content to extract title, description, and metadata."""
        
        # 假设标题是第一个一级标题
        title_match = re.search(r"^#\s*(.+)\s*$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else filename_without_ext

        # 提取 Short Description 作为描述
        desc_match = re.search(r"\*\*Short Description\*\*:\s*(.+)", content)
        description = desc_match.group(1).strip() if desc_match else "No description available."
        
        # 提取 Metadata
        metadata_dict: Dict[str, Union[str, bool]] = {}
        metadata_section_match = re.search(r"##\s*Metadata\s*---\s*(.*?)(?=\n##|$)", content, re.DOTALL | re.IGNORECASE)
        
        if metadata_section_match:
            metadata_content = metadata_section_match.group(1)
            # 使用正则表达式提取键值对
            for line in metadata_content.split('\n'):
                line = line.strip()
                if line.startswith('**') and ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip('*').lower().replace(' ', '_')
                    value = value.strip()
                    
                    if value.lower() in ['✅ allowed', 'allowed', 'yes', 'true']:
                        metadata_dict[key] = True
                    elif value.lower() in ['❌ not allowed', 'not allowed', 'no', 'false']:
                        metadata_dict[key] = False
                    else:
                        metadata_dict[key] = value

        return title, description, metadata_dict

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific know-how document."""
        return self.documents.get(doc_id.lower())

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all loaded know-how documents."""
        return list(self.documents.values())

    def display_document_info(self, doc_id: str):
        """Print the structured information of a know-how document."""
        doc = self.get_document(doc_id)
        if doc is None:
            print(f"Document '{doc_id}' not found")
            return

        print("=" * 70)
        print(f"📚 {doc['name']}")
        print("=" * 70)
        print(f"\nDescription: {doc['description']}")

        metadata = doc.get("metadata", {})
        if metadata:
            print("\n" + "-" * 70)
            print("METADATA")
            print("-" * 70)

            # Display key metadata fields
            if "authors" in metadata:
                print(f"Authors: {metadata['authors']}")
            if "affiliations" in metadata:
                print(f"Affiliations: {metadata['affiliations']}")
            if "version" in metadata:
                print(f"Version: {metadata['version']}")
            if "last_updated" in metadata:
                print(f"Last Updated: {metadata['last_updated']}")
            if "license" in metadata:
                print(f"License: {metadata['license']}")
            if "commercial_use" in metadata:
                print(f"Commercial Use: {metadata['commercial_use']}")
            if "status" in metadata:
                print(f"Status: {metadata['status']}")

        print("=" * 70)

    def remove_document(self, doc_id: str):
        """Remove a know-how document.

        Args:
            doc_id: Document identifier

        """
        if doc_id in self.documents:
            del self.documents[doc_id]

    def reload(self):
        """Reload all documents from disk."""
        self.documents = {}
        self._load_documents()
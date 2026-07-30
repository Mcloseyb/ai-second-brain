"""
知识图谱页面
-----------
蜘蛛网状展示笔记间的关联关系。

每个节点是一个笔记文件名，相关笔记用线连起来。
相似度基于标签重叠计算。
"""

import random

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PySide6.QtCore import Qt

from widgets.knowledge_graph import GraphCanvas, GraphNode, GraphEdge
from resources.styles.colors import Colors, Spacing, FontSize


# ---- 示例数据（P2 后将替换为真实笔记数据） ----

SAMPLE_NOTES = [
    ("nlp", "Natural Language Processing"),
    ("transformer", "Transformer Architecture"),
    ("attention", "Attention Mechanism"),
    ("bert", "BERT Explained"),
    ("gpt", "GPT Series Overview"),
    ("fine_tuning", "Fine-tuning Techniques"),
    ("rag", "RAG Retrieval Augmented Generation"),
    ("vector_db", "Vector Databases"),
    ("embedding", "Text Embeddings"),
    ("prompt", "Prompt Engineering Guide"),
    ("agent", "AI Agent Design Patterns"),
    ("langchain", "LangChain Framework"),
    ("function_call", "Function Calling in LLMs"),
    ("memory", "Conversation Memory Design"),
]

SAMPLE_EDGES = [
    ("nlp", "transformer"),
    ("transformer", "attention"),
    ("transformer", "bert"),
    ("transformer", "gpt"),
    ("attention", "bert"),
    ("attention", "gpt"),
    ("bert", "fine_tuning"),
    ("gpt", "fine_tuning"),
    ("gpt", "prompt"),
    ("rag", "vector_db"),
    ("rag", "embedding"),
    ("vector_db", "embedding"),
    ("rag", "prompt"),
    ("agent", "langchain"),
    ("agent", "function_call"),
    ("agent", "memory"),
    ("langchain", "function_call"),
    ("nlp", "embedding"),
    ("agent", "rag"),
    ("transformer", "embedding"),
]


class GraphPage(QWidget):
    """知识图谱页面"""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(f"""
            background: {Colors.bg_content};
            border-bottom: 1px solid {Colors.border_default};
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(Spacing.lg, Spacing.md, Spacing.lg, Spacing.md)

        title = QLabel("Knowledge Graph")
        title.setStyleSheet(f"""
            color: {Colors.text_primary};
            font-size: {FontSize.xl}px;
            font-weight: 600;
            border: none;
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        info = QLabel(f"{len(SAMPLE_NOTES)} notes, {len(SAMPLE_EDGES)} connections")
        info.setStyleSheet(f"color: {Colors.text_secondary}; font-size: {FontSize.sm}px; border: none;")
        header_layout.addWidget(info)

        layout.addWidget(header)

        # 图谱画布
        self.canvas = GraphCanvas()
        layout.addWidget(self.canvas)

        # 加载数据
        self._load_sample_data()

    def _load_sample_data(self):
        """加载示例图谱数据"""
        colors_list = [
            Colors.graph_node_default,
            Colors.accent_purple,
            Colors.accent_green,
            Colors.accent_yellow,
        ]

        nodes = []
        for i, (nid, label) in enumerate(SAMPLE_NOTES):
            color = colors_list[i % len(colors_list)]
            nodes.append(GraphNode(nid, label, color))

        edges = []
        for src, tgt in SAMPLE_EDGES:
            edges.append(GraphEdge(src, tgt, weight=random.uniform(0.5, 1.5)))

        self.canvas.set_data(nodes, edges)

    def update_data(self, notes_data: list[dict], connections: list[dict]):
        """用真实笔记数据更新图谱（P2 对接）"""
        nodes = [GraphNode(n["id"], n["title"]) for n in notes_data]
        edges = [GraphEdge(c["source"], c["target"], c.get("weight", 1.0))
                 for c in connections]
        self.canvas.set_data(nodes, edges)

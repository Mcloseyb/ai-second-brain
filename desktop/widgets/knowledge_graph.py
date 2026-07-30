"""
知识图谱可视化组件
------------------
蜘蛛网状展示笔记之间的关联关系。

工作原理:
  1. 节点 = 笔记文件名
  2. 连线 = 标签重叠或内容相似度
  3. 布局 = 简易力导向算法 (force-directed)
  4. 交互 = 拖拽节点、滚轮缩放

力导向算法简述（面试可讲）:
  - 斥力: 每对节点相互排斥（类比带电粒子）
  - 引力: 有连线的节点相互吸引（类比弹簧）
  - 迭代: 反复计算力 → 移动节点 → 直到稳定
  - 阻尼: 逐步降低移动速度，避免震荡
"""

import math
import random
from typing import Optional

from PySide6.QtWidgets import QWidget, QGraphicsView, QGraphicsScene
from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import (
    QPainter, QBrush, QPen, QColor, QFont, QFontMetrics,
    QPainterPath, QMouseEvent, QWheelEvent,
)

from resources.styles.colors import Colors, FontSize


# ---- 数据结构 ----

class GraphNode:
    """图谱节点"""
    def __init__(self, node_id: str, label: str, color: str = Colors.graph_node_default):
        self.id = node_id
        self.label = label
        self.color = QColor(color)
        self.x: float = random.uniform(-200, 200)
        self.y: float = random.uniform(-200, 200)
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.radius: float = 22.0
        self._pinned: bool = False  # 拖拽时固定

    @property
    def pos(self) -> QPointF:
        return QPointF(self.x, self.y)


class GraphEdge:
    """图谱连线"""
    def __init__(self, source_id: str, target_id: str, weight: float = 1.0):
        self.source_id = source_id
        self.target_id = target_id
        self.weight = weight
        self.color = QColor(Colors.graph_edge)
        self.highlighted = False


# ---- 力导向画布 ----

class GraphCanvas(QWidget):
    """知识图谱画布 — 纯 QPainter 绘制"""

    # 物理参数
    REPULSION = 5000.0     # 斥力常数
    ATTRACTION = 0.01      # 引力常数
    DAMPING = 0.85          # 阻尼系数
    MIN_VELOCITY = 0.1      # 最小速度（停止阈值）

    def __init__(self):
        super().__init__()
        self.setMinimumSize(400, 300)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._offset = QPointF(0, 0)       # 平移偏移
        self._scale = 1.0                    # 缩放
        self._dragging_node: Optional[GraphNode] = None
        self._panning = False
        self._last_mouse_pos = QPointF()
        self._simulating = False

        # 动画定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._simulate_step)
        self._timer.setInterval(16)  # ~60fps

    # ============================================================
    # 数据加载
    # ============================================================

    def set_data(self, nodes: list[GraphNode], edges: list[GraphEdge]):
        """加载图谱数据并启动模拟"""
        self._nodes = {n.id: n for n in nodes}
        self._edges = edges
        self._simulating = True
        self._timer.start()
        self.update()

    def clear(self):
        self._nodes.clear()
        self._edges.clear()
        self._timer.stop()
        self._simulating = False
        self.update()

    # ============================================================
    # 力导向模拟（每帧一步）
    # ============================================================

    def _simulate_step(self):
        if not self._simulating:
            return

        nodes = list(self._nodes.values())
        if not nodes:
            self._timer.stop()
            return

        forces = {n.id: [0.0, 0.0] for n in nodes}

        # 1. 计算斥力（每对节点）
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                dx = a.x - b.x
                dy = a.y - b.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 1:
                    dist = 1
                force = self.REPULSION / (dist * dist)
                fx = (dx / dist) * force
                fy = (dy / dist) * force
                forces[a.id][0] += fx
                forces[a.id][1] += fy
                forces[b.id][0] -= fx
                forces[b.id][1] -= fy

        # 2. 计算引力（有连线的节点对）
        for edge in self._edges:
            a = self._nodes.get(edge.source_id)
            b = self._nodes.get(edge.target_id)
            if not a or not b:
                continue
            dx = b.x - a.x
            dy = b.y - a.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 1:
                dist = 1
            force = dist * self.ATTRACTION * edge.weight
            fx = (dx / dist) * force
            fy = (dy / dist) * force
            forces[a.id][0] += fx
            forces[a.id][1] += fy
            forces[b.id][0] -= fx
            forces[b.id][1] -= fy

        # 3. 应用力 + 阻尼
        max_vel = 0.0
        for node in nodes:
            if node._pinned:
                continue
            fx, fy = forces[node.id]
            node.vx = (node.vx + fx) * self.DAMPING
            node.vy = (node.vy + fy) * self.DAMPING
            node.x += node.vx
            node.y += node.vy
            vel = math.sqrt(node.vx * node.vx + node.vy * node.vy)
            if vel > max_vel:
                max_vel = vel

        # 4. 速度足够小 → 停止模拟
        if max_vel < self.MIN_VELOCITY:
            self._simulating = False
            self._timer.stop()

        self.update()

    # ============================================================
    # 绘制
    # ============================================================

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        painter.fillRect(self.rect(), QColor(Colors.bg_content))

        # 变换
        painter.translate(self.width() / 2 + self._offset.x(),
                          self.height() / 2 + self._offset.y())
        painter.scale(self._scale, self._scale)

        # 画连线
        for edge in self._edges:
            a = self._nodes.get(edge.source_id)
            b = self._nodes.get(edge.target_id)
            if not a or not b:
                continue

            pen = QPen()
            if edge.highlighted:
                pen.setColor(QColor(Colors.graph_edge_highlight))
                pen.setWidthF(2.0 / self._scale)
            else:
                pen.setColor(edge.color)
                pen.setWidthF(1.0 / self._scale)
            painter.setPen(pen)
            painter.drawLine(a.pos, b.pos)

        # 画节点
        for node in self._nodes.values():
            self._draw_node(painter, node)

    def _draw_node(self, painter: QPainter, node: GraphNode):
        """绘制单个节点（圆形 + 标签）"""
        r = node.radius

        # 圆形背景
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(node.color))
        painter.drawEllipse(node.pos, r, r)

        # 标签文字
        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        painter.setPen(QColor(Colors.text_primary))

        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(node.label)
        # 截断过长文字
        label = node.label
        if text_width > r * 3:
            label = fm.elidedText(label, Qt.TextElideMode.ElideRight, int(r * 3))

        text_rect = QRectF(
            node.x - r * 1.5,
            node.y + r + 6,
            r * 3,
            20
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

    # ============================================================
    # 交互
    # ============================================================

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # 检查是否点击了节点
            pos = self._to_scene(event.position())
            for node in self._nodes.values():
                dx = pos.x() - node.x
                dy = pos.y() - node.y
                if math.sqrt(dx * dx + dy * dy) < node.radius:
                    node._pinned = True
                    self._dragging_node = node
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                    return

            # 否则开始平移
            self._panning = True
            self._last_mouse_pos = event.position()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging_node:
            pos = self._to_scene(event.position())
            self._dragging_node.x = pos.x()
            self._dragging_node.y = pos.y()
            self._simulating = True
            self._timer.start()
            self.update()
        elif self._panning:
            delta = event.position() - self._last_mouse_pos
            self._offset += delta
            self._last_mouse_pos = event.position()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._dragging_node:
            self._dragging_node._pinned = False
            self._dragging_node = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._panning = False

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        new_scale = self._scale * factor
        if 0.2 <= new_scale <= 3.0:
            self._scale = new_scale
            self.update()

    def _to_scene(self, screen_pos) -> QPointF:
        """屏幕坐标 → 场景坐标"""
        return QPointF(
            (screen_pos.x() - self.width() / 2 - self._offset.x()) / self._scale,
            (screen_pos.y() - self.height() / 2 - self._offset.y()) / self._scale,
        )

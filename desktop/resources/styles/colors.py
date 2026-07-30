"""
主题色彩系统
-----------
所有颜色集中管理，方便后期调整。
修改这里的值即可全局生效。

设计原则:
  - 使用语义化命名（bg_primary 而非 gray_100）
  - 按功能分层: 背景 / 文字 / 边框 / 强调
  - 支持后期扩展为多主题（亮色/暗色切换）

使用方式:
    from resources.styles.colors import Colors
    btn.setStyleSheet(f"background: {Colors.accent_blue};")
"""


class Colors:
    """全局色彩常量"""

    # ============================================================
    # 背景色
    # ============================================================
    bg_workspace = "#111110"       # 最外层背景
    bg_sidebar = "#191918"        # 侧边栏背景
    bg_content = "#1D1D1C"        # 内容区背景
    bg_card = "#252523"           # 卡片/面板背景
    bg_card_hover = "#2A2A28"     # 卡片悬停
    bg_input = "#2A2A28"          # 输入框背景
    bg_input_focus = "#31312F"    # 输入框聚焦
    bg_dropdown = "#252523"       # 下拉菜单

    # ============================================================
    # 文字色
    # ============================================================
    text_primary = "#E1E1E0"      # 主要文字
    text_secondary = "#999995"    # 次要文字（说明、占位符）
    text_tertiary = "#6B6B66"     # 三级文字（禁用、提示）
    text_link = "#A1C2FA"         # 链接文字
    text_inverse = "#111110"      # 反色文字（深色按钮上的白字）

    # ============================================================
    # 边框色
    # ============================================================
    border_default = "#2E2E2C"    # 默认边框
    border_light = "#3A3A38"      # 浅边框
    border_focus = "#5A5A56"      # 聚焦边框

    # ============================================================
    # 强调色
    # ============================================================
    accent_blue = "#6B9FFF"       # 主强调色 — 按钮、选中、链接
    accent_blue_hover = "#85B0FF" # 悬停
    accent_green = "#7ACB8C"      # 成功/确认
    accent_yellow = "#E5C76B"     # 警告
    accent_red = "#E06C75"        # 错误/删除
    accent_purple = "#C792EA"     # AI/特殊功能

    # ============================================================
    # 侧边栏专用
    # ============================================================
    sidebar_item_default = "transparent"
    sidebar_item_hover = "#252523"
    sidebar_item_active = "#2E2E2C"
    sidebar_divider = "#2E2E2C"
    sidebar_user_section = "#151514"

    # ============================================================
    # 聊天气泡
    # ============================================================
    chat_user_bg = "#2E3A52"       # 用户消息气泡
    chat_assistant_bg = "#252523"  # AI 消息气泡
    chat_code_bg = "#1A1A19"       # 代码块背景

    # ============================================================
    # 知识图谱
    # ============================================================
    graph_node_default = "#6B9FFF"
    graph_node_highlight = "#C792EA"
    graph_edge = "#3A3A38"
    graph_edge_highlight = "#6B9FFF"


# 间距常量（px）
class Spacing:
    xs = 4
    sm = 8
    md = 12
    lg = 16
    xl = 24
    xxl = 32


# 圆角常量（px）
class Radius:
    sm = 4
    md = 8
    lg = 12
    full = 999


# 字体大小（px）
class FontSize:
    xs = 11
    sm = 12
    md = 13
    lg = 14
    xl = 16
    xxl = 20
    title = 24

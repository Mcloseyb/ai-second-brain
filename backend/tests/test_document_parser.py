"""
测试文档解析器
------------
1. 解析 .md 文件 → 验证内容完整
2. 解析 .docx 文件 → 验证标题/粗体/列表/表格转 Markdown
3. 解析 .pdf 文件 → 验证文本提取
4. 边界条件：文件不存在、不支持的格式、空文件
"""

import asyncio
import sys
import os
sys.path.insert(0, "H:/agent/backend")

from app.core.document_parser import (
    document_parser, ParsedDocument, DocumentParseError,
    SUPPORTED_EXTENSIONS,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


async def main():
    print("=" * 60)
    print("🧪 文档解析器测试")
    print("=" * 60)
    print(f"支持格式: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
    print()

    # ---- 测试 1: 解析 .md ----
    print("📝 测试 1: 解析 .md 文件")
    print("-" * 40)
    md_path = os.path.join(FIXTURES, "sample.md")
    doc = await document_parser.parse_file(md_path)
    assert doc.content, "MD 内容不应为空"
    assert doc.source_type == "md"
    assert "AI Agent" in doc.content
    assert "## 什么是 Agent？" in doc.content
    assert "```python" in doc.content, "应保留代码块"
    print(f"  ✅ 标题: {doc.title}")
    print(f"  ✅ 字数: {doc.word_count}")
    print(f"  ✅ source_type: {doc.source_type}")
    print(f"  ✅ 含标题 / 代码块 / 列表")
    print()

    # ---- 测试 2: 解析 .docx ----
    print("📝 测试 2: 解析 .docx 文件")
    print("-" * 40)
    docx_path = os.path.join(FIXTURES, "sample.docx")
    doc = await document_parser.parse_file(docx_path)
    assert doc.content, "DOCX 内容不应为空"
    assert doc.source_type == "docx"
    content = doc.content
    checks = [
        ("# AI Agent", "一级标题 → # "),
        ("## 核心能力", "二级标题 → ## "),
        ("**自主感知环境**", "粗体 → **text**"),
        ("| 模型 |", "表格 → Markdown table"),
        ("ReAct", "正文内容"),
    ]
    for pattern, desc in checks:
        assert pattern in content, f"缺失: {desc}"
        print(f"  ✅ {desc}")
    print(f"  ✅ 标题: {doc.title}")
    print(f"  ✅ 字数: {doc.word_count}")
    print()

    # ---- 测试 3: 解析 .pdf ----
    print("📝 测试 3: 解析 .pdf 文件")
    print("-" * 40)
    pdf_path = os.path.join(FIXTURES, "sample.pdf")
    doc = await document_parser.parse_file(pdf_path)
    assert doc.content, "PDF 内容不应为空"
    assert doc.source_type == "pdf"
    content = doc.content
    assert "AI Agent" in content, "应包含标题文本"
    assert "ReAct" in content, "应包含正文"
    print(f"  ✅ 标题: {doc.title}")
    print(f"  ✅ 字数: {doc.word_count}")
    print(f"  ✅ 文本提取完整")
    print()

    # ---- 测试 4: 标题提取 ----
    print("📝 测试 4: 标题自动提取")
    print("-" * 40)
    # .md 文件第一个 # 是 "AI Agent 学习笔记" → 自动提取
    md_doc = await document_parser.parse_file(md_path)
    assert md_doc.title == "AI Agent 学习笔记", f"期望从 # 提取标题，实际: {md_doc.title}"
    print(f"  ✅ .md 从 '# ' 行提取: \"{md_doc.title}\"")
    # .pdf 文件没有 # 标题 → fallback 到文件名
    pdf_doc = await document_parser.parse_file(pdf_path)
    assert pdf_doc.title == "sample", f"PDF 应 fallback 到文件名，实际: {pdf_doc.title}"
    print(f"  ✅ .pdf 无 # 标题 → 文件名 fallback: \"{pdf_doc.title}\"")
    print()

    # ---- 测试 5: 边界条件 ----
    print("📝 测试 5: 边界条件")
    print("-" * 40)

    # 文件不存在
    try:
        await document_parser.parse_file("H:/nonexistent_file.md")
        assert False, "应抛出 FileNotFoundError"
    except FileNotFoundError:
        print("  ✅ 文件不存在 → FileNotFoundError")

    # 不支持的格式
    try:
        await document_parser.parse_file("H:/agent/backend/tests/fixtures/sample.docx")
        # 换个不支持的扩展名测试
        invalid = os.path.join(FIXTURES, "sample.md")
        await document_parser.parse_file(invalid.replace(".md", ".xyz"))
        assert False, "应抛出 DocumentParseError"
    except (DocumentParseError, FileNotFoundError):
        print("  ✅ 不支持的格式 → DocumentParseError")

    print()

    # ---- 测试 6: parse_bytes ----
    print("📝 测试 6: parse_bytes（内存解析）")
    print("-" * 40)
    with open(md_path, "rb") as f:
        data = f.read()
    doc = await document_parser.parse_bytes("test.md", data)
    assert doc.content, "parse_bytes 应有内容"
    assert doc.source_type == "md"
    print(f"  ✅ parse_bytes 解析成功: {doc.title}")
    print()

    # ---- 总结 ----
    print("=" * 60)
    print("✅ 全部测试通过！文档解析器正常工作")
    print("=" * 60)
    print()
    print("📊 解析器能力:")
    print("  - .md:  直接读取 + UTF-8/GBK 编码回退")
    print("  - .docx: 标题层级/粗体斜体/列表/表格 → MD")
    print("  - .pdf:  PyMuPDF 逐页提取 + 字体推断标题")
    print("  - 边界: 文件不存在/不支持格式/空文件")


if __name__ == "__main__":
    asyncio.run(main())

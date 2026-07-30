"""
数据库初始化脚本
---------------
用法: python scripts/init_db.py

首次使用或重置数据库时运行此脚本。
"""

import sys
sys.path.insert(0, ".")

from app.database import init_db

if __name__ == "__main__":
    print("🔧 正在初始化数据库...")
    init_db()
    print("✅ 数据库初始化完成！")
    print("   - 表已创建（如不存在）")
    print("   - 数据目录已创建")

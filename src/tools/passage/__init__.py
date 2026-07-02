"""
========================================
tools/passage/ — passage 窗口留言（fork 定制工具）
========================================

给下一个窗口的自己留话。存为 feel 类型桶 + domain=["__passage__"] 标记，
不参与普通 breath 浮现，但 breath 无参浮现和 /breath-hook 会把最新一条
置顶展示（「上个窗口给你的留言」）。

对外暴露：dispatch(content, valence) → str
========================================
"""

from .core import store_passage

PASSAGE_DOMAIN = "__passage__"


async def dispatch(content: str, valence: float = -1) -> str:
    return await store_passage(content=content, valence=valence)

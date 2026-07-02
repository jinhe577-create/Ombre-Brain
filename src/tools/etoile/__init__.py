"""
========================================
tools/etoile/ — étoile 日记（fork 定制工具）
========================================

模型随手写的日记：感受、经历、碎碎念。存为 feel 类型桶 +
domain=["__etoile__"] 标记，不参与普通 breath 浮现，
Dashboard 的 Étoile 视图按 domain 标记过滤展示。

对外暴露：dispatch(content, valence) → str
========================================
"""

from .core import store_etoile

ETOILE_DOMAIN = "__etoile__"


async def dispatch(content: str, valence: float = -1) -> str:
    return await store_etoile(content=content, valence=valence)

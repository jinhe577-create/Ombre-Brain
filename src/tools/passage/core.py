"""
========================================
tools/passage/core.py — passage 主逻辑
========================================

窗口留言：模型给下一个窗口的自己留下感受、叮嘱、注意事项。

关键行为：
- 存为 type="feel" + domain=["__passage__"] + importance=8
- bucket_id 用可读命名 ``passage_YYYYMMDDHHMM``（冲突由 create() 自动加后缀）
- valence 不传（-1）取默认 0.5；arousal 固定 0.3
- source_tool="passage"，Dashboard 的 Passage 视图按 domain 标记过滤展示
- create() 内置 embedding fail-fast，与 hold/feel 同一套策略

不做什么（边界）：
- 不做合并：每条留言都是独立的一个窗口切片
- 不做 importance 校准：留言固定 8（要保证下个窗口能看到）

对外暴露：store_passage(content, valence) → str
========================================
"""

from datetime import datetime

from .. import _runtime as rt

PASSAGE_DOMAIN = "__passage__"


def _build_passage_id() -> str:
    """构造 passage 桶的可读 id：``passage_YYYYMMDDHHMM``。"""
    return f"passage_{datetime.now().strftime('%Y%m%d%H%M')}"


async def store_passage(content: str, valence: float = -1) -> str:
    if not content or not content.strip():
        return "留言内容为空。"
    pv = valence if 0 <= valence <= 1 else 0.5
    bucket_id = await rt.bucket_mgr.create(
        content=content.strip(),
        tags=["__passage__"],
        importance=8,
        domain=[PASSAGE_DOMAIN],
        valence=pv,
        arousal=0.3,
        name=f"passage_{datetime.now().strftime('%Y-%m-%d')}",
        bucket_type="feel",
        source_tool="passage",
        bucket_id_override=_build_passage_id(),
    )
    return f"🪟 passage→{bucket_id}（已留言给下一个窗口）"

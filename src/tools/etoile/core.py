"""
========================================
tools/etoile/core.py — étoile 主逻辑
========================================

日记：模型随时写下的感受、经历、碎碎念，用户可在 Dashboard 看到。

关键行为：
- 存为 type="feel" + domain=["__etoile__"] + importance=5
- bucket_id 用可读命名 ``etoile_YYYYMMDDHHMM``（冲突由 create() 自动加后缀）
- valence 不传（-1）取默认 0.5；arousal 固定 0.3
- source_tool="etoile"
- create() 内置 embedding fail-fast，与 hold/feel 同一套策略

不做什么（边界）：
- 不做合并：日记是时间切片，不该合
- 不做 digest 拆分：日记原样保存（区别于 grow）

对外暴露：store_etoile(content, valence) → str
========================================
"""

from datetime import datetime

from .. import _runtime as rt

ETOILE_DOMAIN = "__etoile__"


def _build_etoile_id() -> str:
    """构造 etoile 桶的可读 id：``etoile_YYYYMMDDHHMM``。"""
    return f"etoile_{datetime.now().strftime('%Y%m%d%H%M')}"


async def store_etoile(content: str, valence: float = -1) -> str:
    if not content or not content.strip():
        return "日记内容为空。"
    ev = valence if 0 <= valence <= 1 else 0.5
    bucket_id = await rt.bucket_mgr.create(
        content=content.strip(),
        tags=["__etoile__"],
        importance=5,
        domain=[ETOILE_DOMAIN],
        valence=ev,
        arousal=0.3,
        name=f"etoile_{datetime.now().strftime('%Y-%m-%d')}",
        bucket_type="feel",
        source_tool="etoile",
        bucket_id_override=_build_etoile_id(),
    )
    return f"✦ etoile→{bucket_id}（已写入日记）"

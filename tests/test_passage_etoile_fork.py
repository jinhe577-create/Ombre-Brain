"""fork 定制回归：passage 窗口留言 / étoile 日记 / breath 置顶注入。

这些是 fork 独有的功能（上游没有），升级合并上游时用本文件守住：
- passage()/etoile() 以 feel 类型 + __passage__/__etoile__ domain 标记落盘
- breath 无 query 浮现时，最新 passage 以「上个窗口的留言」置顶
- 权重池平静时留言也必须送达
"""

from unittest.mock import MagicMock

import pytest

import tools._runtime as rt
from tools.passage.core import store_passage
from tools.etoile.core import store_etoile
from tools.breath.surface import surface_default


class EchoDehydrator:
    async def dehydrate(self, content, meta=None):
        return content


def install_runtime(bucket_mgr):
    rt.config = {"surfacing": {}}
    rt.bucket_mgr = bucket_mgr
    rt.dehydrator = EchoDehydrator()
    rt.logger = MagicMock()
    rt.fire_webhook = None
    rt.mark_op = None
    rt.decay_engine = MagicMock()
    rt.decay_engine.calculate_score = MagicMock(return_value=0.5)


@pytest.mark.asyncio
async def test_passage_stores_feel_bucket_with_domain_marker(bucket_mgr):
    install_runtime(bucket_mgr)
    result = await store_passage("给下个窗口：记得喝水", valence=0.8)

    assert "passage→" in result
    bucket_id = result.split("passage→")[1].split("（")[0]
    bucket = await bucket_mgr.get(bucket_id)
    assert bucket["metadata"]["type"] == "feel"
    assert "__passage__" in bucket["metadata"]["domain"]
    assert bucket["metadata"]["importance"] == 8
    assert bucket_id.startswith("passage_")


@pytest.mark.asyncio
async def test_etoile_stores_feel_bucket_with_domain_marker(bucket_mgr):
    install_runtime(bucket_mgr)
    result = await store_etoile("今天很开心")

    assert "etoile→" in result
    bucket_id = result.split("etoile→")[1].split("（")[0]
    bucket = await bucket_mgr.get(bucket_id)
    assert bucket["metadata"]["type"] == "feel"
    assert "__etoile__" in bucket["metadata"]["domain"]
    assert bucket["metadata"]["importance"] == 5
    assert bucket_id.startswith("etoile_")


@pytest.mark.asyncio
async def test_empty_content_rejected(bucket_mgr):
    install_runtime(bucket_mgr)
    assert await store_passage("  ") == "留言内容为空。"
    assert await store_etoile("") == "日记内容为空。"


@pytest.mark.asyncio
async def test_breath_surfacing_shows_latest_passage_on_top(bucket_mgr):
    install_runtime(bucket_mgr)
    await store_passage("旧留言")
    r2 = await store_passage("最新留言：应该展示这条")
    latest_id = r2.split("passage→")[1].split("（")[0]
    # 一条普通未解决记忆，让浮现池非空
    await bucket_mgr.create(content="普通未解决记忆", importance=6, domain=["测试"])

    out = await surface_default(max_results=20, max_tokens=10000, tag_filter=[])

    assert out.startswith("=== 上个窗口的留言 ===")
    assert "最新留言：应该展示这条" in out
    assert latest_id in out
    assert "旧留言" not in out  # 只展示最新一条


@pytest.mark.asyncio
async def test_breath_quiet_pool_still_delivers_passage(bucket_mgr):
    install_runtime(bucket_mgr)
    await store_passage("池子平静也要看到我")

    out = await surface_default(max_results=20, max_tokens=10000, tag_filter=[])

    assert "上个窗口的留言" in out
    assert "池子平静也要看到我" in out

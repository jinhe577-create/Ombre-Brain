"""
========================================
web/passages.py — passage/étoile/trace 统计（fork 定制路由）
========================================

- /api/passages：列出所有窗口留言（最新在前，带 window_no 反向编号）
- /api/etoiles：列出所有 étoile 日记（最新在前）
- /api/trace：Trace 视图的综合统计（总数/总字数/类型分布/passage/etoile/
  resolved/pinned/digested/最早最晚时间）

对外暴露：register(mcp)。
========================================
"""

from starlette.requests import Request
from starlette.responses import Response

from . import _shared as sh

try:
    from utils import strip_wikilinks  # type: ignore
except ImportError:  # pragma: no cover
    from ..utils import strip_wikilinks  # type: ignore

PASSAGE_DOMAIN = "__passage__"
ETOILE_DOMAIN = "__etoile__"


def register(mcp) -> None:

    @mcp.custom_route("/api/passages", methods=["GET"])
    async def api_passages(request: Request) -> Response:
        """List passage messages, newest first, with reverse window numbering."""
        from starlette.responses import JSONResponse
        err = sh._require_auth(request)
        if err:
            return err
        try:
            all_buckets = await sh.bucket_mgr.list_all(include_archive=False)
            passages = [
                b for b in all_buckets
                if PASSAGE_DOMAIN in b.get("metadata", {}).get("domain", [])
            ]
            passages.sort(key=lambda b: (str(b["metadata"].get("created", "")), str(b["id"])), reverse=True)
            result = []
            for idx, b in enumerate(passages):
                meta = b["metadata"]
                result.append({
                    "id": b["id"],
                    "window_no": len(passages) - idx,
                    "content": strip_wikilinks(b.get("content", "")),
                    "valence": meta.get("valence", 0.5),
                    "created": str(meta.get("created", "")),
                })
            return JSONResponse(result)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @mcp.custom_route("/api/etoiles", methods=["GET"])
    async def api_etoiles(request: Request) -> Response:
        """List étoile diary entries, newest first."""
        from starlette.responses import JSONResponse
        err = sh._require_auth(request)
        if err:
            return err
        try:
            all_buckets = await sh.bucket_mgr.list_all(include_archive=False)
            etoiles = [
                b for b in all_buckets
                if ETOILE_DOMAIN in b.get("metadata", {}).get("domain", [])
            ]
            etoiles.sort(key=lambda b: (str(b["metadata"].get("created", "")), str(b["id"])), reverse=True)
            result = [
                {
                    "id": b["id"],
                    "content": strip_wikilinks(b.get("content", "")),
                    "valence": b["metadata"].get("valence", 0.5),
                    "created": str(b["metadata"].get("created", "")),
                }
                for b in etoiles
            ]
            return JSONResponse(result)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @mcp.custom_route("/api/trace", methods=["GET"])
    async def api_trace(request: Request) -> Response:
        """Aggregate stats for the Trace view."""
        from starlette.responses import JSONResponse
        err = sh._require_auth(request)
        if err:
            return err
        try:
            all_buckets = await sh.bucket_mgr.list_all(include_archive=True)
            total_chars = 0
            type_counts: dict[str, int] = {}
            feel_pure = passages_count = etoiles_count = 0
            resolved = unresolved = pinned = digested = 0
            oldest_date = newest_date = None
            for b in all_buckets:
                meta = b.get("metadata", {})
                total_chars += len(b.get("content", ""))
                btype = meta.get("type", "dynamic")
                type_counts[btype] = type_counts.get(btype, 0) + 1
                domains = meta.get("domain", [])
                if btype == "feel":
                    if PASSAGE_DOMAIN in domains:
                        passages_count += 1
                    elif ETOILE_DOMAIN in domains:
                        etoiles_count += 1
                    else:
                        feel_pure += 1
                if meta.get("resolved"):
                    resolved += 1
                else:
                    unresolved += 1
                if meta.get("pinned"):
                    pinned += 1
                if meta.get("digested"):
                    digested += 1
                created = str(meta.get("created", ""))
                if created:
                    if oldest_date is None or created < oldest_date:
                        oldest_date = created
                    if newest_date is None or created > newest_date:
                        newest_date = created
            return JSONResponse({
                "total": len(all_buckets),
                "total_chars": total_chars,
                "types": type_counts,
                "feel_pure": feel_pure,
                "passages": passages_count,
                "etoiles": etoiles_count,
                "resolved": resolved,
                "unresolved": unresolved,
                "pinned": pinned,
                "digested": digested,
                "oldest": oldest_date,
                "newest": newest_date,
            })
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @mcp.custom_route("/api/domain-stats", methods=["GET"])
    async def api_domain_stats(request: Request) -> Response:
        """Domain distribution statistics for the Trace view chart."""
        from starlette.responses import JSONResponse
        err = sh._require_auth(request)
        if err:
            return err
        try:
            all_buckets = await sh.bucket_mgr.list_all(include_archive=True)
            domain_counts: dict[str, int] = {}
            type_counts: dict[str, int] = {}
            total_resolved = total_unresolved = 0
            for b in all_buckets:
                meta = b.get("metadata", {})
                btype = meta.get("type", "dynamic")
                type_counts[btype] = type_counts.get(btype, 0) + 1
                for d in (meta.get("domain") or ["未分类"]):
                    domain_counts[d] = domain_counts.get(d, 0) + 1
                if meta.get("resolved"):
                    total_resolved += 1
                else:
                    total_unresolved += 1
            sorted_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)
            return JSONResponse({
                "domains": [{"name": d, "count": c} for d, c in sorted_domains],
                "types": type_counts,
                "resolved": total_resolved,
                "unresolved": total_unresolved,
                "total": len(all_buckets),
            })
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

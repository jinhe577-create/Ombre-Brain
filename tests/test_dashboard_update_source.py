from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# fork 定制：更新源指向自己的 fork（jinhe577-create/Ombre-Brain），
# 防止 Dashboard 一键更新拉官方版覆盖薄荷绿主题/passage/etoile 等定制。
FORK_REPO = "jinhe577-create/Ombre-Brain"


def test_dashboard_version_check_uses_github_api_before_raw_cdn_fallback():
    api_url = f"https://api.github.com/repos/{FORK_REPO}/contents/VERSION?ref=main"
    raw_url = f"https://raw.githubusercontent.com/{FORK_REPO}/main/VERSION?t="

    for rel_path in ("dashboard.html", "frontend/dashboard.html"):
        html = (ROOT / rel_path).read_text(encoding="utf-8")

        assert api_url in html
        assert raw_url in html
        assert html.index(api_url) < html.index(raw_url)


def test_dashboard_update_never_points_at_upstream_repo():
    """一键更新绝不能指回官方仓库——那会把 fork 的全部定制冲掉。"""
    for rel_path in ("dashboard.html", "frontend/dashboard.html"):
        html = (ROOT / rel_path).read_text(encoding="utf-8")
        assert "api.github.com/repos/P0luz/Ombre-Brain" not in html
        assert "raw.githubusercontent.com/P0luz/Ombre-Brain" not in html

    meta_py = (ROOT / "src" / "web" / "meta.py").read_text(encoding="utf-8")
    assert 'or "P0luz/Ombre-Brain"' not in meta_py
    assert FORK_REPO in meta_py

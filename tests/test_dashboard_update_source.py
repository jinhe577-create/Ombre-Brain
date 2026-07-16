from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# fork 定制：更新源指向自己的 fork（jinhe577-create/Ombre-Brain），
# 防止 Dashboard 一键更新拉官方版覆盖薄荷绿主题/passage/etoile 等定制。
FORK_REPO = "jinhe577-create/Ombre-Brain"


def test_dashboard_version_check_uses_github_api_before_raw_cdn_fallback():
    api_url = f"https://api.github.com/repos/{FORK_REPO}/contents/VERSION?ref=main"
    raw_url = f"https://raw.githubusercontent.com/{FORK_REPO}/main/VERSION?t="

    for rel_path in ("frontend/dashboard.html",):
        html = (ROOT / rel_path).read_text(encoding="utf-8")

        assert api_url in html
        assert raw_url in html
        assert html.index(api_url) < html.index(raw_url)


def test_dashboard_update_never_points_at_upstream_repo():
    """一键更新绝不能指回官方仓库——那会把 fork 的全部定制冲掉。"""
    html = (ROOT / "frontend" / "dashboard.html").read_text(encoding="utf-8")
    assert "api.github.com/repos/P0luz/Ombre-Brain" not in html
    assert "raw.githubusercontent.com/P0luz/Ombre-Brain" not in html

    meta_py = (ROOT / "src" / "web" / "meta.py").read_text(encoding="utf-8")
    assert 'or "P0luz/Ombre-Brain"' not in meta_py
    assert FORK_REPO in meta_py


def test_dashboard_hot_update_surfaces_csrf_proxy_guidance():
    html = (ROOT / "frontend" / "dashboard.html").read_text(encoding="utf-8")
    block = html[html.index("window.doHotUpdate = async function()") :]
    block = block[: block.index("window.checkGitHubVersion = async function()")]

    assert "fetch(BASE + '/api/do-update'" in block
    assert "authFetch(BASE + '/api/do-update'" not in block
    assert "热更新不是可重试写操作" in block
    assert "failure.error === 'Cross-origin request rejected'" in block
    assert "这不是 CORS 缺失" in block
    assert "OMBRE_TRUSTED_PROXY_CIDRS" in block


def test_fork_repo_is_trusted_update_source():
    """fork 仓库必须在热更新可信白名单里，否则一键更新会被安全闸门拒绝。"""
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from web import meta

    assert meta._update_repo_allowed(FORK_REPO)
    assert meta._update_repo_allowed("P0luz/Ombre-Brain")
    assert not meta._update_repo_allowed("evil/repo")

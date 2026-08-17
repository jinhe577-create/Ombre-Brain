"""fork 回归：登录/改密码错误提示必须读后端真实字段 `error`。

历史 bug：前端 doLogin/changePassword 读 `d.detail`，但后端 /auth/login
所有失败（429 限流、401 密码错、409 密码已变更、400 格式）统一返回
`{"error": ...}`。字段名不匹配导致任何登录失败都 fallback 成「密码错误」
——把限流伪装成密码问题，用户反复重试→更被限流→死循环，且完全看不到
真实原因。此测试锁住修复，防止合并上游前端时回归。
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "dashboard.html").read_text(encoding="utf-8")


def _fn_body(name: str) -> str:
    start = HTML.index(f"async function {name}(")
    nxt = HTML.index("async function ", start + 10)
    return HTML[start:nxt]


def test_dologin_reads_error_field():
    body = _fn_body("doLogin")
    assert "d.error" in body


def test_dologin_trims_password():
    """iOS 钥匙串自动填充常带首尾空白，提交前 trim 避免看着对却不匹配。"""
    body = _fn_body("doLogin")
    assert ".value.trim()" in body


def test_change_password_reads_error_field():
    body = _fn_body("changePassword")
    assert "d.error" in body


def test_login_input_has_current_password_autocomplete():
    """让 iOS/浏览器把正确的已存密码填进来，减少填错。"""
    idx = HTML.index('id="auth-login-pwd"')
    tag = HTML[idx:idx + 200]
    assert 'autocomplete="current-password"' in tag


def test_no_bare_detail_reads_in_auth_flows():
    """每处 d.detail 前必须有 d.error 兜底；不得单独把 detail 作首选读取。"""
    for m in re.finditer(r"d\.detail", HTML):
        prefix = HTML[max(0, m.start() - 12):m.start()]
        assert "d.error ||" in prefix, f"裸读 d.detail：...{prefix}d.detail"

"""fork 定制回归：面板配置持久化到数据目录（Render/Zeabur 持久盘）。

痛点：Render 上仓库目录随每次部署重建，config.yaml / .env 写在仓库根目录
就会随重启丢失——面板配置的服务商/key/模型全部蒸发。修复后这两个文件
落在 OMBRE_BUCKETS_DIR 指向的持久盘上，并在启动时回载。
"""

import os

import pytest

from utils import (
    config_file_path,
    env_file_path,
    load_env_file_into_environ,
    _persistent_data_dir,
)


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    """隔离掉可能影响路径解析的环境变量，返回一个存在的假数据目录。"""
    for var in ("OMBRE_CONFIG_PATH", "OMBRE_VAULT_DIR", "OMBRE_BUCKETS_DIR"):
        monkeypatch.delenv(var, raising=False)
    data_dir = tmp_path / "disk"
    data_dir.mkdir()
    monkeypatch.chdir(tmp_path)  # cwd 里没有 config.yaml
    return data_dir


def test_config_path_prefers_existing_data_dir_file(clean_env, monkeypatch):
    monkeypatch.setenv("OMBRE_BUCKETS_DIR", str(clean_env))
    cfg = clean_env / "config.yaml"
    cfg.write_text("dehydration: {model: test}\n", encoding="utf-8")
    assert config_file_path() == str(cfg)


def test_config_path_first_write_lands_on_data_dir(clean_env, monkeypatch):
    """数据目录已挂载但还没有 config.yaml（首次保存）→ 写入路径应指向数据目录。"""
    monkeypatch.setenv("OMBRE_BUCKETS_DIR", str(clean_env))
    assert config_file_path() == str(clean_env / "config.yaml")


def test_ombre_config_path_env_still_wins(clean_env, monkeypatch):
    monkeypatch.setenv("OMBRE_BUCKETS_DIR", str(clean_env))
    monkeypatch.setenv("OMBRE_CONFIG_PATH", "/custom/config.yaml")
    assert config_file_path() == "/custom/config.yaml"


def test_env_file_lands_on_data_dir_and_loads_at_boot(clean_env, monkeypatch):
    monkeypatch.setenv("OMBRE_BUCKETS_DIR", str(clean_env))
    assert env_file_path() == str(clean_env / ".env")

    (clean_env / ".env").write_text('AI_NAME=小克\nOMBRE_HOOK_URL="https://x.example/hook"\n', encoding="utf-8")
    monkeypatch.delenv("AI_NAME", raising=False)
    monkeypatch.delenv("OMBRE_HOOK_URL", raising=False)

    loaded = load_env_file_into_environ()

    assert "AI_NAME" in loaded and os.environ["AI_NAME"] == "小克"
    assert os.environ["OMBRE_HOOK_URL"] == "https://x.example/hook"
    monkeypatch.delenv("AI_NAME", raising=False)
    monkeypatch.delenv("OMBRE_HOOK_URL", raising=False)


def test_platform_env_not_overridden_by_env_file(clean_env, monkeypatch):
    """平台注入的进程 env 优先级最高：.env 同名值不得覆盖。"""
    monkeypatch.setenv("OMBRE_BUCKETS_DIR", str(clean_env))
    (clean_env / ".env").write_text("AI_NAME=文件里的名字\n", encoding="utf-8")
    monkeypatch.setenv("AI_NAME", "平台注入的名字")

    loaded = load_env_file_into_environ()

    assert "AI_NAME" not in loaded
    assert os.environ["AI_NAME"] == "平台注入的名字"


def test_no_data_dir_falls_back_to_project_root(clean_env):
    """没配数据目录（裸机默认）→ 行为与上游一致，用项目根目录。"""
    assert _persistent_data_dir() == ""
    assert config_file_path().endswith("config.yaml")
    assert "disk" not in config_file_path()

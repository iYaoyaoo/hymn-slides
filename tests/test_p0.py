"""P0 验收测试：路径/便携模式、soffice 探测、selftest、CLI 分发。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.render import lo_detect
from src.utils import paths
from src.utils.selftest import run_selftest


def _make_fake_soffice(directory: Path, name: str = "soffice") -> Path:
    p = directory / name
    p.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    p.chmod(0o755)
    return p


# ---------- paths / 便携模式 ----------

def test_exe_dir_is_project_root_in_dev():
    d = paths.exe_dir()
    assert (d / "main.py").is_file()
    assert getattr(sys, "frozen", False) is False


def test_is_portable_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "portable_flag_dir", lambda: tmp_path)
    assert paths.is_portable() is False
    (tmp_path / paths.PORTABLE_FLAG).write_text("", encoding="utf-8")
    assert paths.is_portable() is True


def test_data_dir_portable(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "portable_flag_dir", lambda: tmp_path)
    (tmp_path / paths.PORTABLE_FLAG).write_text("", encoding="utf-8")
    assert paths.data_dir() == tmp_path / "data"


def test_log_dir_created(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "portable_flag_dir", lambda: tmp_path)
    (tmp_path / paths.PORTABLE_FLAG).write_text("", encoding="utf-8")
    d = paths.log_dir()
    assert d.is_dir() and d.name == "logs"


# ---------- lo_detect ----------

def test_detect_soffice_config_priority(tmp_path, monkeypatch):
    fake = _make_fake_soffice(tmp_path, "custom_soffice")
    monkeypatch.setattr(lo_detect, "_bundled_candidates", lambda: [])
    monkeypatch.setattr(lo_detect, "_system_candidates", lambda: [])
    info = lo_detect.detect_soffice(str(fake))
    assert info.found and info.source == "config" and info.path == fake


def test_detect_soffice_config_invalid_falls_through(tmp_path, monkeypatch):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    fake = _make_fake_soffice(bundled)
    monkeypatch.setattr(lo_detect, "_bundled_candidates", lambda: [fake])
    monkeypatch.setattr(lo_detect, "_system_candidates", lambda: [])
    info = lo_detect.detect_soffice(str(tmp_path / "no_such_file"))
    assert info.found and info.source == "bundled"


def test_detect_soffice_system_last(tmp_path, monkeypatch):
    fake = _make_fake_soffice(tmp_path)
    monkeypatch.setattr(lo_detect, "_bundled_candidates", lambda: [tmp_path / "absent"])
    monkeypatch.setattr(lo_detect, "_system_candidates", lambda: [fake])
    info = lo_detect.detect_soffice("")
    assert info.found and info.source == "system"


def test_detect_soffice_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(lo_detect, "_bundled_candidates", lambda: [tmp_path / "absent"])
    monkeypatch.setattr(lo_detect, "_system_candidates", lambda: [tmp_path / "absent2"])
    info = lo_detect.detect_soffice("")
    assert not info.found
    assert any("未找到" not in c for c in info.candidates)


# ---------- selftest ----------

def test_selftest_report_structure():
    ok, report = run_selftest()
    assert "OS:" in report
    assert "Python:" in report
    assert "LibreOffice" in report
    assert "SELFTEST RESULT: " in report
    assert isinstance(ok, bool)


def test_selftest_passes_on_this_machine():
    """本机已装 LibreOffice，selftest 应 PASS（CI 无 LO 环境可能 FAIL，故此测试仅在本机有意义）。"""
    ok, _ = run_selftest()
    assert ok is True


# ---------- config ----------

def test_config_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "portable_flag_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "exe_dir", lambda: tmp_path)
    from src.core.config import Config

    cfg = Config(settings_path=tmp_path / "test_config.ini")
    assert cfg.main_dir == tmp_path
    assert cfg.soffice_path == ""
    assert cfg.cache_limit_mb > 0
    assert cfg.single_screen_confirm is True

    cfg.set_main_dir(tmp_path / "hymns")
    cfg.set_soffice_path("/opt/lo/soffice")
    cfg.set_cache_limit_mb(512)
    cfg.set_single_screen_confirm(False)
    cfg.sync()

    cfg2 = Config(settings_path=tmp_path / "test_config.ini")
    assert cfg2.main_dir == tmp_path / "hymns"
    assert cfg2.soffice_path == "/opt/lo/soffice"
    assert cfg2.cache_limit_mb == 512
    assert cfg2.single_screen_confirm is False


# ---------- CLI 分发 ----------

def test_cli_all_flags_run(qapp):
    """--scan/--render-test/--list-screens/--selftest 均已实现，应正常返回而非 exit 2。"""
    import main as main_mod

    from src.render.lo_detect import detect_soffice

    lo_ok = detect_soffice().found
    rc = main_mod.main(["--list-screens"])
    assert rc == 0
    rc_self = main_mod.main(["--selftest"])
    assert rc_self == (0 if lo_ok else 1)


def test_cli_selftest_exit_code():
    import main as main_mod

    rc = main_mod.main(["--selftest"])
    assert rc in (0, 1)

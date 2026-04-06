"""Unit tests for stable window geometry behavior."""

from pathlib import Path

import pytest
from PyQt6.QtCore import QRect, QSettings
from PyQt6.QtWidgets import QMainWindow, QWidget

from ui.MainWindow import MainWindow
from ui.TraceXTab import TraceXTab
from ui.TraceXView import MainWindow as TraceXView
from ui.window_geometry import (
    clamp_rect_to_screen,
    compute_adaptive_rect,
    find_target_screen,
    load_window_settings,
    save_window_settings,
)


@pytest.mark.unit
def test_compute_adaptive_rect_within_screen():
    screen = QRect(0, 0, 1920, 1080)
    rect = compute_adaptive_rect(screen)

    assert rect.width() > 0
    assert rect.height() > 0
    assert rect.left() >= screen.left()
    assert rect.top() >= screen.top()
    assert rect.right() <= screen.right()
    assert rect.bottom() <= screen.bottom()


@pytest.mark.unit
def test_clamp_rect_to_screen():
    screen = QRect(0, 0, 1366, 768)
    offscreen = QRect(-500, -300, 2200, 1400)
    clamped = clamp_rect_to_screen(offscreen, screen)

    assert clamped.left() >= screen.left()
    assert clamped.top() >= screen.top()
    assert clamped.right() <= screen.right()
    assert clamped.bottom() <= screen.bottom()


@pytest.mark.unit
def test_window_settings_roundtrip(qt_app, tmp_path):
    settings_file = tmp_path / "atomx_window_settings.ini"
    settings = QSettings(str(settings_file), QSettings.Format.IniFormat)
    settings.clear()

    win = QMainWindow()
    win.setGeometry(120, 80, 1100, 700)
    save_window_settings(win, settings=settings)

    loaded = load_window_settings(settings=settings)
    rect = loaded["normal_rect"]

    assert rect is not None
    assert (rect.x(), rect.y(), rect.width(), rect.height()) == (120, 80, 1100, 700)
    assert loaded["maximized"] is False


@pytest.mark.unit
def test_find_target_screen_returns_screen(qt_app):
    win = QMainWindow()
    screen = find_target_screen(win)
    assert screen is not None


@pytest.mark.unit
def test_tracex_view_is_widget_not_qmainwindow(qt_app):
    view = TraceXView(project_root=Path.cwd())
    assert isinstance(view, QWidget)
    assert not isinstance(view, QMainWindow)


@pytest.mark.unit
def test_tracex_tab_embeds_expanding_widget(qt_app):
    tab = TraceXTab(can_mgr=None, dbc_parser=None, logger=None)
    view = getattr(tab, "_tracex_window", None)
    assert view is not None
    policy = view.sizePolicy()
    assert policy.horizontalPolicy().name == "Expanding"
    assert policy.verticalPolicy().name == "Expanding"


@pytest.mark.unit
def test_mainwindow_tab_switch_does_not_resize(monkeypatch, qt_app):
    def _fake_init_core(self, profile_name):
        self.inst_mgr = None
        self.dbc_parser = None
        self.signal_manager = None
        self.can_mgr = None
        self.sequencer = None

    monkeypatch.setattr(MainWindow, "initialize_core_components", _fake_init_core)

    win = MainWindow(logger=None, log_path=None)
    win._window_geometry_restored = True
    win.resize(1200, 800)
    win.show()
    qt_app.processEvents()

    before = win.size()
    win.on_tab_changed(win.tracex_tab_index)
    qt_app.processEvents()
    after = win.size()

    assert abs(after.width() - before.width()) <= 2
    assert abs(after.height() - before.height()) <= 2


import sys
import traceback
import logging
from PyQt6.QtWidgets import QApplication, QMessageBox
try:
    import PyQt6.QtWebEngineWidgets
except ImportError:
    pass
import qdarktheme
from logging_setup import setup_logging
from ui.MainWindow import MainWindow
from ui.resources import create_app_icon, create_splash_pixmap
from PyQt6.QtWidgets import QSplashScreen
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QGuiApplication


def _hide_console_if_frozen() -> None:
    """Hide console window when packaged with console bootloader."""
    if not getattr(sys, "frozen", False):
        return
    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass


def _global_exception_handler(exc_type, exc_value, exc_tb):
    """Global exception handler to log unhandled exceptions."""
    logger = logging.getLogger(__name__)
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.critical(f"Unhandled exception:\n{error_msg}")

    # Show error dialog to user
    try:
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Application Error")
        msg_box.setText("An unexpected error occurred.")
        msg_box.setDetailedText(error_msg)
        msg_box.exec()
    except Exception:
        pass  # If we can't show dialog, at least we logged it

    # Call the default handler
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def main():
    # Install global exception handler
    sys.excepthook = _global_exception_handler
    _hide_console_if_frozen()

    logger, log_path = setup_logging()
    try:
        from core.action_catalog import write_action_catalog
        catalog_path = write_action_catalog()
        if catalog_path:
            logger.info(f"Action catalog updated: {catalog_path}")
    except Exception as e:
        try:
            logger.warning(f"Action catalog update skipped: {e}")
        except Exception:
            pass
    # Enable high-DPI scaling so the UI adapts to screen resolution
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setStyleSheet(qdarktheme.load_stylesheet())
    
    from ui.Styles import get_styles
    app.setStyleSheet(app.styleSheet() + get_styles())
    
    # App icon
    app_icon = create_app_icon()
    app.setWindowIcon(app_icon)

    frozen_build = bool(getattr(sys, "frozen", False))
    splash = None
    if not frozen_build:
        # Keep splash/animations for source runs; prefer reliability in packaged EXE.
        splash = QSplashScreen(create_splash_pixmap())
        splash.show()
        app.processEvents()

    window = MainWindow(logger=logger, log_path=log_path)
    window.setWindowIcon(app_icon)
    # Maximized display (keeps window controls visible)
    window.showMaximized()
    window.raise_()
    window.activateWindow()

    if splash is not None:
        splash.finish(window)

    if not frozen_build:
        # Fade-in animation (source run polish only).
        window.setWindowOpacity(0.0)
        anim = QPropertyAnimation(window, b"windowOpacity", window)
        anim.setDuration(700)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.start()
        window._fade_anim = anim  # prevent GC

        # Slide-up animation for added polish (skip when maximized to avoid unmaximizing)
        if not window.isMaximized():
            slide_anim = QPropertyAnimation(window, b"pos", window)
            slide_anim.setDuration(700)
            start_pos = window.pos() + QPoint(0, 30)
            slide_anim.setStartValue(start_pos)
            slide_anim.setEndValue(window.pos())
            slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            slide_anim.start()
            window._slide_anim = slide_anim

    sys.exit(app.exec())

if __name__ == "__main__":
    main()

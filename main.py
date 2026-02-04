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
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QPoint


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
    app = QApplication(sys.argv)
    # qdarktheme.setup_theme() # Not available in 0.1.7
    app.setStyleSheet(qdarktheme.load_stylesheet())
    
    from ui.Styles import get_styles
    app.setStyleSheet(app.styleSheet() + get_styles())
    
    # App icon
    app_icon = create_app_icon()
    app.setWindowIcon(app_icon)

    # Splash screen
    splash = QSplashScreen(create_splash_pixmap())
    splash.show()
    app.processEvents()

    window = MainWindow(logger=logger, log_path=log_path)
    window.setWindowIcon(app_icon)
    window.setWindowOpacity(0.0)
    # Maximized display (keeps window controls visible)
    window.showMaximized()
    splash.finish(window)

    # Fade-in animation
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

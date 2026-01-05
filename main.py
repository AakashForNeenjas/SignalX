import sys
from PyQt6.QtWidgets import QApplication
try:
    import PyQt6.QtWebEngineWidgets
except ImportError:
    pass
import qdarktheme
from logging_setup import setup_logging
from ui.MainWindow import MainWindow
from ui.resources import create_app_icon, create_splash_pixmap
from PyQt6.QtWidgets import QSplashScreen
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QPoint, QRect

def main():
    logger, log_path = setup_logging()
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
    window.show()
    splash.finish(window)

    # Fade-in animation
    anim = QPropertyAnimation(window, b"windowOpacity", window)
    anim.setDuration(700)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
    anim.start()
    window._fade_anim = anim  # prevent GC

    # Slide-up animation for added polish
    slide_anim = QPropertyAnimation(window, b"geometry", window)
    slide_anim.setDuration(700)
    start_rect = window.geometry()
    slide_anim.setStartValue(QRect(start_rect.x(), start_rect.y() + 30, start_rect.width(), start_rect.height()))
    slide_anim.setEndValue(start_rect)
    slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    slide_anim.start()
    window._slide_anim = slide_anim
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

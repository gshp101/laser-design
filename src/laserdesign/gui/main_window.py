"""The main window: a step list, the wizard pages, and Back/Next navigation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QListWidget, QMainWindow,
                               QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from .. import __version__
from . import icons, presets
from .pages import ALL_PAGES
from .spec import DesignSpec

STEP_ICON = 22  # px, icons in the step list


class MainWindow(QMainWindow):
    """Guided laser design window.

    The window owns one :class:`DesignSpec`. Pages write their inputs into it
    and the current page's preview is recomputed shortly after each edit.
    """

    def __init__(self, spec: DesignSpec | None = None):
        super().__init__()
        self.spec = spec or presets.cw_nd_yvo4()
        self.path: Path | None = None
        self.resize(1250, 780)

        self.steps = QListWidget()
        self.steps.setFixedWidth(190)
        self.stack = QStackedWidget()
        self.pages = [cls() for cls in ALL_PAGES]
        self.steps.setIconSize(QSize(STEP_ICON, STEP_ICON))
        for page in self.pages:
            self.steps.addItem(page.title)
            self.stack.addWidget(page)
            page.edited.connect(self._edited)

        self.back = QPushButton("◀ Back")
        self.next = QPushButton("Next ▶")
        self.back.clicked.connect(lambda: self.go(self.current() - 1))
        self.next.clicked.connect(lambda: self.go(self.current() + 1))
        nav = QHBoxLayout()
        nav.addStretch(1)
        nav.addWidget(self.back)
        nav.addWidget(self.next)

        right = QVBoxLayout()
        right.addWidget(self.stack, 1)
        right.addLayout(nav)
        central = QWidget()
        lay = QHBoxLayout(central)
        lay.addWidget(self.steps)
        lay.addLayout(right, 1)
        self.setCentralWidget(central)
        self.steps.currentRowChanged.connect(self._step_selected)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.refresh)

        self._build_menus()
        self.setWindowIcon(icons.app_icon())
        self.refresh_icons()
        self.load_spec(self.spec)
        self.go(0)

    # ------------------------------------------------------------------ #
    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        for text, key, slot in (("&New", QKeySequence.New, self.new_design),
                                ("&Open…", QKeySequence.Open, self.open_design),
                                ("&Save", QKeySequence.Save, self.save_design),
                                ("Save &As…", QKeySequence.SaveAs, self.save_design_as),
                                ("&Quit", QKeySequence.Quit, self.close)):
            act = QAction(text, self)
            act.setShortcut(key)
            act.triggered.connect(slot)
            file_menu.addAction(act)
        preset_menu = self.menuBar().addMenu("&Examples")
        for name, factory in presets.PRESETS.items():
            act = QAction(name, self)
            act.triggered.connect(lambda _=False, f=factory: self.load_spec(f()))
            preset_menu.addAction(act)
        help_menu = self.menuBar().addMenu("&Help")
        about = QAction("&About", self)
        about.triggered.connect(self._about)
        help_menu.addAction(about)

    def _about(self) -> None:
        QMessageBox.about(self, "laserdesign",
                          f"<b>laserdesign {__version__}</b><p>Guided design of solid state "
                          "lasers. Physics after Siegman, Milonni & Eberly and Koechner; see "
                          "the documentation for the models and their assumptions.</p>")

    def refresh_icons(self) -> None:
        """Redraw step and page icons in the current palette."""
        for row, page in enumerate(self.pages):
            if page.icon_name:
                self.steps.item(row).setIcon(icons.icon(page.icon_name))
            page.refresh_icons()

    def changeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if (event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange)
                and hasattr(self, "pages")):
            self.refresh_icons()
        super().changeEvent(event)

    # ------------------------------------------------------------------ #
    def current(self) -> int:
        return self.stack.currentIndex()

    def go(self, index: int) -> None:
        index = max(0, min(index, len(self.pages) - 1))
        self.steps.setCurrentRow(index)

    def _step_selected(self, index: int) -> None:
        if index < 0:
            return
        self.store_all()
        self.stack.setCurrentIndex(index)
        self.back.setEnabled(index > 0)
        self.next.setEnabled(index < len(self.pages) - 1)
        self.refresh()

    def _edited(self) -> None:
        self.store_all()
        self._timer.start()

    def store_all(self) -> None:
        for page in self.pages:
            page.store(self.spec)

    def refresh(self) -> None:
        """Recompute the preview of the visible page."""
        page = self.pages[self.current()]
        try:
            page.refresh(self.spec)
        except Exception as exc:  # keep the GUI alive on unexpected model errors
            self.statusBar().showMessage(f"Error: {exc}", 8000)
        else:
            problems = self.spec.validate()
            self.statusBar().showMessage("; ".join(problems) if problems else self.spec.name)

    def load_spec(self, spec: DesignSpec) -> None:
        self.spec = spec
        for page in self.pages:
            page.load(spec)
        self.setWindowTitle(f"laserdesign: {spec.name}")
        self.refresh()

    # ------------------------------------------------------------------ #
    def new_design(self) -> None:
        self.path = None
        self.load_spec(DesignSpec())
        self.go(0)

    def open_design(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(self, "Open design", "", "Laser design (*.json)")
        if fn:
            self.open_path(Path(fn))

    def open_path(self, path: Path) -> None:
        try:
            spec = DesignSpec.load(path)
        except Exception as exc:
            QMessageBox.warning(self, "Could not open design", str(exc))
            return
        self.path = path
        self.load_spec(spec)

    def save_design(self) -> None:
        if self.path is None:
            self.save_design_as()
        else:
            self.store_all()
            self.spec.save(self.path)
            self.statusBar().showMessage(f"Saved {self.path}", 4000)

    def save_design_as(self) -> None:
        fn, _ = QFileDialog.getSaveFileName(self, "Save design", "design.json",
                                            "Laser design (*.json)")
        if fn:
            self.path = Path(fn)
            self.save_design()

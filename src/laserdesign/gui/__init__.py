"""Qt (PySide6) GUI that guides the user through designing a laser.

Start it with ``laserdesign-gui`` or ``python -m laserdesign.gui``. The
Qt-free parts (:mod:`.spec`, :mod:`.presets`) can be used without PySide6.
"""

from .presets import PRESETS
from .spec import DesignSpec, build_laser

__all__ = ["DesignSpec", "build_laser", "PRESETS"]

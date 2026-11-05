"""Browser front end: the guided wizard running under Pyodide.

The static web app in the repository's ``web/`` folder loads this package
into Pyodide (CPython compiled to WebAssembly) and calls
:mod:`laserdesign.web.api`. :mod:`laserdesign.web.report` computes what each
wizard step shows as plain data; it needs neither Qt nor matplotlib and runs
the same under CPython and Pyodide.
"""

from .report import STEPS

__all__ = ["STEPS"]

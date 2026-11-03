"""Sphinx configuration for laserdesign."""

import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

project = "laserdesign"
author = "Joe"
copyright = "2026, Joe"
release = "0.2.0"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.mathjax",
    "sphinx.ext.viewcode",
    "sphinx.ext.doctest",
]

myst_enable_extensions = ["dollarmath", "amsmath", "deflist", "colon_fence"]
napoleon_numpy_docstring = True
napoleon_google_docstring = False
autodoc_member_order = "bysource"
autodoc_default_options = {"members": True, "undoc-members": False, "show-inheritance": True}
autosummary_generate = False

source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
exclude_patterns = ["_build"]

html_theme = "furo"
html_title = "laserdesign"

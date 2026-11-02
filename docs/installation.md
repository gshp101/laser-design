# Installation

`laserdesign` needs Python 3.10 or newer, NumPy and SciPy.

```bash
git clone https://github.com/gshp101/laser-design.git
cd laser-design
python -m pip install -e ".[plot,test]"
```

Optional extras:

| Extra   | Installs                         | For                         |
|---------|----------------------------------|-----------------------------|
| `plot`  | matplotlib                       | the tutorial and examples   |
| `gui`   | PySide6, matplotlib              | the graphical design wizard |
| `docs`  | Sphinx, MyST, Furo               | building this documentation |
| `test`  | pytest                           | running the test suite      |

Run the tests with

```bash
python -m pytest
```

and build the documentation with

```bash
python -m pip install -e ".[docs]"
sphinx-build -b html docs docs/_build/html
```

# Example designs

Four worked designs, each a runnable script in `examples/` that prints a
summary and regenerates the figures on these pages:

```bash
python examples/cw_nd_yvo4.py
python examples/qswitched_nd_yag.py
python examples/modelocked_nd_yvo4_sesam.py
python examples/koechner_side_pumped_rod.py
```

| Example | Laser | Shows |
|---|---|---|
| {doc}`cw_nd_yvo4` | 30 W end-pumped CW Nd:YVO4 | thermal lens vs. stability, mode matching, output coupler choice, M² |
| {doc}`qswitched_nd_yag` | 20 W end-pumped AO Q-switched Nd:YAG | energy, width, peak and average power vs repetition rate, pulse shape, coating damage margin |
| {doc}`modelocked_nd_yvo4_sesam` | 100 MHz SESAM mode-locked Nd:YVO4 | folded astigmatic cavity, QML margin, SESAM saturation, pulse width |
| {doc}`koechner_side_pumped_rod` | side-pumped Nd:YAG rod (after Koechner) | bifocusing, fracture limit, thermally loaded flat-flat resonator, Q-switch extraction |

The numbers come from the library's models, which are idealised: they leave
out energy-transfer upconversion, excited-state absorption, spatial hole
burning and imperfect pump spectra, so real lasers typically reach 70 to 90 %
of the predicted efficiency and need a somewhat higher threshold. The
examples are meant for comparing design choices and seeing trends, which the
models capture well.

```{toctree}
:maxdepth: 1

cw_nd_yvo4
qswitched_nd_yag
modelocked_nd_yvo4_sesam
koechner_side_pumped_rod
```

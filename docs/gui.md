# GUI guide

The `laserdesign` GUI walks you through a design in five steps: gain medium,
pump, resonator, operation and results. Each step shows a live preview that
updates as you type, and you can jump back to any step at any time. It uses
exactly the same models as the library, so a design built in the GUI gives
the same numbers as the equivalent script.

## Starting the GUI

```bash
python -m pip install -e ".[gui]"
laserdesign-gui                 # or: python -m laserdesign.gui
laserdesign-gui my_design.json  # open a saved design
```

The window opens with the CW Nd:YVO4 example loaded. **Examples** in the menu
bar loads any of the three worked designs from {doc}`examples/index`.
**File → New** starts a blank design, and **File → Save / Open** stores
designs as JSON files.

The step list on the left and the **Back / Next** buttons move between
steps. The status bar shows the design name, or what is wrong with the
current inputs.

## Tutorial: from a crystal to a Q-switched laser

This walk-through rebuilds the {doc}`Q-switched Nd:YAG example
<examples/qswitched_nd_yag>` from scratch. Start with **File → New**.

### Step 1: gain medium

![Step 1](gui/images/step1_gain_medium.png)

1. Choose **Nd:YAG** as the material. Set the doping to 1.0 at.% and the
   length to 8 mm.
2. The material properties box shows the database values. To use your
   supplier's data, type over any of them; the change is stored with the
   design as an override. **Reset to database values** undoes all overrides.
3. Below the box the page summarises what follows from these numbers: pump
   absorption coefficient, single-pass absorption, saturation fluence and
   the σ·τ product that sets the threshold.

### Step 2: pump

![Step 2](gui/images/step2_pump.png)

1. Enter 20 W, a 300 µm waist radius, M² = 80 and a waist 2 mm inside the
   crystal. For a fibre-coupled diode, M² ≈ π × fibre core radius × NA / λ.
   A 400 µm, 0.22 NA fibre at 808 nm gives about 170.
2. The plots show the pump caustic in the crystal and where the power is
   absorbed. The summary gives the absorption-weighted pump radius, which is
   the size that matters for threshold and thermal lensing, and the thermal
   focal length at full power.
3. If your diode's spectrum is broad, enter a measured **effective
   absorption** in /cm instead of relying on the narrow-band material value.

### Step 3: resonator

![Step 3 (shown for the mode-locked example)](gui/images/step3_resonator.png)

The table lists everything the beam meets going from end mirror 1 (normally
the HR-coated pumped face) to end mirror 2. Use the **+** buttons to insert
elements after the selected row, edit lengths, radii, fold angles and indices
directly in the table, and reorder with **Move up / down**. The gain crystal
row comes from step 1 and cannot be deleted.

For the Q-switched laser:

1. Leave end mirror 1 flat. Set end mirror 2 to −200 mm (a convex output
   coupler) by unticking **flat** and typing the radius.
2. After the crystal, add a 10 mm air gap, a medium of 25 mm and n = 1.45
   named "AO Q-switch", and a 40 mm air gap.

The upper plot shows the TEM00 mode along the cavity at full pump power in
both planes (they differ only with off-axis curved mirrors or Brewster
plates). The lower plot shows the stability parameter as the pump power, and
so the thermal lens, changes. The shaded band is the stable zone, and the
dotted line marks your operating point. The summary gives the mode-to-pump
size ratio in the crystal (aim for about 0.8 to 1 for TEM00 with good
efficiency) and the stable pump range.

A typical design loop is to adjust the gap and mirror radius until the
operating point sits comfortably inside the band and the mode ratio is right.

### Step 4: operation

![Step 4](gui/images/step4_operation.png)

1. Set the output coupler to 20 % and other losses to 2 % (the AOM's
   insertion loss is included here).
2. Choose **Q-switched** and a 10 kHz repetition rate.

For **SESAM mode-locked** operation, end mirror 2 is the SESAM. Enter its
saturation fluence and modulation depth here.

### Step 5: results

![Results for the Q-switched design](gui/images/step5_results_qswitch.png)

The table lists the operating point (absorbed power, heat load, thermal lens,
mode sizes), the CW performance and M² estimate, and the results for the
chosen operating mode. The plots depend on the mode:

- **CW:** output power and M² against pump power.
- **Q-switched:** pulse energy, pulse width and average power against
  repetition rate, with your rate marked and the CW power for comparison.
- **SESAM mode-locked:** QML margin and SESAM saturation against pump
  power, with warnings when the design would Q-switch mode lock, damage the
  SESAM or fail to self-start.

![Results for the CW example](gui/images/step5_results_cw.png)

![Results for the mode-locked example](gui/images/step5_results_modelock.png)

Go back to any step, change something, and return: the results are
recomputed from the current inputs.

## Design files

Designs are saved as readable JSON in SI units, for example:

```json
{
  "name": "Q-switched Nd:YAG, 20 W pump",
  "material": "nd:yag",
  "doping": 1.0,
  "crystal_length": 0.008,
  "pump_power": 20.0,
  "R1": "inf",
  "R2": -0.2,
  "elements": [
    {"type": "crystal"},
    {"type": "space", "length": 0.01},
    {"type": "medium", "length": 0.025, "n": 1.45, "name": "AO Q-switch"},
    {"type": "space", "length": 0.04}
  ],
  "output_coupling": 0.2,
  "mode": "qswitch",
  "rep_rate": 10000.0
}
```

The same file can be used from Python:

```python
from laserdesign.gui.spec import DesignSpec, build_laser

spec = DesignSpec.load("qs.json")
laser = build_laser(spec)                 # an EndPumpedLaser
print(laser.q_switched(spec.pump_power, spec.rep_rate)["energy"])
```

so you can sketch a design in the GUI and then script parameter scans on it.

## Limitations

- The GUI models end-pumped lasers with standing-wave resonators. Side-pumped
  rods and ring resonators are available in the library
  ({doc}`examples/koechner_side_pumped_rod`) but not yet in the GUI.
- The mode-locking step assumes the SESAM is end mirror 2.
- The results are only as accurate as the models; see the theory pages for
  their assumptions.

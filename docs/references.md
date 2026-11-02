# References

Textbooks used throughout:

- A. E. Siegman, *Lasers*, University Science Books (1986).
- P. W. Milonni and J. H. Eberly, *Laser Physics*, Wiley (2010).
- W. Koechner, *Solid-State Laser Engineering*, 6th ed., Springer (2006).

Papers cited for specific models:

- H. Kogelnik and T. Li, "Laser beams and resonators", Appl. Opt. 5, 1550 (1966).
- H. Kogelnik, E. P. Ippen, A. Dienes and C. V. Shank, "Astigmatically
  compensated cavities for CW dye lasers", IEEE JQE 8, 373 (1972).
- M. E. Innocenzi, H. T. Yura, C. L. Fincher and R. A. Fields, "Thermal
  modeling of continuous-wave end-pumped solid-state lasers", Appl. Phys. Lett.
  56, 1831 (1990).
- P. F. Moulton, "An investigation of the Co:MgF2 laser system", IEEE JQE 21,
  1582 (1985).
- W. P. Risk, "Modeling of longitudinally pumped solid-state lasers exhibiting
  reabsorption losses", JOSA B 5, 1412 (1988).
- T. Y. Fan and R. L. Byer, "Modeling and CW operation of a quasi-three-level
  946 nm Nd:YAG laser", IEEE JQE 23, 605 (1987).
- J. J. Degnan, "Theory of the optimally coupled Q-switched laser", IEEE JQE
  25, 214 (1989).
- H. A. Haus, "Mode-locking of lasers", IEEE JSTQE 6, 1173 (2000).
- F. X. Kärtner, I. D. Jung and U. Keller, "Soliton mode-locking with
  saturable absorbers", IEEE JSTQE 2, 540 (1996).
- C. Hönninger, R. Paschotta, F. Morier-Genoud, M. Moser and U. Keller,
  "Q-switching stability limits of continuous-wave passive mode locking",
  JOSA B 16, 46 (1999).
- R. Paschotta and U. Keller, "Passive mode locking with slow saturable
  absorbers", Appl. Phys. B 73, 653 (2001).
- A. E. Siegman, "Analysis of laser beam quality degradation caused by quartic
  phase aberrations", Appl. Opt. 32, 5893 (1993).
- ISO 11146, "Lasers and laser-related equipment: test methods for laser beam
  widths, divergence angles and beam propagation ratios".

## Where the tests come from

`tests/test_abcd.py` checks the resonator solver against Siegman ch. 19 to 21.
`tests/test_qswitch_modelocking.py` checks the Q-switch theory against direct
integration and the Siegman/Koechner extraction curve, and the AM mode-locking
formula against the Kuizenga-Siegman form. `tests/test_koechner.py` collects
checks based on Koechner's tables and formulas. Values marked "from memory" in
the tests were reproduced without the book at hand and should be verified
against it.

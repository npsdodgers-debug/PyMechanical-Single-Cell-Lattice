# PyMechanical-Single-Cell-Lattice

An automated simulation pipeline using Ansys PyMechanical to generate Frequency Response Function (FRF) datasets for a single-cell lattice structure. Active research project at Texas A&M University targeting AI-based structural health monitoring (SHM).

## Project Goal

Simulate healthy and damaged lattice configurations to build a labeled training dataset for an AI model capable of detecting structural defects from FRF data.

## Repository Structure

```
simulation/
    (simulation scripts — in progress)

plotting/
    plot_lattice_frf.py      — plots FRF from Mechanical probe export (.xls)
    compare_lattice_psv.py   — compares Mechanical simulation vs Polytec PSV experiment
    compare_two_psv.py       — compares two Polytec PSV experimental FRFs against each other
```

## Requirements

- Ansys Mechanical 2025 R2 (v252) with valid license
- Python 3.12+
- `ansys-mechanical-core==0.11.0`
- `matplotlib`, `numpy`, `pandas`, `scipy`, `pyuff`

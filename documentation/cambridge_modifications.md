# AMOP modifications to Qudi {#cambridge-mods}

This page provides a list of modifications by Cambridge to Qudi. Changes can
also be seen by comparing the branch amop-mods to the upstream master.

## Additions

### Stage control chain
- Add GUI & logic modules for controlling motorised x, y, z stages
- Add common interface PositionerInterface for hardware to connect to this chain
- Add hardware modules for ANC-300 and PI-C843 stage controllers

### Time-resolved PL
- Add hardware module for QuTAU and QuTAG time-tagging units
- Add histogram logic and GUI for displaying and saving histograms and time tags

### AOM laser control
- Add simple GUI and logic for controlling laser power via the NI-DAQ card, using
    an analogue input for a photodiode and output for an AOM.

### Fibre switch
- Add simple GUI for controlling a fibre switch connected to a digital output
    on the DAQ card.

## Unmerged changes to upstream Qudi

### Confocal GUI
- Add Center Cursor action to toolbar
- Modify saving so it doesn't block the GUI

### POI manager GUI
- Fix a bug that prevented tracking a POI if the POI name was changed during
    tracking
# Getting started {#get-started}

## Installation

Follow the [installation guide](@ref installation) to get Qudi set up on your
computer. The "Quick install using Miniconda" is the easiest thing to do.

## Modules

Qudi uses the concept of 'modules' to separate different functions that might
be useful on different setups. Modules come in three types: GUI, Logic and 
Hardware. On the manager screen that is displayed when Qudi starts up, you
can see these modules listed under three tabs (one for each type).

You can load a module by clicking its name in the manager. Any modules that it
depends on are also loaded; usually, you only need to click on the GUI you want
to use, and the required logic and hardware modules are loaded up automatically.

On its first start, Qudi will be  configured in a 'demo' mode, and will 
generate dummy data to show how each GUI is supposed to work - you can try loading some GUI modules to explore their features using this.

## Configuration

Qudi uses a configuration file to set it up for measurements. This file controls
which modules appear in the manager, how they are connected to each other, and
what settings are used to make them work with hardware.

The default configuration file `config/example/default.cfg` connects some
'dummy' hardware modules to the logic and GUIs, putting it in a demo mode that
is useful for testing without requiring actual hardware.

Instructions for configuring Qudi can be found in the [config file documentation](@ref #config-explanation).

## Using Jupyter Notebooks

One of the most powerful features of Qudi is its integration with Jupyter
notebooks, which allows custom or automatic experiments to be rapidly
developed and run side-by-side with the Qudi GUI.

Please see the [Jupyter setup](@ref jupyterkernel) page for setup instructions and notebook examples.

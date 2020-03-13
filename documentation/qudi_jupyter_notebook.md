# How to use the Qudi Jupyter Notebook {#jupyterkernel}

1. Install the Qudi Jupyter kernel

* Ensure that your Anaconda environment or Python installation has
  up-to-date dependencies
* In a terminal, go to the `core` folder in the `qudi` folder
* Eventually do `activate qudi` to activate the conda environment
* Do `python qudikernel.py install`
* This should tell you where the kernel specification was installed

2. Configure Qudi

* Ensure that your Qudi configuration file contains the following
entry or an equvalent configuration in the `global` section:

```yaml
  module_server:
    - address: 'localhost'
    - port: 12345
```

* Ensure that your Qudi configuration file contains the following 
entry in the `logic` section:

```yaml
    kernellogic:
        module.Class: 'jupyterkernel.kernellogic.QudiKernelLogic'
        remoteaccess: True
```

3. Start the Jupyter notebook server

* Run `activate qudi` to activate the conda environment
* Run `jupyter notebook` or an equivalent, when starting from the
Windows Start menu, be sure to pick the Jupyter notebook installed
into the Qudi environment
* Start Qudi with the configuration you checked before
* Now, the 'New' menu should have a 'Qudi' entry and in a notebook, 
the 'Kernel->Change kernel' menu should also have a qudi entry
* If anything goes wrong, check that your firewall does not block
the Qudi remote connections or the Jupyter notebook connections

## Creating a notebook

Start the Jupyter server as above.

When creating a notebook, you will need to pick 'Qudi' from the drop-down
list that appears under 'New', on the right-hand side of the notebook browser.

The resulting notebook will be running the Qudi notebook kernel. This means
that you can access attributes and methods of all loaded modules in Qudi. For example, running the following Python code will run a confocal xy scan,
return it as a Numpy array, and plot it.

```python
import time
import matplotlib.pyplot as plt

# Start xy scan
scannerlogic.start_scanning()

# Wait until scan completes: the module will be 'locked' until then.
while scannerlogic.module_state() == 'locked':
    time.sleep(0.1)

# Get confocal scan data
# Array slices available: 
# [:, :, 0]: Real X position at each point
# [:, :, 1]: Real Y position at each point
# [:, :, 2]: Real Z position at each point
# [:, :, 3]: First channel of counter data.
xy_image = scannerlogic.xy_image[:, :, 3]

# Plot it
plt.imshow(xy_image)
plt.show()
```

You should also notice that the confocal scan data is being updated in the GUI
at the same time.

Note that plotting works a bit differently compared to normal Jupyter notebooks,
because "magic commands" (e.g. `%matplotlib inline`) are not supported. Just
calling plt.show() will display plots in the Jupyter notebook.

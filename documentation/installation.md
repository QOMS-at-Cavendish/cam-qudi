# Installation        {#installation}

## Quick install using Miniconda

1. Download the latest version of [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
2. Install it, keeping any options as their defaults.
3. Download Qudi from either https://github.com/johnjarman/cam-qudi (with
    Cambridge mods) or https://github.com/Ulm-IQO/qudi (unmodified) and 
    extract all of its files to somewhere memorable (e.g. `C:\qudi`)
4. Open the Anaconda Prompt, which should have been installed by Miniconda.
    (Try searching the Start Menu on Windows)
5. Use the `cd` (change directory) command to set the current directory to the
    folder where you copied Qudi. E.g., type `cd C:\qudi` and press Enter.
6. Run `tools\install-python-modules-windows.bat`. This will set up a Conda
    environment with all the required packages for running Qudi.
7. Run `conda activate qudi` to activate this environment (you'll need to 
    do this each time you restart Anaconda Prompt)
8. Run `python start.py` to start up Qudi.

To make Qudi easy to start, you can also 
[create a desktop shortcut](@ref desktop-shortcut).

## Hardware driver installation

Qudi also needs appropriate drivers and libraries to communicate with hardware.

Please check the documentation pages for individual hardware modules for some
tips on finding appropriate drivers and software for specific pieces of hardware.

## More installation information

### Requirements

Qudi requires Python 3.6 or 3.7, and is not yet compatible with Python 3.8 due
to its use of a deprecated event loop for `pyzmq`. 
The 64-bit version of Python is also needed for compatibility with the widest
range of hardware DLLs.

A complete list of the Python modules depended on by Qudi can be found in
`requirements.txt`.

Qudi works with vanilla Python as well as Miniconda/Anaconda; if you prefer, 
you can install the required packages using 
`pip install -r requirements.txt`, optionally in a `venv`.

### Git

Qudi uses git as its version control system. If you want to keep up with
updates, or make any changes to Qudi, you will need Git.

Get Git for Windows from https://git-for-windows.github.io/

To make Qudi work with Git, you will need to run `git clone <repo_url>` instead of copying over Qudi's files by hand.

Replace `<repo_url>` with one of the following:

- For unmodified Qudi, use `https://github.com/Ulm-IQO/qudi.git`
- For the Cambridge version, use `https://github.com/johnjarman/cam-qudi.git`

#### Desktop shortcut {#desktop-shortcut}

You can create a Desktop shortcut to launch Qudi easily on your machine.

- On your Desktop, right click and go to ``New->Shortcut``
- For the location you need to copy the following target 
    - ` %windir%\System32\cmd.exe "/K" <path-to-activation-script> "<path-to-qudi-environment>"
     && cd "<path-to-qudi-directory>" && python "start.py" `
    - In order for the shortcut to work on every windows setup, you need to specify 3 things :
        - `<path-to-activation-script>` : the path to the Anaconda activate.bat file, for example
        `C:\ProgramData\Miniconda3\Scripts\activate.bat`.
        - `<path-to-qudi-environment>` : this can be found using command `conda info --envs` in a terminal.
        - `<path-to-qudi-directory>` : the path where Qudi's `start.py` can be found.  
- Click ``Next``
- Give the name you want fot the shortcut : ``Qudi``
- Click ``Finish``
- (Optional) Right click on the newly created shortcut and go to `Proprerties`
    - Click ``Change Icon...`` and browse for the ``artwork\logo\logo_qudi.ico`` logo

##### Troubleshooting

Please note, in Windows you cannot switch directly between partitions with cd (i.e. between C: and D:).
If Qudi's program is stored in another partition, you need to change the command to :
` %windir%\System32\cmd.exe "/K" <path-to-activation-script> "<path-to-qudi-environment>" && D:
     && cd "<path-to-qudi-directory-on-D-partition>" && python "start.py" `

## Linux installation

1. Install git using system package manager.

2. Do `git clone https://github.com/Ulm-IQO/qudi.git` .

3. Install a conda package manager.  [Miniconda](https://conda.io/miniconda.html) is nice and easy.

4. Install the qudi conda environment from `tools/conda-env-linx64-qt5.yml` .

5. Activate the qudi conda environment.

6. Change to the qudi code directory and run start.py using `./start.py` or `python3 start.py` or similar.

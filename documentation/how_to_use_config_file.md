# How to use and understand a config file  {#config-explanation}

The config file is used to set up Qudi to work with a particular set of
hardware in a particular setup or experiment.

Config files are stored in the `config` subdirectory, and have a `.cfg` extension.

They serve two purposes:

1. To define connections between modules
2. To specify configuration options for individual modules

The file is written in a language called YAML.

## Structure of a config file

There are four main parts of the config file: a global section, and three parts
corresponding to the three types of modules (gui, logic and hardware).

### The module sections (`hardware`, `logic` and `gui`)

Modules are configured here under one of these headings, depending on the type
of module.

There is no specific documentation page for many modules. However, there should be an example config section that is suitable for copying and pasting at the top of the Python file, that shows the available options and some suggested values.

For example, using the `hardware/PI_C843.py` stage driver and `hardware/xbox_controller.py` Xbox controller interface:

```yaml
hardware:
    pi_c843:
        module.Class: 'PI_C843.PI_C843'
        port: 1
        axes: {'x':1,'y':2,'z':3}

    xboxcontroller:
        module.Class: 'xbox_controller.XboxController'
```

We have placed this config under the `hardware:` heading because it is a hardware module; this tells Qudi to look for it in the `hardware` subdirectory and place it under the hardware tab. All hardware modules should be placed under this heading.

The next heading is `pi_c843`, which is a name for the module. Any name can be used here: it will appear in the GUI, and is also used to reference the module when connecting to it, but has no special significance.

The first definition is `module.Class: 'PI_C843.PI_C843'`. This defines the actual Python class that contains the module's functions. The first half of this is the name of the file containing the class (without the `.py` extension), and the second half is the name of the class. In this case, the file is `PI_C843.py` and the class is called `PI_C843`, so we specify `PI_C843.PI_C843`. Note that the class name and filename are not always the same.

The following definitions, `port:` and `axes:`, are configuration options for the module. You should refer to the module itself to find out what these do. Note that Python syntax is accepted here for passing lists and dicts as options.

The `xboxcontroller` module is included in the same way, but this time there are no config options to specify.

#### Connecting modules

Logic and GUI modules need connections to other modules to be useful. To connect to other modules, they provide named Connectors, and these can be connectd to modules of certain types that provide the correct Interface.

These connections are specified in the config file, so modules providing the same Interface can be interchanged (e.g. for different hardware that does the same job).

For example, here is the `logic` config section containing the `xboxlogic` and `stagecontrol_logic` modules:

```yaml
logic:
    xboxlogic:
        module.Class: 'xbox_logic.XboxLogic'
        connect:
            hardware: 'xboxcontroller'

    stagecontrollogic:
        module.Class: 'stagecontrol_logic.StagecontrolLogic'
        connect:
            stagehardware: 'pi_c843'
            xboxlogic: 'xboxlogic'
```

Each line in the `connect:` section specifies a module to connect. For example, the line

```yaml
stagehardware: 'pi_c843'
```

specifies that the module we called `pi_c843` earlier should be connected to the logic module's `stagehardware` connector. The names of the connectors are defined in the module.

Check the comments near the top of the Python file for the logic module to see what modules can be (or need to be) connected, and to find out the names of the connectors.

GUI modules are then specified and connected in a very similar way:

```yaml
gui:
    tray:
        module.Class: 'trayicon.TrayIcon'

    man:
        module.Class: 'manager.managergui.ManagerGui'

    stagecontrolgui:
        module.Class: 'stagecontrol.stagecontrolgui.StagecontrolGui'
        connect:
            stagecontrollogic: 'stagecontrollogic'
```

The `tray` and `man` modules provide the tray icon and manager GUI, and should be included in most Qudi config files.

`stagecontrolgui` is a GUI desgined to connect to the `stagecontrollogic` module, and provides a user interface to the functions in that module.

### The `global` section

This section configures the modules to load at startup; the IP address and port of the remote module server provided by Qudi; and the style used by the GUI. The startup modules are referred to by their names as they were configured
in the module sections. Here, we are loading the manager and the tray icon.

```yaml
global:
    startup: ['man', 'tray']

    module_server:
        address: 'localhost'
        port: 12345

    stylesheet: 'qdark.qss'
```

Usually, this section can be included as-is. If necessary, the IP address and port should be edited to point at a Qudi module server.

## Loading a config file

The config file can be specified from the Manager GUI. Click the 'open' icon in the toolbar, find the config file, and restart when prompted to load up the configuration.

Any errors encountered while loading the config will appear in the log at the bottom of the Manager window.

If everything has worked properly, the modules specified in the file will appear under the tabs in the left-hand pane of the Manager window.

#### Using `load.cfg`

The file `load.cfg` in the `config` directory can also be edited to specify which config file to use, as follows:

```yaml
configfile: config/file.cfg
```

Note that the value in `load.cfg` is updated whenever the config file is changed via the GUI.

### From the command line

Alternatively, the config file can be specified with the `-c` command line option:

```bash
> python start.py -c config/file.cfg
```

In this case, the value in `load.cfg` is ignored.

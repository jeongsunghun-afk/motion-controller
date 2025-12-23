# mcx_client_app Python Package

This package provides the main application logic for building Motorcortex client applications in Python. It enables robust communication, state management, and automation for Motorcortex-based robotic and industrial systems.

## Overview

The package provides two main classes for building Motorcortex client applications:

1. **`McxClientApp`** - Base class that runs actions in the main thread
2. **`McxClientAppThread`** - Derived class that runs actions in a separate thread

Both classes handle the complete lifecycle of a Motorcortex client application:

1. **Connection**: Establishes secure WebSocket connection with certificate-based authentication
2. **Engagement**: Commands the robot/system to the ENGAGED state
3. **Execution**: Runs your custom automation logic with start/stop signal monitoring
4. **Disengagement**: Safely returns the system to OFF state
5. **Disconnection**: Cleans up resources and closes connections

This pattern ensures safe operation by automatically handling state transitions and providing graceful shutdown on stop signals and keyboard interrupts (Ctrl+C).

## Features
- Two execution modes: main thread or separate thread
- Configurable via JSON or environment variable (`CONFIG_PATH`)
- Connect to Motorcortex servers using secure WebSocket and certificate authentication
- Monitor and control robot/system state via parameter tree
- Send state commands and handle start/stop logic
- Run custom automation routines with safe engagement/disengagement
- Support for external start/stop control via parameter subscription
- Extensible via inheritance - override methods for custom behavior
- Built-in stop signal handling for safe interruption of running operations
- Graceful keyboard interrupt (Ctrl+C) handling with proper cleanup
- Thread-safe value container for cross-thread communication

## Configuration and Options

### `McxClientAppOptions`
- All configuration is handled via the `McxClientAppOptions` class.
- You can load options from a JSON file using `from_json()`, or set the `CONFIG_PATH` environment variable to load config at runtime.
- All keys in the config file are set as attributes, including those only used by subclasses.
- Enum values (like `run_during_states`) should be specified as strings in the config (e.g., `"ENGAGED_S"`), and are automatically converted to enum objects.

**Example config (`dataLogger_config.json`):**
```json
{
  "login": "admin",
  "password": "vectioneer",
  "target_url": "wss://192.168.2.100",
  "log_file": "data/robot_data.csv",
  "paths_to_log": [
    "root/ManipulatorControl/jointPositionsActual",
    "root/ManipulatorControl/manipulatorToolPoseActual"
  ],
  "divider": 10,
  "batch_size": 100,
  "save_interval": 5,
  "run_during_states": ["ENGAGED_S"]
}
```

**Enum Handling:**  

For `run_during_states` in the config, use the enum names as strings. The options loader will convert them to enum objects.

**Child Class Inheritance Note:**

When inheriting from this class, ensure to call super().__init__(**kwargs) after initialising the class parameters. For example,

``` python
class CustomOptions(McxClientAppOptions):
    def __init__(self, custom_param: str = "default", **kwargs):
        self.custom_param = custom_param
        super().__init__(**kwargs)
```

## Main Classes

### `McxClientAppOptions`
Dataclass for configuration options:
- `login`: Username for Motorcortex server
- `password`: Password for Motorcortex server
- `target_url`: WebSocket URL (default: `wss://localhost`)
- `cert`: Path to SSL certificate (default: `mcx.cert.crt`)
- `statecmd_param`: Parameter path for state commands (default: `root/Logic/stateCommand`)
- `state_param`: Parameter path for reading state (default: `root/Logic/state`)
- `start_stop_param`: Optional parameter path for start/stop control
- Any additional keys in your config file are set as attributes

### `McxClientApp`
Base client class that runs the `iterate()` method in the main thread. Use this when you want simple, sequential execution without threading complexity.

### `McxClientAppThread`
Derived class that runs the `iterate()` method in a separate thread while the main thread monitors start/stop signals. Use this when you need concurrent execution or when actions should run independently of signal monitoring.

### `ThreadSafeValue[T]`
Generic thread-safe single-value container for cross-thread communication.

## Usage Examples

### Example: Data Logger App

```python
from src.mcx_client_app import McxClientApp, McxClientAppOptions

class DataLoggerOptions(McxClientAppOptions):
    pass  # All config keys are set as attributes

class DataLoggerApp(McxClientApp):
    def iterate(self):
        # Your logging logic here
        self.wait(1)

if __name__ == "__main__":
    import os
    config_path = os.path.join(os.path.dirname(__file__), 'examples/dataLogger_config.json')
    options = DataLoggerOptions.from_json(config_path)
    app = DataLoggerApp(options)
    app.run()
```

### Example: Enum Handling

```python
# In your config: "run_during_states": ["ENGAGED_S"]
# In your app:
if State.ENGAGED_S in options.run_during_states:
    print("Will run when engaged")
```

## Advanced Patterns

- See the original README for patterns on lifecycle hooks, start/stop control, exception handling, and threading.

## Troubleshooting

- If you see `'str' object has no attribute 'value'`, ensure your config uses enum names as strings and that your options loader converts them to enum objects.
- If you get import errors, do not run modules directly; use `python -m ...` or run your main script from the project root.

## Import Statement

```python
from mcx_client_app import McxClientApp, McxClientAppThread, McxClientAppOptions, StopSignal, ThreadSafeValue
```

---

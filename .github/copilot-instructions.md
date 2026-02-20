# Motorcortex Client Application (MCX-Client-App) - AI Coding Instructions

**CRITICAL: READ THESE INSTRUCTIONS COMPLETELY BEFORE GENERATING ANY CODE**

This document provides comprehensive servicesdance for AI agents to create, modify, and understand Motorcortex client applications. These are Python applications that connect to a Motorcortex control system to monitor parameters, control robots, automate workflows, and integrate with external systems.

---

## Table of Contents

1. [How Client Apps Interact with Motorcortex](#how-client-apps-interact-with-motorcortex)
2. [Project Overview](#project-overview)
3. [Core Architecture](#core-architecture)
4. [Creating an MCX-Client-App](#creating-an-mcx-client-app)
5. [Configuration System](#configuration-system)
6. [Thread vs Non-Thread Usage](#thread-vs-non-thread-usage)
7. [Subscription Patterns](#subscription-patterns)
8. [Error Handler - Triggering System Errors](#error-handler---triggering-system-errors)
9. [Keep iterate() Clean - Best Practices](#keep-iterate-clean---best-practices)
10. [Complete Working Examples](#complete-working-examples)
11. [API Reference](#api-reference)
12. [Coding Conventions](#coding-conventions)

---

## How Client Apps Interact with Motorcortex

MCX-Client-Apps connect to a **Motorcortex server on a Target** via WebSocket (e.g., `wss://192.168.1.100`) and interact with the **parameter tree** - a hierarchical structure with existing Motorcortex parameters (like `root/AGVControl/actualVelocityLocal`, `root/Sensors/Temperature`) and service-specific parameters.

**Operations:** Read with `self.req.getParameter()`, write with `self.req.setParameter()`, subscribe for real-time updates with `self.sub.subscribe()`.

### Adding Custom Service Parameters

**CRITICAL:** All custom client-app parameters are automatically placed under `root/Services/{ServiceName}/serviceParameters/` when defined in the `Parameters` section of `services_config.json`.

**IMPORTANT:** Only add parameters for **client-app-specific** controls (buttons, counters, settings). If a parameter path is provided like `root/AGVControl/actualVelocityLocal` or `root/Sensors/Temperature`, these **already exist** in the Motorcortex application's parameter tree - just read/subscribe to them directly. Do NOT document them as "required parameters".

When your app needs **new service parameters**, define them in the `Parameters` section of your service configuration in `services_config.json`. These parameters will be automatically placed under `root/Services/{ServiceName}/serviceParameters/` in the parameter tree.

### Service Parameters vs McxClientAppConfiguration

**Critical distinction:**

**Service Parameters (in parameter tree at `root/Services/{ServiceName}/serviceParameters/`):**

- ✅ Use for values that **change during runtime** (buttons, setpoints, thresholds that users adjust)
- ✅ Can be modified via DESK tool or other clients while app is running
- ✅ Access with `self.req.getParameter(f"{self.options.get_service_parameter_path}/...")` or subscriptions
- ✅ Changes take effect immediately
- ✅ Defined in the `Parameters` section of `services_config.json`
- Example: `{"Name": "MaxSpeed", "Type": "double, input"}` under service parameters

**McxClientAppConfiguration (in Config section):**

- ✅ Use for values that are **set once at startup** and remain constant
- ✅ Cannot be changed while app is running (requires restart)
- ✅ Access via `self.options.connection_timeout`
- ✅ Simpler, faster access (no network calls)
- ✅ Defined in the `Config` section of `services_config.json`
- Example: `{"connection_timeout": 30}` in Config section

**Decision Guide:**

```python
# ❌ WRONG: Static configuration in service parameters when it never changes at runtime
# (Adds unnecessary complexity and network overhead)
# In services_config.json Parameters section:
{
  "Name": "Parameters",
  "Children": [
    {"Name": "LogFilePath", "Type": "string, parameter", "Value": "/var/log/app.log"}
  ]
}
# Then reading: self.req.getParameter(f"{self.options.get_service_parameter_path}/LogFilePath")

# ✅ CORRECT: Static configuration in Config section
# In services_config.json Config section: {"log_file_path": "/var/log/app.log", "connection_timeout": 30}
# Access: self.options.log_file_path

# ✅ CORRECT: Runtime-adjustable parameter in service parameters
# In services_config.json Parameters section:
{"Name": "VelocityThresholds", "Type": "double[6], parameter", "Value": [0.2, 0.4, 0.6, 0.8, 1.0, 1.5]}
# Access: self.req.getParameter(f"{self.options.get_service_parameter_path}/VelocityThresholds")
# User can change thresholds in DESK tool, app responds immediately via subscription
```

**Required Service Configuration Format:**

Services are configured in `services_config.json` with the following structure:

```json
{
  "Services": [
    {
      "Name": "RobotController",
      "Enabled": true,
      "Config": {
        "login": "admin",
        "password": "your_password",
        "target_url": "wss://192.168.1.100",
        "autoStart": true
      },
      "Parameters": {
        "Version": "1.0",
        "Children": [
          {
            "Name": "userParameters",
            "Children": [
              {
                "Name": "StartButton",
                "Type": "bool, input",
                "Value": 0
              },
              {
                "Name": "Counter",
                "Type": "int, parameter_volatile",
                "Value": 0
              }
            ]
          }
        ]
      },
      "Watchdog": {
        "Enabled": true,
        "Disabled": false,
        "high": 1000000,
        "tooHigh": 5000000
      }
    }
  ]
}
```

**Service Configuration Fields:**

- `Name`: Service name (used in parameter tree as `root/Services/{Name}`)
- `Enabled`: Whether service is enabled
- `Config`: Runtime configuration (login, password, target_url, autoStart, custom fields) - access via `self.options.field_name`
- `Parameters`: Service-specific parameters (placed under `root/Services/{Name}/serviceParameters/`) - access via `self.options.get_service_parameter_path`
- `Watchdog`: Watchdog settings (enabled, thresholds in microseconds)

**Application Code:**

```python
"""
MCX-Client-App: Robot Controller
"""

import logging
from src.mcx_client_app import McxClientApp, McxClientAppConfiguration

class RobotController(McxClientApp):
    def __init__(self, options: McxClientAppConfiguration):
        super().__init__(options)

    def iterate(self):
        # Access service parameters via self.options.get_service_parameter_path
        button = self.req.getParameter(f"{self.options.get_service_parameter_path}/StartButton").get().value[0]
        self.req.setParameter(f"{self.options.get_service_parameter_path}/Counter", 42).get()
        self.wait(1.0)

if __name__ == "__main__":
    config = McxClientAppConfiguration(name="RobotController")
    config.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/services_config.json",
        non_deployed_config="services_config.json"
    )
    config.load_config()
    app = RobotController(config)
    app.run()
```

**Note:** Replace `"services/RobotController"` with your actual client app name for UserParameters organization, and use `"robot_controller.json"` (lowercase with underscores) as the config filename in the portal.

### Parameter Types Reference

Parameter types follow the format: `<type>[array_size], <access_level>`

**Base Types:** `bool`, `int`, `float`, `double`, `string`

**Access Levels (from Target's perspective):**

- **`input`**: Writable from client apps - client **writes**, Target **reads** (buttons, commands, setpoints that control the Target)
- **`output`**: Read-only from client apps - Target **writes**, client **reads** (sensor data, status values from Target)
- **`parameter`**: Configuration values (writable but typically set once during setup)
- **`parameter_volatile`**: **RECOMMENDED for client app outputs** - Values that change frequently at runtime, written by client apps and read by other components

**CRITICAL:** Access levels are from the **Target's point of view**, not the client app:

- If your client app **outputs a value** to the tree → use `parameter_volatile` (optimized for frequent updates from client)
- If your client app **reads a value** from the tree → use `output` (Target outputs data to client)
- For buttons/commands that control the Target → use `input` (Target receives input from client)

**Client Apps Can Only Write To:**

- ✅ `input` parameters - Client can call `self.req.setParameter()`
- ✅ `parameter` parameters - Client can call `self.req.setParameter()`
- ✅ `parameter_volatile` parameters - Client can call `self.req.setParameter()` (RECOMMENDED for client outputs)
- ❌ `output` parameters - **CANNOT** write! These are read-only from client perspective

**Common Mistake:**

```python
# ❌ WRONG: Declaring client app output as "output" type
{"Name": "SafetyZone", "Type": "int, output", "Value": 0}
self.req.setParameter("root/.../SafetyZone", zone).get()  # FAILS! Can't write to output

# ✅ CORRECT: Client app output should be "parameter_volatile" type (optimized for client writes)
{"Name": "SafetyZone", "Type": "int, parameter_volatile", "Value": 0}
self.req.setParameter("root/.../SafetyZone", zone).get()  # Works! Best performance
```

**Array Syntax:** Add `[N]` for arrays (e.g., `double[5], input`)

**Examples:**

- `bool, input` → Client writes, Target reads: Button press `0` or `1`
- `int[3], input` → Client writes array: `[1, 2, 3]`
- `double, output` → Target writes, client reads: Sensor value `42.5`
- `string, parameter` → Configuration: `"default_name"`
- `int, parameter_volatile` → Client app output that updates frequently: Counter value `42`

### Best Practices

✅ **DO:**

- Document required parameters in file docstring
- Use descriptive names, organize hierarchically under `UserParameters`
- **Use `parameter_volatile` type for client app outputs** (data that changes frequently, written by client)
- **Use `input` type for control commands** (buttons, commands that trigger actions on Target)
- **Use `output` type for Target data** (data flowing FROM Target TO client)
- **Group related parameters as arrays** instead of separate entries:

  ```json
  // ❌ BAD: Multiple separate threshold parameters
  {"Name": "Zone1Threshold", "Type": "double, parameter", "Value": 0.2}
  {"Name": "Zone2Threshold", "Type": "double, parameter", "Value": 0.4}

  // ✅ GOOD: Single array parameter
  {"Name": "ZoneThresholds", "Type": "double[6], parameter", "Value": [0.2, 0.4, 0.6, 0.8, 1.0, 1.5]}
  ```

❌ **DON'T:**

- Assume parameters exist, use generic names like `param1`
- **Create custom parameters directly under `root/`** - ALL custom params MUST be under `root/UserParameters/`
- Use `output` type for values your client app writes (use `parameter_volatile` instead)
- Use `input` for frequently changing client outputs (use `parameter_volatile` for better performance)
- Try to call `setParameter()` on `output` type parameters (will fail)

### Accessing Parameters in Code

**Service parameters** are automatically scoped to your service and accessed via `self.options.get_service_parameter_path`:

```python
class MyApp(McxClientApp):
    def iterate(self):
        # ✅ CORRECT: Access service parameters using get_service_parameter_path
        button = self.req.getParameter(f"{self.options.get_service_parameter_path}/StartButton").get().value[0]
        self.req.setParameter(f"{self.options.get_service_parameter_path}/Counter", 42).get()

        # ✅ CORRECT: Access existing Motorcortex parameters directly
        velocity = self.req.getParameter("root/AGVControl/actualVelocityLocal").get().value[0]
```

❌ **WRONG - Hardcoded service parameter paths:**

```python
def iterate(self):
    # ❌ Hardcoded paths - don't do this!
    value = self.req.getParameter("root/Services/MyApp/serviceParameters/userParameters/StartButton").get().value[0]
```

**Parameter Access Patterns:**

```python
# Read service parameter (any type)
value = self.req.getParameter(f"{self.options.get_service_parameter_path}/StartButton").get().value[0]

# Write service parameter (only works on "input" and "parameter" types!)
self.req.setParameter(f"{self.options.get_service_parameter_path}/Counter", 42).get()  # ✅ OK if Counter is "input"

# Array parameter
speeds = self.req.getParameter(f"{self.options.get_service_parameter_path}/Speeds").get().value
# Returns: [0.1, 0.2, 0.3, ...]

# Subscribe for real-time updates
self.sub.subscribe(
    [f"{self.options.get_service_parameter_path}/StartButton"],
    group_alias="btn"
).get().notify(self._onButtonChange)
```

**Why This Matters:**

- ✅ Parameters automatically scoped to your service
- ✅ No naming conflicts with other services
- ✅ Cleaner, more maintainable code
- ✅ Follows framework best practices

### Example: Complete Documentation

```python
"""
MCX-Client-App: Pick and Place Robot Controller

REQUIRED SERVICE CONFIGURATION:
Add this service to services_config.json:
{
  "Name": "PickPlaceController",
  "Enabled": true,
  "Parameters": {
    "Version": "1.0",
    "Children": [
      {
        "Name": "userParameters",
        "Children": [
          {
            "Name": "StartButton",
            "Type": "bool, input",
            "Value": 0
          },
          {
            "Name": "ResetButton",
            "Type": "bool, input",
            "Value": 0
          },
          {
            "Name": "CycleCounter",
            "Type": "int, parameter_volatile",
            "Value": 0
          }
        ]
      }
    ]
  }
}

ACCESS IN CODE:
# Read:      self.req.getParameter(f"{self.options.get_service_parameter_path}/StartButton").get().value[0]
# Write:     self.req.setParameter(f"{self.options.get_service_parameter_path}/CycleCounter", 42).get()
# Subscribe: self.sub.subscribe([f"{self.options.get_service_parameter_path}/StartButton"], "alias").get().notify(callback)
"""
```

---

## Project Overview

The MCX-Client-App template provides a framework for creating Python applications that:

- Connect to Motorcortex servers via WebSocket (using `motorcortex-python` library)
- Control robots using the `robot_control` API
- Monitor and set parameters in real-time
- Execute automated workflows with start/stop control
- Deploy as Debian packages on MCX-RTOS systems

**Key Files:**

- [mcx-client-app.py](../mcx-client-app.py) - Main template file (modify this)
- [src/mcx_client_app/McxClientApp.py](../src/mcx_client_app/McxClientApp.py) - Base classes (do not modify)
- [src/mcx_client_app/McxClientAppConfiguration.py](../src/mcx_client_app/McxClientAppConfiguration.py) - Configuration class (extend if needed)
- [config.json](../config.json) - Runtime configuration (connection settings, custom config)
- [service_config.json](../service_config.json) - Service/deployment configuration (package name, script name)

**CRITICAL: Always Update Configuration Files When Making Changes**

When you modify the project structure, **immediately update the relevant configuration files**:

1. **Rename/create Python script** → Update `service_config.json`:

   ```json
   {
     "PACKAGE_NAME": "my-client-app",
     "PYTHON_SCRIPT": "my_new_script.py", // ← Update when renaming mcx-client-app.py
     "PYTHON_MODULES": "src",
     "DEBUG_ON": false
   }
   ```

2. **Add custom configuration fields** → Update `config.json`:

   ```json
   {
     "login": "",
     "password": "",
     "target_url": "wss://192.168.1.100",
     "cert": "mcx.cert.crt",
     "my_custom_field": 123 // ← Add your custom fields here
   }
   ```

3. **Change class name** → Update `if __name__ == "__main__":` block:
   ```python
   if __name__ == "__main__":
       client_options = CustomMcxClientAppConfiguration.from_json("config.json")
       app = RobotController(client_options)  # ← Update this line
       app.run()
   ```

**Common scenarios requiring config updates:**

- Creating a new main script file → Update `PYTHON_SCRIPT` in service_config.json
- Changing package name for deployment → Update `PACKAGE_NAME` in service_config.json
- Adding custom configuration options → Add fields to config.json AND custom Configuration class
- Renaming the main Python file → Update `PYTHON_SCRIPT` in service_config.json

---

## Core Architecture

### Base Classes

**`McxClientApp`** - Main thread execution

```python
from src.mcx_client_app import McxClientApp, McxClientAppConfiguration

class MyApp(McxClientApp):
    def iterate(self) -> None:
        """Runs in main thread, blocking execution"""
        pass
```

**`McxClientAppThread`** - Separate thread execution

```python
from src.mcx_client_app import McxClientAppThread, McxClientAppConfiguration

class MyApp(McxClientAppThread):
    def iterate(self) -> None:
        """Runs in separate thread, main thread monitors start/stop"""
        pass
```

### Lifecycle Methods

Override these methods in your subclass:

1. **`__init__(self, options: McxClientAppConfiguration)`** - Initialize instance variables
2. **`startOp(self) -> None`** - Called after connection, before iterate starts (setup subscriptions here)
3. **`iterate(self) -> None`** - Main application logic (called repeatedly while running)
4. **`onExit(self) -> None`** - Cleanup before disconnect (unsubscribe, save data, etc.)

### Inherited Attributes (Available in Your Class)

```python
self.req                # motorcortex.Request - for setting/getting parameters
self.sub                # motorcortex.Subscription - for subscribing to parameters
self.parameter_tree     # motorcortex.ParameterTree - parameter structure
self.motorcortex_types  # motorcortex.MessageTypes - message type definitions
self.options            # McxClientAppConfiguration - your configuration
self.running            # ThreadSafeValue[bool] - current running state
self.watchdog           # McxWatchdog - watchdog manager (automatically kept alive)
self.errorHandler       # McxErrorHandler - error handler for triggering system errors
```

**CRITICAL - Watchdog Best Practices:**

The watchdog is **automatically managed** and kept alive when you use `self.wait()` or `self.wait_for()` methods.

✅ **DO:**

- Use `self.wait()` for delays - keeps watchdog alive automatically
- Use `self.wait_for()` for waiting on conditions - keeps watchdog alive
- Keep `iterate()` free of long blocking operations

❌ **DON'T:**

- Use `time.sleep()` - watchdog will timeout!
- Block in `iterate()` without calling `self.wait()`
- Perform long computations without periodic `self.wait()` calls

**Example - Correct Watchdog Usage:**

```python
def iterate(self):
    # ✅ CORRECT: Uses self.wait() which keeps watchdog alive
    self.process_data()
    self.wait(1.0)  # Automatically keeps watchdog alive

    # ✅ CORRECT: For long operations, add periodic waits
    for i in range(1000):
        self.heavy_computation(i)
        if i % 100 == 0:
            self.wait(0.01)  # Keep watchdog alive during long loop

# ❌ WRONG: time.sleep() doesn't keep watchdog alive
def iterate(self):
    import time
    time.sleep(1.0)  # WATCHDOG WILL TIMEOUT!
```

**Error Handler Usage:**

The `self.errorHandler` provides methods to trigger system-level errors at different severity levels:

```python
# In startOp(), optionally configure error handler
def startOp(self):
    self.errorHandler.set_subsystem_id(1)  # Optional: identify subsystem
    self.errorHandler.set_acknowledge_callback(self.on_error_acknowledged)

# Trigger errors at different levels
def iterate(self):
    if critical_condition:
        self.errorHandler.trigger_emergency_stop(error_code=5001)  # Most severe
    elif shutdown_needed:
        self.errorHandler.trigger_shutdown(error_code=4001)
    elif forced_disengage:
        self.errorHandler.trigger_forced_disengage(error_code=3001)
    elif warning_condition:
        self.errorHandler.trigger_warning(error_code=1001)  # Least severe

# Optional callback when error is acknowledged
def on_error_acknowledged(self):
    logging.info("Error was acknowledged by user")
    # Reset your application state here
```

**Error Levels (from MotorcortexErrorLevel enum):**

- `ERROR_LEVEL_UNDEFINED` (0): Undefined
- `INFO` (1): Information message
- `WARNING` (2): Warning - does not stop system
- `FORCED_DISENGAGE` (3): Graceful software stop
- `SHUTDOWN` (4): Abrupt software stop
- `EMERGENCY_STOP` (5): Abrupt software and hardware stop

**IMPORTANT:** To check subscription status, import `motorcortex.OK` directly:

```python
import motorcortex

# ✅ CORRECT: Use motorcortex.OK (module-level constant)
if result and result.status == motorcortex.OK:
    subscription.notify(callback)

# ❌ WRONG: self.motorcortex_types.OK does not exist
if result and result.status == self.motorcortex_types.OK:  # AttributeError!
```

### Inherited Methods (Available in Your Class)

```python
self.wait(timeout: float = 30, testinterval: float = 0.2,
          keep_watchdog: bool = True, block_stop_signal: bool = False) -> bool
# Wait for timeout seconds, checking for stop signal. Raises StopSignal when stopped.
# keep_watchdog: If True (default), automatically keeps watchdog alive during wait
# block_stop_signal: If True, ignore stop signals during this wait

self.wait_for(param: str, value: object, index: int = 0, timeout: float = 30,
              testinterval: float = 0.2, operat: str = "==",
              keep_watchdog: bool = True, block_stop_signal: bool = False) -> bool
# Wait for parameter to meet condition. Raises StopSignal when stopped.
# Operators: "==", "!=", "<", "<=", ">", ">=", "in"
# keep_watchdog: If True (default), automatically keeps watchdog alive while waiting
# block_stop_signal: If True, ignore stop signals during this wait

self.reset() -> None
# Set running flag to False (stops the iterate loop)
```

**Note:** Both `wait()` and `wait_for()` automatically keep the watchdog alive by default (`keep_watchdog=True`). This ensures your application doesn't timeout during normal operations.

---

## Creating an MCX-Client-App

### Step 1: Define Your Custom Configuration (Optional)

Only create a custom configuration if you need additional parameters beyond the defaults.

```python
from src.mcx_client_app import McxClientAppConfiguration

class MyAppConfiguration(McxClientAppConfiguration):
    """
    Custom configuration with additional parameters.

    Attributes:
        speed (float): Movement speed in m/s.
        cycle_count (int): Number of cycles to execute.
    """
    def __init__(self, speed: float = 0.5, cycle_count: int = 10, **kwargs):
        # Set custom attributes BEFORE calling super().__init__()
        self.speed = speed
        self.cycle_count = cycle_count
        # Always call super().__init__() LAST with **kwargs
        super().__init__(**kwargs)
```

**Update services_config.json with your service configuration:**

```json
{
  "Services": [
    {
      "Name": "MyApp",
      "Enabled": true,
      "Config": {
        "login": "admin",
        "password": "password",
        "target_url": "wss://192.168.1.100",
        "autoStart": true,
        "speed": 0.8,
        "cycle_count": 20
      },
      "Watchdog": {
        "Enabled": true,
        "Disabled": false,
        "high": 1000000,
        "tooHigh": 5000000
      }
    }
  ]
}
```

**Important Configuration Parameters:**

- `autoStart`: If `true`, app starts immediately. If `false`, waits for `enableService` parameter
- `Watchdog.Enabled`: Enable watchdog monitoring (recommended: true)
- `Watchdog.high`: Warning threshold in microseconds
- `Watchdog.tooHigh`: Error threshold in microseconds

### Step 2: Create Your Application Class

```python
from src.mcx_client_app import McxClientApp
import logging

class MyApp(McxClientApp):
    """
    Brief description of what this application does.
    """
    def __init__(self, options: MyAppConfiguration):
        super().__init__(options)
        # Initialize instance variables here
        self.counter = 0
        self.my_subscription = None
        logging.info("MyApp initialized.")

    def startOp(self) -> None:
        """
        Setup subscriptions and initialize parameters after connection.
        This runs once when the application connects to Motorcortex.
        """
        # Configure error handler (optional)
        self.errorHandler.set_subsystem_id(1)
        self.errorHandler.set_acknowledge_callback(self.on_error_acknowledged)

        # Set initial parameter values using service parameter path
        try:
            self.req.setParameter(f"{self.options.get_service_parameter_path}/Counter", 0).get()
            logging.info("Counter parameter initialized.")
        except Exception as e:
            logging.error(f"Failed to initialize counter: {e}")

        # Setup subscriptions (see Subscription Patterns section)
        self._setupSubscriptions()

    def iterate(self) -> None:
        """
        Main application logic - called repeatedly while running.
        Keep this method clean and focused (see Best Practices section).

        CRITICAL: Use self.wait() instead of time.sleep() to keep watchdog alive!
        """
        # Your main logic here
        self.counter += 1
        logging.info(f"Iteration {self.counter}")

        # ✅ CORRECT: Use self.wait() - automatically keeps watchdog alive
        self.wait(1.0)  # Wait 1 second

    def on_error_acknowledged(self) -> None:
        """
        Called when user acknowledges an error (optional).
        """
        logging.info("Error acknowledged by user")
        # Reset application state here

    def onExit(self) -> None:
        """
        Cleanup before disconnecting.
        """
        # Unsubscribe from subscriptions
        if self.my_subscription:
            self.my_subscription.unsubscribe()

        logging.info(f"Exiting after {self.counter} iterations.")

    def _setupSubscriptions(self) -> None:
        """
        Private helper method to setup subscriptions.
        Keeps startOp() clean.
        """
        pass  # Implementation in Subscription Patterns section

# Run the application
if __name__ == "__main__":
    config = MyAppConfiguration.from_json("config.json")
    app = MyApp(config)
    app.run()
```

### Step 3: Configure and Run

**Minimal services_config.json:**

```json
{
  "Services": [
    {
      "Name": "MyApp",
      "Enabled": true,
      "Config": {
        "login": "admin",
        "password": "password",
        "target_url": "wss://localhost",
        "autoStart": true
      },
      "Watchdog": {
        "Enabled": true,
        "Disabled": false,
        "high": 1000000,
        "tooHigh": 5000000
      }
    }
  ]
}
```

**Main block:**

```python
if __name__ == "__main__":
    config = MyAppConfiguration(name="MyApp")
    config.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/services_config.json",
        non_deployed_config="services_config.json"
    )
    config.load_config()
    app = MyApp(config)
    app.run()
```

**Run locally:**

```bash
python3 mcx-client-app.py
```

---

## Configuration System

### Built-in Configuration Parameters

The `McxClientAppConfiguration` class provides these built-in parameters:

```python
McxClientAppConfiguration(
    # Connection settings
    login: str | None = None,              # Username for authentication
    password: str | None = None,            # Password for authentication
    target_url: str = "wss://localhost",    # WebSocket URL (local development)
    target_url_deployed: str = "wss://localhost",  # URL when deployed
    cert: str = "mcx.cert.crt",            # SSL certificate (local)
    cert_deployed: str = "/etc/ssl/certs/mcx.cert.pem",  # Certificate (deployed)

    # State management
    statecmd_param: str | None = "root/Logic/stateCommand",  # State command parameter
    state_param: str | None = "root/Logic/state",            # Current state parameter
    run_during_states: list = None,        # List of State enums when iterate() can run

    # Start/stop control
    start_stop_param: str | None = None,   # Parameter to monitor for start/stop (e.g., button)
)
```

### Automatic Deployment Detection

The configuration automatically detects deployment via `CONFIG_PATH` environment variable:

- **Local development**: Uses `target_url` and `cert`
- **Deployed**: Uses `target_url_deployed` and `cert_deployed`, loads from `CONFIG_PATH`

### Using State-Based Execution

Control when `iterate()` runs based on Motorcortex system state:

```python
from src.mcx_client_app import State

config = MyAppConfiguration(
    target_url="wss://192.168.1.100",
    run_during_states=[State.ENGAGED_S, State.IDLE_S],  # Only run in these states
)
```

If `run_during_states` is empty or `None`, the app runs in any state.

### Using Start/Stop Parameters

The framework automatically manages service enable/disable via the `enableService` parameter under `root/Services/{ServiceName}/enableService`.

To control when your app runs:

- Set `autoStart: true` in Config → app starts immediately when service is enabled
- Set `autoStart: false` in Config → app waits for `enableService` parameter to be set to 1

```python
# In services_config.json:
{
  "Config": {
    "autoStart": false  # Wait for manual enable
  }
}
```

---

## Thread vs Non-Thread Usage

### Use `McxClientApp` (Main Thread) When:

✅ **Simple sequential workflows**

```python
class SequentialApp(McxClientApp):
    def iterate(self):
        self.step1()
        self.wait(1)
        self.step2()
        self.wait(1)
```

✅ **Direct control needed** - You want the main thread to execute your logic
✅ **Simpler debugging** - Single-threaded execution is easier to trace
✅ **No concurrent operations** - No need for parallel monitoring

**Behavior:**

- `iterate()` runs in main thread
- Stop signal checked in `wait()` and `wait_for()` calls
- Blocking execution

### Use `McxClientAppThread` (Separate Thread) When:

✅ **Long-running operations** that should be independently stoppable

```python
class LongRunningApp(McxClientAppThread):
    def iterate(self):
        # Long computation or operation
        for i in range(1000):
            self.process_data(i)
            if not self.running.get():  # Check manually in loops
                break
```

✅ **Independent monitoring** - Main thread monitors start/stop while iterate() runs
✅ **Responsive stopping** - Need immediate response to stop signals without waiting for iterate() to complete

**Behavior:**

- `iterate()` runs in separate daemon thread
- Main thread monitors `running` state independently
- Thread stops when `running` becomes `False`

**IMPORTANT:** When using `McxClientAppThread`, check `self.running.get()` in long loops:

```python
def iterate(self):
    while self.running.get():  # Check running state
        # Do work
        self.wait(0.1)
```

### Decision Matrix

| Scenario                     | Use                  | Reason                     |
| ---------------------------- | -------------------- | -------------------------- |
| Sequential steps with waits  | `McxClientApp`       | Simple, clear flow         |
| Robot motion programs        | `McxClientApp`       | Sequential motion commands |
| Data logging every N seconds | `McxClientApp`       | Simple periodic task       |
| Long computation             | `McxClientAppThread` | Can stop mid-computation   |
| Real-time monitoring         | `McxClientAppThread` | Independent monitoring     |
| Complex state machines       | `McxClientApp`       | Easier to debug            |

**Default recommendation:** Start with `McxClientApp` unless you have a specific need for threading.

---

## Subscription Patterns

Subscriptions allow you to receive real-time parameter updates from Motorcortex.

### Pattern 1: Basic Parameter Subscription

```python
def startOp(self) -> None:
    """Subscribe to a single parameter."""
    self.button_subscription = self.sub.subscribe(
        ["root/UserParameters/Buttons/ResetButton"],
        group_alias="reset_button_group",
        frq_divider=10  # Update every 10 cycles
    )

    result = self.button_subscription.get()
    if result and result.status == motorcortex.OK:
        self.button_subscription.notify(self._onButtonUpdate)
    else:
        logging.error("Failed to subscribe to reset button")

def _onButtonUpdate(self, msg) -> None:
    """
    Callback for button updates (runs in subscription thread).
    Keep this method fast and thread-safe.
    """
    button_value = msg[0].value[0]
    if button_value != 0:
        logging.info("Reset button pressed!")
        self.reset_requested.set(True)  # Use ThreadSafeValue
```

### Pattern 2: Multiple Parameters in One Subscription

```python
def startOp(self) -> None:
    """Subscribe to multiple related parameters efficiently."""
    self.sensor_subscription = self.sub.subscribe(
        [
            "root/Sensors/Temperature",
            "root/Sensors/Pressure",
            "root/Sensors/Humidity"
        ],
        group_alias="sensor_group",
        frq_divider=100
    )

    result = self.sensor_subscription.get()
    if result and result.status == motorcortex.OK:
        self.sensor_subscription.notify(self._onSensorUpdate)

def _onSensorUpdate(self, msg) -> None:
    """
    Callback receives list of messages in same order as subscription.
    msg[0] = Temperature, msg[1] = Pressure, msg[2] = Humidity
    """
    temp = msg[0].value[0]
    pressure = msg[1].value[0]
    humidity = msg[2].value[0]

    # Store in thread-safe containers
    self.latest_temperature.set(temp)
    self.latest_pressure.set(pressure)
    self.latest_humidity.set(humidity)
```

### Pattern 3: Using ThreadSafeValue for Subscription Data

```python
from src.mcx_client_app import ThreadSafeValue

class MyApp(McxClientApp):
    def __init__(self, options):
        super().__init__(options)
        # Use ThreadSafeValue for data shared between threads
        self.sensor_value = ThreadSafeValue(0.0)
        self.alarm_active = ThreadSafeValue(False)

    def startOp(self):
        self.sub.subscribe(
            ["root/Sensors/Value"],
            group_alias="sensor"
        ).get().notify(self._onSensorUpdate)

    def _onSensorUpdate(self, msg):
        """Runs in subscription thread"""
        value = msg[0].value[0]
        self.sensor_value.set(value)  # Thread-safe write

        if value > 100:
            self.alarm_active.set(True)

    def iterate(self):
        """Runs in main thread"""
        current = self.sensor_value.get()  # Thread-safe read
        if self.alarm_active.get():
            logging.warning(f"Alarm! Sensor value: {current}")
            self.alarm_active.set(False)

        self.wait(1)
```

### Pattern 4: Unsubscribing in onExit

```python
def onExit(self) -> None:
    """Always unsubscribe to clean up resources."""
    if self.button_subscription:
        try:
            self.button_subscription.unsubscribe()
            logging.info("Unsubscribed from button")
        except Exception as e:
            logging.error(f"Error unsubscribing: {e}")

    if self.sensor_subscription:
        try:
            self.sensor_subscription.unsubscribe()
            logging.info("Unsubscribed from sensors")
        except Exception as e:
            logging.error(f"Error unsubscribing: {e}")
```

### Subscription Best Practices

1. **Subscribe in `startOp()`**, not `__init__()` - Connection must be established first
2. **Unsubscribe in `onExit()`** - Clean up resources
3. **Keep callbacks EXTREMELY fast** - Callbacks run in subscription thread, don't block
4. **Use ThreadSafeValue** - For data shared between subscription callbacks and iterate()
5. **Check subscription result** - Always verify `result.status == motorcortex.OK` (import motorcortex first)
6. **GROUP parameters in subscriptions whenever possible** - More efficient, better performance
7. **Use descriptive group_alias** - Helps with debugging
8. **Set appropriate frq_divider** - Don't request updates faster than needed (saves bandwidth)

### IMPORTANT: Group Subscriptions Together for Better Performance

**Strongly Recommended:** Subscribe to multiple related parameters in a **single subscription** instead of creating separate subscriptions. Grouped subscriptions are **more efficient** and reduce network overhead.

**When to Group Parameters:**

✅ **DO group when:**

- Parameters are **logically related** (all sensor readings, all configuration values)
- Parameters need the **same update frequency** (same `frq_divider`)
- Parameters are processed **together** in your logic
- Reading from the **same subsystem** (e.g., all from `root/Sensors/`, all from `root/AGVControl/`)

❌ **DON'T group when:**

- Parameters need **different update frequencies** (one needs 10Hz, another 100Hz)
- One is **critical, low-latency** and others are not
- Parameters are **completely unrelated** and processed separately
- Mixing **input parameters** (you write) with **output parameters** (you read) that have different purposes

**Examples:**

✅ **GOOD - Grouped subscription (preferred):**

```python
def startOp(self) -> None:
    """Group all related sensor readings in ONE subscription."""
    self.sensor_subscription = self.sub.subscribe(
        [
            "root/Sensors/Temperature",
            "root/Sensors/Pressure",
            "root/Sensors/Humidity",
            "root/Sensors/VibrationLevel"
        ],
        group_alias="all_sensors",  # One subscription for all sensors
        frq_divider=100
    )
    result = self.sensor_subscription.get()
    if result and result.status == motorcortex.OK:
        self.sensor_subscription.notify(self._onSensorUpdate)

def _onSensorUpdate(self, msg) -> None:
    """Single callback handles all sensors efficiently."""
    self.temperature.set(msg[0].value[0])
    self.pressure.set(msg[1].value[0])
    self.humidity.set(msg[2].value[0])
    self.vibration.set(msg[3].value[0])
```

❌ **BAD - Separate subscriptions (inefficient):**

```python
def startOp(self) -> None:
    """Don't do this - wastes resources with 4 separate subscriptions!"""
    # ❌ Creates 4 separate network subscriptions - inefficient!
    self.sub.subscribe(["root/Sensors/Temperature"], "temp", 100).get().notify(self._onTemp)
    self.sub.subscribe(["root/Sensors/Pressure"], "press", 100).get().notify(self._onPress)
    self.sub.subscribe(["root/Sensors/Humidity"], "humid", 100).get().notify(self._onHumid)
    self.sub.subscribe(["root/Sensors/VibrationLevel"], "vib", 100).get().notify(self._onVib)
    # This creates 4x network overhead and 4 separate callbacks!
```

✅ **GOOD - Separate subscriptions when needed:**

```python
def startOp(self) -> None:
    """OK to separate when update frequencies differ."""
    # High-frequency critical parameter (10Hz)
    self.velocity_sub = self.sub.subscribe(
        ["root/AGVControl/actualVelocityLocal"],
        group_alias="velocity",
        frq_divider=10  # Fast updates
    ).get().notify(self._onVelocityUpdate)

    # Low-frequency configuration parameters (1Hz)
    self.config_sub = self.sub.subscribe(
        [
            "root/UserParameters/Config/MaxSpeed",
            "root/UserParameters/Config/Thresholds"
        ],
        group_alias="config",
        frq_divider=1000  # Slow updates - different frequency!
    ).get().notify(self._onConfigUpdate)
```

**Benefits of Grouping:**

- ✅ **Reduced network overhead** - One subscription vs multiple
- ✅ **Better performance** - Less communication with Motorcortex
- ✅ **Simpler code** - One callback instead of many
- ✅ **Atomic updates** - All values update together in one message
- ✅ **Easier debugging** - Single subscription to monitor

**Rule of Thumb:** If parameters are updated at the same rate and processed together, **always group them in one subscription**.

### ⚠️ CRITICAL: Subscription Callbacks Must Be FAST - They Run on EVERY Tree Update!

**🚨 EXTREMELY IMPORTANT:** Subscription callbacks fire on **EVERY parameter tree update** (based on `frq_divider`), **NOT** when values change. If `frq_divider=10` and Motorcortex runs at 1000Hz, your callback runs **100 times per second** - even if the value never changes!

**What This Means:**

- Your callback executes **constantly** at high frequency
- The value might be **identical** on every call
- Callbacks run in a **separate thread** from your main iterate() loop
- **Any blocking operation** (file I/O, network calls, complex math) will **cause severe performance issues**

**Golden Rules for Callbacks:**

✅ **ONLY DO THIS in callbacks:**

1. Extract value from `msg[0].value[0]`
2. Store it in a ThreadSafeValue: `self.my_value.set(value)`
3. (Optional) Check if changed: `if value != self.previous_value`
4. **That's it. Nothing else.**

❌ **NEVER DO THIS in callbacks:**

- ❌ Logging on every call (spams logs at 100Hz+)
- ❌ Call `self.req.setParameter()` (network overhead every cycle!)
- ❌ File I/O (writing to files, reading config)
- ❌ Complex calculations (trigonometry, matrix math)
- ❌ Database queries
- ❌ Sleep/wait calls
- ❌ Calling other slow functions

**Callback Best Practices:**

✅ **DO - Minimal, fast callback:**

```python
def _onVelocityUpdate(self, msg) -> None:
    """GOOD: Fast extraction and storage only."""
    new_velocity = msg[0].value[0]
    self.current_velocity.set(new_velocity)  # Just store it
    # Done! Let iterate() handle the rest
```

✅ **DO - With change detection (still fast):**

```python
def _onVelocityUpdate(self, msg) -> None:
    """GOOD: Quick check if changed, minimal logging."""
    new_velocity = msg[0].value[0]
    self.current_velocity.set(new_velocity)

    # Only log when value actually changes (not every tree update)
    if new_velocity != self.previous_velocity:
        logging.info(f"Velocity changed: {self.previous_velocity} → {new_velocity}")
        self.previous_velocity = new_velocity
```

❌ **DON'T - Slow operations in callback:**

```python
def _onVelocityUpdate(self, msg) -> None:
    """BAD: This runs 100+ times per second!"""
    velocity = msg[0].value[0]

    # ❌ Logs EVERY tree update (even if value unchanged) - log spam!
    logging.info(f"Velocity: {velocity}")

    # ❌ Network call EVERY cycle - huge overhead!
    self.req.setParameter("root/Status/LastVelocity", velocity).get()

    # ❌ File I/O EVERY cycle - kills performance!
    with open("velocity_log.txt", "a") as f:
        f.write(f"{velocity}\n")

    # ❌ Complex math EVERY cycle - wastes CPU!
    safety_zone = self._calculateComplexSafetyZone(velocity)
```

✅ **CORRECT Pattern - Callback stores, iterate() processes:**

```python
def __init__(self, options):
    super().__init__(options)
    self.current_velocity = ThreadSafeValue(0.0)
    self.previous_velocity = 0.0

def _onVelocityUpdate(self, msg) -> None:
    """Callback: ONLY extract and store. Runs 100+ times/sec!"""
    new_velocity = msg[0].value[0]
    self.current_velocity.set(new_velocity)  # Fast storage only

def iterate(self) -> None:
    """iterate(): Do ALL the processing here. Runs at your control rate."""
    velocity = self.current_velocity.get()

    # Do expensive operations in iterate(), not callback
    if velocity != self.previous_velocity:
        # Log changes
        logging.info(f"Velocity: {velocity}")

        # Update parameters
        self.req.setParameter("root/Status/LastVelocity", velocity).get()

        # Complex calculations
        safety_zone = self._calculateComplexSafetyZone(velocity)

        # File I/O
        self._logToFile(velocity)

        self.previous_velocity = velocity

    self.wait(0.1)  # Control your own update rate
```

**Summary - Callback Rules:**

- **Callbacks run at HIGH FREQUENCY** (100Hz+) on EVERY tree update
- **Keep callbacks to 3 lines max**: Extract → Store → (Maybe check if changed)
- **Do ALL processing in iterate()**: Logging, setParameter, calculations, file I/O
- **Remember: Tree update ≠ Value change** - Same value repeated constantly!

---

## Error Handler - Triggering System Errors

The `McxErrorHandler` allows your client application to trigger system-level errors at different severity levels in Motorcortex. This is essential for integrating your application into the overall system safety and error management.

### Overview

Every `McxClientApp` instance has a built-in error handler accessible via `self.errorHandler`. The error handler:

- Triggers errors at 5 different severity levels (INFO, WARNING, FORCED_DISENGAGE, SHUTDOWN, EMERGENCY_STOP)
- Uses **subsystem IDs** to identify which service or component triggered the error
- Uses **error codes** to describe what the error is (e.g., battery low, sensor failure, timeout)
- Supports acknowledgment callbacks to reset your application state when errors are cleared

### Error Severity Levels

The error handler supports 5 severity levels (from `MotorcortexErrorLevel` enum):

| Level                   | Value | Description             | System Response                |
| ----------------------- | ----- | ----------------------- | ------------------------------ |
| `ERROR_LEVEL_UNDEFINED` | 0     | Undefined/cleared error | Clears active errors           |
| `INFO`                  | 1     | Information message     | No system action, just logging |
| `WARNING`               | 2     | Warning condition       | System continues running       |
| `FORCED_DISENGAGE`      | 3     | Graceful software stop  | Disengages system gracefully   |
| `SHUTDOWN`              | 4     | Abrupt software stop    | Immediate software shutdown    |
| `EMERGENCY_STOP`        | 5     | Hardware emergency stop | Software AND hardware stop     |

**Severity Progression:** INFO < WARNING < FORCED_DISENGAGE < SHUTDOWN < EMERGENCY_STOP

### Subsystem IDs - Identifying Error Sources

**Subsystem IDs** identify which service or component triggered an error. This is critical for diagnosing issues in complex systems with multiple services.

**Best Practices:**

✅ **One Subsystem ID per Service:**

- If your client app is a single logical service (e.g., "BatteryMonitor"), use one subsystem ID for the entire service
- Set the subsystem ID in `startOp()` and use it for all errors in that service

```python
def startOp(self) -> None:
    # Set subsystem ID for this service
    self.errorHandler.set_subsystem_id(1)  # BatteryMonitor = subsystem 1
```

✅ **Multiple Subsystem IDs within a Service:**

- If your service has distinct subsystems (e.g., "FleetManager" managing multiple robots), use different IDs for each
- Pass `subsystem_id` parameter when triggering errors to distinguish between subsystems

```python
class FleetManager(McxClientApp):
    def __init__(self, options):
        super().__init__(options)
        self.ROBOT_1_SUBSYSTEM = 10
        self.ROBOT_2_SUBSYSTEM = 11
        self.ROBOT_3_SUBSYSTEM = 12

    def check_robot_1(self):
        if battery_low:
            # Specify which robot has the error
            self.errorHandler.trigger_warning(
                error_code=1001,
                subsystem_id=self.ROBOT_1_SUBSYSTEM
            )
```

**Subsystem ID Guidelines:**

- Use **unique IDs across your entire system** to avoid conflicts
- Document your subsystem ID allocation (e.g., 1-10 for service A, 11-20 for service B)
- Reserve ID 0 for system-level errors (undefined subsystem)
- Use consistent IDs - don't change them between runs

### Error Codes - Describing What Happened

**Error codes** describe the specific condition that triggered the error. Think of them as unique identifiers for different failure modes.

**Best Practices:**

✅ **Define Error Code Constants:**

```python
class BatteryMonitor(McxClientApp):
    # Error code definitions
    ERROR_BATTERY_LOW = 1001
    ERROR_BATTERY_CRITICAL = 1002
    ERROR_CHARGING_FAULT = 1003
    ERROR_TEMPERATURE_HIGH = 1004
    ERROR_COMMUNICATION_LOST = 1005

    def check_battery(self):
        if battery_voltage < self.CRITICAL_THRESHOLD:
            self.errorHandler.trigger_emergency_stop(
                error_code=self.ERROR_BATTERY_CRITICAL
            )
        elif battery_voltage < self.LOW_THRESHOLD:
            self.errorHandler.trigger_warning(
                error_code=self.ERROR_BATTERY_LOW
            )
```

✅ **Use Meaningful Ranges:**

```python
# Organize error codes by category
# 1000-1099: Battery errors
# 1100-1199: Sensor errors
# 1200-1299: Communication errors
# 1300-1399: Motion errors

ERROR_BATTERY_LOW = 1001
ERROR_BATTERY_CRITICAL = 1002

ERROR_SENSOR_FAULT = 1101
ERROR_SENSOR_CALIBRATION = 1102

ERROR_COMM_TIMEOUT = 1201
ERROR_COMM_LOST = 1202
```

✅ **Document Error Codes:**

```python
"""
BatteryMonitor Service - Error Codes

Subsystem ID: 1

Error Codes:
- 1001: Battery voltage below warning threshold (triggers WARNING)
- 1002: Battery voltage critical (triggers EMERGENCY_STOP)
- 1003: Charging circuit fault detected (triggers FORCED_DISENGAGE)
- 1004: Battery temperature too high (triggers SHUTDOWN)
- 1005: Communication with battery management lost (triggers WARNING)
"""
```

### Basic Usage Pattern

**1. Configure Error Handler in `startOp()`:**

```python
def startOp(self) -> None:
    """Initialize error handler with subsystem ID."""
    # Set subsystem ID for this service
    self.errorHandler.set_subsystem_id(1)

    # Optional: Set callback for error acknowledgment
    self.errorHandler.set_acknowledge_callback(self.on_error_acknowledged)

    logging.info("Error handler configured for subsystem 1")
```

**2. Trigger Errors in Your Code:**

```python
def iterate(self) -> None:
    """Monitor conditions and trigger appropriate errors."""
    battery_voltage = self.get_battery_voltage()

    if battery_voltage < 10.5:
        # Critical - stop everything immediately
        self.errorHandler.trigger_emergency_stop(error_code=1002)

    elif battery_voltage < 11.0:
        # Low battery warning
        self.errorHandler.trigger_warning(error_code=1001)

    self.wait(1.0)
```

**3. Handle Error Acknowledgment (Optional):**

```python
def on_error_acknowledged(self) -> None:
    """Called when operator acknowledges the error."""
    logging.info("Error acknowledged - resetting application state")

    # Reset your error conditions
    self.error_count = 0
    self.retry_attempts = 0

    # Clear any error flags
    self.req.setParameter(
        f"{self.options.get_service_parameter_path}/ErrorActive",
        0
    ).get()
```

### Complete Error Handler Example

```python
import logging
import motorcortex
from src.mcx_client_app import McxClientApp, McxClientAppConfiguration

class SafetyMonitor(McxClientApp):
    """
    Monitors safety conditions and triggers appropriate errors.

    Subsystem ID: 5
    Error Codes:
    - 2001: Temperature warning (>70°C)
    - 2002: Temperature critical (>85°C)
    - 2003: Pressure out of range
    - 2004: Emergency stop button pressed
    """

    # Subsystem ID
    SUBSYSTEM_ID = 5

    # Error codes
    ERROR_TEMP_WARNING = 2001
    ERROR_TEMP_CRITICAL = 2002
    ERROR_PRESSURE = 2003
    ERROR_ESTOP = 2004

    # Thresholds
    TEMP_WARNING = 70.0
    TEMP_CRITICAL = 85.0
    PRESSURE_MIN = 50.0
    PRESSURE_MAX = 150.0

    def __init__(self, options: McxClientAppConfiguration):
        super().__init__(options)
        self.last_temp_state = "normal"
        self.error_count = 0

    def startOp(self) -> None:
        """Configure error handler."""
        self.errorHandler.set_subsystem_id(self.SUBSYSTEM_ID)
        self.errorHandler.set_acknowledge_callback(self.on_error_acknowledged)
        logging.info(f"Safety monitor configured with subsystem ID {self.SUBSYSTEM_ID}")

    def iterate(self) -> None:
        """Monitor safety parameters."""
        # Get sensor values
        temperature = self.req.getParameter("root/Sensors/Temperature").get().value[0]
        pressure = self.req.getParameter("root/Sensors/Pressure").get().value[0]
        estop = self.req.getParameter("root/Safety/EmergencyStop").get().value[0]

        # Check emergency stop (highest priority)
        if estop:
            self.errorHandler.trigger_emergency_stop(error_code=self.ERROR_ESTOP)
            logging.critical("Emergency stop button pressed!")
            return

        # Check temperature (rising severity)
        if temperature > self.TEMP_CRITICAL:
            if self.last_temp_state != "critical":
                self.errorHandler.trigger_shutdown(error_code=self.ERROR_TEMP_CRITICAL)
                logging.error(f"Temperature critical: {temperature}°C")
                self.last_temp_state = "critical"

        elif temperature > self.TEMP_WARNING:
            if self.last_temp_state != "warning":
                self.errorHandler.trigger_warning(error_code=self.ERROR_TEMP_WARNING)
                logging.warning(f"Temperature high: {temperature}°C")
                self.last_temp_state = "warning"
        else:
            self.last_temp_state = "normal"

        # Check pressure
        if pressure < self.PRESSURE_MIN or pressure > self.PRESSURE_MAX:
            self.errorHandler.trigger_forced_disengage(error_code=self.ERROR_PRESSURE)
            logging.error(f"Pressure out of range: {pressure} bar")

        self.wait(1.0)

    def on_error_acknowledged(self) -> None:
        """Reset state when error is acknowledged."""
        logging.info("Error acknowledged - resetting safety monitor")
        self.last_temp_state = "normal"
        self.error_count = 0

if __name__ == "__main__":
    config = McxClientAppConfiguration(name="SafetyMonitor")
    config.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/services_config.json",
        non_deployed_config="services_config.json"
    )
    config.load_config()
    app = SafetyMonitor(config)
    app.run()
```

### Advanced Patterns

**Rising Edge Detection (Trigger Error Once):**

```python
def __init__(self, options):
    super().__init__(options)
    self.last_value = 0

def iterate(self):
    value = self.req.getParameter(f"{self.options.get_service_parameter_path}/Input").get().value[0]

    # Only trigger on change (0 -> non-zero)
    if self.last_value == 0 and value != 0:
        if value < 10:
            self.errorHandler.trigger_warning(error_code=3001)
        elif value < 20:
            self.errorHandler.trigger_forced_disengage(error_code=3002)

    self.last_value = value
    self.wait(0.5)
```

**Multi-Subsystem Service:**

```python
class MultiRobotController(McxClientApp):
    """Controls 3 robots with separate subsystem IDs."""

    ROBOT_A_SUBSYSTEM = 20
    ROBOT_B_SUBSYSTEM = 21
    ROBOT_C_SUBSYSTEM = 22

    ERROR_COLLISION = 4001
    ERROR_TIMEOUT = 4002

    def check_robot_a(self):
        if collision_detected:
            self.errorHandler.trigger_emergency_stop(
                error_code=self.ERROR_COLLISION,
                subsystem_id=self.ROBOT_A_SUBSYSTEM  # Identify which robot
            )

    def check_robot_b(self):
        if motion_timeout:
            self.errorHandler.trigger_warning(
                error_code=self.ERROR_TIMEOUT,
                subsystem_id=self.ROBOT_B_SUBSYSTEM
            )
```

**Clearing Errors Programmatically:**

```python
def iterate(self):
    # Check if error condition resolved
    if self.error_active and self.error_resolved():
        # Clear the error by triggering ERROR_LEVEL_UNDEFINED
        self.errorHandler.trigger_error(
            level=MotorcortexErrorLevel.ERROR_LEVEL_UNDEFINED,
            code=0
        )
        self.error_active = False
        logging.info("Error condition resolved, error cleared")
```

### Error Handler Best Practices

✅ **DO:**

- Define subsystem IDs as class constants with descriptive names
- Document all error codes in class/module docstring
- Use error code ranges for different error categories (1000-1099: battery, 1100-1199: sensors)
- Implement rising edge detection to avoid repeated error triggers
- Set subsystem ID in `startOp()` for single-subsystem services
- Use acknowledge callbacks to reset application state
- Log when errors are triggered for debugging

❌ **DON'T:**

- Use random or changing subsystem IDs - they must be consistent
- Reuse error codes for different conditions
- Trigger errors in subscription callbacks (too fast, wrong thread)
- Forget to document your subsystem ID and error code allocation
- Use subsystem ID 0 unless it's truly a system-level error
- Trigger EMERGENCY_STOP for non-critical conditions

### Error Handler Reference

**Available Methods:**

```python
# Configure (in startOp)
self.errorHandler.set_subsystem_id(subsystem_id: int)
self.errorHandler.set_acknowledge_callback(callback: Callable)

# Trigger errors (in iterate or other methods)
self.errorHandler.trigger_info(error_code: int, subsystem_id: int = None)
self.errorHandler.trigger_warning(error_code: int, subsystem_id: int = None)
self.errorHandler.trigger_forced_disengage(error_code: int, subsystem_id: int = None)
self.errorHandler.trigger_shutdown(error_code: int, subsystem_id: int = None)
self.errorHandler.trigger_emergency_stop(error_code: int, subsystem_id: int = None)

# Generic trigger (advanced use)
self.errorHandler.trigger_error(
    level: MotorcortexErrorLevel,
    code: int,
    subsystem_id: int = None
)
```

**When to Use Each Severity Level:**

- **INFO**: Non-critical information (state changes, milestones reached)
- **WARNING**: Conditions that need attention but don't stop operation (high temperature, low battery warning)
- **FORCED_DISENGAGE**: Controlled shutdown needed (sensor fault, timeout, safe limits exceeded)
- **SHUTDOWN**: Immediate stop required (critical sensor failure, communication lost)
- **EMERGENCY_STOP**: Hardware safety issue (collision detected, physical emergency stop pressed)

---

## Keep iterate() Clean - Best Practices

### Rule 1: Extract Logic into Private Methods

❌ **BAD - Cluttered iterate():**

```python
def iterate(self):
    # Long inline logic
    temp = self.req.getParameter("root/Sensors/Temp").get().value[0]
    if temp > 50:
        self.req.setParameter("root/Cooling/Fan", 1).get()
        logging.info("Fan activated")
    else:
        self.req.setParameter("root/Cooling/Fan", 0).get()
        logging.info("Fan deactivated")

    pressure = self.req.getParameter("root/Sensors/Pressure").get().value[0]
    if pressure > 100:
        self.req.setParameter("root/Safety/Alarm", 1).get()
        logging.warning("Pressure alarm!")

    self.wait(1)
```

✅ **GOOD - Clean iterate():**

```python
def iterate(self):
    """Main control loop - delegates to helper methods."""
    self._checkTemperature()
    self._checkPressure()
    self.wait(1)

def _checkTemperature(self) -> None:
    """Monitor temperature and control cooling fan."""
    temp = self.req.getParameter("root/Sensors/Temp").get().value[0]
    fan_state = 1 if temp > 50 else 0
    self.req.setParameter("root/Cooling/Fan", fan_state).get()
    logging.debug(f"Fan: {fan_state}, Temp: {temp}")

def _checkPressure(self) -> None:
    """Monitor pressure and trigger alarm if needed."""
    pressure = self.req.getParameter("root/Sensors/Pressure").get().value[0]
    if pressure > 100:
        self.req.setParameter("root/Safety/Alarm", 1).get()
        logging.warning(f"Pressure alarm: {pressure}")
```

### Rule 2: Use Subscriptions Instead of Polling

❌ **BAD - Polling in iterate():**

```python
def iterate(self):
    button = self.req.getParameter("root/Buttons/Start").get().value[0]
    if button != self.last_button_state:
        if button == 1:
            self._startOperation()
        self.last_button_state = button
    self.wait(0.1)
```

✅ **GOOD - Use subscriptions:**

```python
def startOp(self):
    """Setup subscription once."""
    self.button_sub = self.sub.subscribe(
        ["root/Buttons/Start"],
        group_alias="start_button"
    ).get()
    self.button_sub.notify(self._onButtonPress)

def _onButtonPress(self, msg):
    """React to button press immediately."""
    if msg[0].value[0] == 1:
        self.operation_requested.set(True)

def iterate(self):
    """Check request flag, not polling parameter."""
    if self.operation_requested.get():
        self._startOperation()
        self.operation_requested.set(False)
    self.wait(1)
```

### Rule 3: Use State Machines for Complex Logic

✅ **GOOD - State machine pattern:**

```python
from enum import Enum

class RobotState(Enum):
    IDLE = 0
    MOVING_TO_START = 1
    EXECUTING = 2
    RETURNING = 3

class RobotApp(McxClientApp):
    def __init__(self, options):
        super().__init__(options)
        self.state = RobotState.IDLE

    def iterate(self):
        """State machine - clean and readable."""
        if self.state == RobotState.IDLE:
            self._handleIdleState()
        elif self.state == RobotState.MOVING_TO_START:
            self._handleMovingState()
        elif self.state == RobotState.EXECUTING:
            self._handleExecutingState()
        elif self.state == RobotState.RETURNING:
            self._handleReturningState()

        self.wait(0.1)

    def _handleIdleState(self):
        if self.start_requested.get():
            self.state = RobotState.MOVING_TO_START
            logging.info("Starting operation")

    def _handleMovingState(self):
        if self._isAtStartPosition():
            self.state = RobotState.EXECUTING

    # ... other state handlers
```

### Rule 4: Initialize Data in **init**, Not iterate()

❌ **BAD:**

```python
def iterate(self):
    if not hasattr(self, 'counter'):
        self.counter = 0  # Don't do this!
    self.counter += 1
```

✅ **GOOD:**

```python
def __init__(self, options):
    super().__init__(options)
    self.counter = 0  # Initialize here

def iterate(self):
    self.counter += 1
```

### Rule 5: Use wait() and wait_for() Appropriately

✅ **GOOD - Responsive to stop signals:**

```python
def iterate(self):
    self._doWork()
    self.wait(5)  # Checks stop signal every 0.2s by default

def _longOperation(self):
    # Wait for condition with timeout
    success = self.wait_for(
        param="root/Operations/Complete",
        value=1,
        timeout=30,
        operat="=="
    )
    if not success:
        logging.error("Operation timeout")
```

### Rule 6: Keep iterate() Focused on One Responsibility

If `iterate()` does too much, split into multiple applications:

```python
# Instead of one app doing everything:
class MonsterApp(McxClientApp):
    def iterate(self):
        self._logData()
        self._controlRobot()
        self._monitorSensors()
        self._updateDatabase()
        self._sendNotifications()

# Split into multiple focused apps:
class DataLoggerApp(McxClientApp):
    def iterate(self):
        self._logData()

class RobotControlApp(McxClientApp):
    def iterate(self):
        self._controlRobot()
```

### Clean iterate() Checklist

- [ ] Less than 20 lines in `iterate()` method
- [ ] No parameter access logic (use subscriptions or helper methods)
- [ ] No inline conditionals longer than 1 line
- [ ] Uses `self.wait()` or `self.wait_for()` for delays
- [ ] Delegates to private helper methods (prefix with `_`)
- [ ] Clear control flow (state machine if complex)
- [ ] No initialization code (use `__init__()` or `startOp()`)

---

## Complete Working Examples

### Example 1: Simple Counter with Start/Stop Button

```python
import logging
from src.mcx_client_app import McxClientApp, McxClientAppConfiguration

class CounterApp(McxClientApp):
    """Increments counter when start button is active."""

    def __init__(self, options: McxClientAppConfiguration):
        super().__init__(options)
        self.counter = 0

    def startOp(self) -> None:
        """Initialize counter parameter."""
        self.req.setParameter(f"{self.options.get_service_parameter_path}/Counter", 0).get()
        logging.info("Counter initialized")

    def iterate(self) -> None:
        """Increment counter every second."""
        self.counter += 1
        self.req.setParameter(f"{self.options.get_service_parameter_path}/Counter", self.counter).get()
        logging.info(f"Counter: {self.counter}")
        self.wait(1)

    def onExit(self) -> None:
        """Log final count."""
        logging.info(f"Exiting. Final count: {self.counter}")

if __name__ == "__main__":
    config = McxClientAppConfiguration(name="CounterApp")
    config.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/services_config.json",
        non_deployed_config="services_config.json"
    )
    config.load_config()
    app = CounterApp(config)
    app.run()
```

### Example 2: Temperature Monitor with Alarm

```python
import logging
import motorcortex
from src.mcx_client_app import McxClientApp, McxClientAppConfiguration, ThreadSafeValue

class TemperatureMonitor(McxClientApp):
    """Monitors temperature and activates alarm if threshold exceeded."""

    def __init__(self, options: McxClientAppConfiguration):
        super().__init__(options)
        self.current_temperature = ThreadSafeValue(0.0)
        self.alarm_threshold = 75.0
        self.temp_subscription = None

    def startOp(self) -> None:
        """Subscribe to temperature parameter."""
        self.temp_subscription = self.sub.subscribe(
            ["root/Sensors/Temperature"],
            group_alias="temperature",
            frq_divider=50
        )
        result = self.temp_subscription.get()
        if result and result.status == motorcortex.OK:
            self.temp_subscription.notify(self._onTemperatureUpdate)
            logging.info("Temperature subscription active")

    def _onTemperatureUpdate(self, msg) -> None:
        """Update current temperature (runs in subscription thread)."""
        temp = msg[0].value[0]
        self.current_temperature.set(temp)

    def iterate(self) -> None:
        """Check temperature and control alarm."""
        temp = self.current_temperature.get()

        if temp > self.alarm_threshold:
            self._activateAlarm(temp)
        else:
            self._deactivateAlarm()

        self.wait(2)

    def _activateAlarm(self, temp: float) -> None:
        """Activate alarm and log warning."""
        self.req.setParameter("root/Safety/TemperatureAlarm", 1).get()
        logging.warning(f"Temperature alarm! Current: {temp}°C, Threshold: {self.alarm_threshold}°C")

    def _deactivateAlarm(self) -> None:
        """Deactivate alarm."""
        self.req.setParameter("root/Safety/TemperatureAlarm", 0).get()

    def onExit(self) -> None:
        """Cleanup subscriptions."""
        if self.temp_subscription:
            self.temp_subscription.unsubscribe()
        self.req.setParameter("root/Safety/TemperatureAlarm", 0).get()
        logging.info("Temperature monitor stopped")

if __name__ == "__main__":
    config = McxClientAppConfiguration(name="TemperatureMonitor")
    config.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/services_config.json",
        non_deployed_config="services_config.json"
    )
    config.load_config()
    app = TemperatureMonitor(config)
    app.run()
```

        """Check temperature and control alarm."""
        temp = self.current_temperature.get()

        if temp > self.alarm_threshold:
            self._activateAlarm(temp)
        else:
            self._deactivateAlarm()

        self.wait(2)

    def _activateAlarm(self, temp: float) -> None:
        """Activate alarm and log warning."""
        self.req.setParameter("root/Safety/TemperatureAlarm", 1).get()
        logging.warning(f"Temperature alarm! Current: {temp}°C, Threshold: {self.alarm_threshold}°C")

    def _deactivateAlarm(self) -> None:
        """Deactivate alarm."""
        self.req.setParameter("root/Safety/TemperatureAlarm", 0).get()

    def onExit(self) -> None:
        """Cleanup subscriptions."""
        if self.temp_subscription:
            self.temp_subscription.unsubscribe()
        self.req.setParameter("root/Safety/TemperatureAlarm", 0).get()
        logging.info("Temperature monitor stopped")

if **name** == "**main**":
config = McxClientAppConfiguration() # Update the config paths below to match your deployment requirements # deployed_config: Path used when DEPLOYED env var is set (on production systems) # non_deployed_config: Path used during local development
config.set_config_paths(
deployed_config="/etc/motorcortex/config/services/temperature_monitor.json",
non_deployed_config="config.json"
)
app = TemperatureMonitor(config)
app.run()

````

### Example 3: Robot Motion Program

```python
import logging
import math
from src.mcx_client_app import McxClientApp, McxClientAppConfiguration, State
from robot_control.motion_program import MotionProgram, Waypoint
from robot_control.robot_command import RobotCommand
from robot_control.system_defs import InterpreterStates

class RobotPickPlace(McxClientApp):
    """Executes pick-and-place motion program."""

    def __init__(self, options: McxClientAppConfiguration):
        super().__init__(options)
        self.robot = None
        self.cycle_count = 0

    def startOp(self) -> None:
        """Initialize robot and engage."""
        self.robot = RobotCommand(self.req, self.motorcortex_types)

        if self.robot.engage():
            logging.info("Robot engaged successfully")
            self.robot.stop()
            self.robot.reset()
        else:
            logging.error("Failed to engage robot")
            self.reset()  # Stop the application

    def iterate(self) -> None:
        """Execute pick-and-place cycle."""
        self._executePickPlace()
        self.cycle_count += 1
        logging.info(f"Completed cycle {self.cycle_count}")
        self.wait(2)

    def _executePickPlace(self) -> None:
        """Execute the pick-and-place motion program."""
        # Define waypoints
        home = Waypoint([0.4, 0.0, 0.35, 0, math.pi, 0])
        pick = Waypoint([0.5, 0.2, 0.1, 0, math.pi, 0])
        place = Waypoint([0.5, -0.2, 0.1, 0, math.pi, 0])

        # Create motion program
        mp = MotionProgram(self.req, self.motorcortex_types)
        mp.addMoveL([home], velocity=0.3, acceleration=0.5)
        mp.addMoveL([pick], velocity=0.2, acceleration=0.3)
        mp.addMoveL([place], velocity=0.2, acceleration=0.3)
        mp.addMoveL([home], velocity=0.3, acceleration=0.5)

        # Send and execute
        mp.send("pick_place_cycle").get()

        state = self.robot.play()
        if state == InterpreterStates.MOTION_NOT_ALLOWED_S.value:
            logging.info("Moving to start position...")
            if self.robot.moveToStart(10):
                self.robot.play()

        # Wait for completion
        self.wait_for("root/Control/fInterpreterState",
                     InterpreterStates.MOTION_COMPLETE_S.value,
                     timeout=30)

    def onExit(self) -> None:
        """Stop and disengage robot."""
        if self.robot:
            self.robot.stop()
            self.robot.disengage()
            logging.info(f"Robot stopped after {self.cycle_count} cycles")

if __name__ == "__main__":
    config = McxClientAppConfiguration()
    # Update the config paths below to match your deployment requirements
    # deployed_config: Path used when DEPLOYED env var is set (on production systems)
    # non_deployed_config: Path used during local development
    config.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/robot_pick_place.json",
        non_deployed_config="config.json"
    )
    config.run_during_states = [State.ENGAGED_S]  # Only run when engaged
    app = RobotPickPlace(config)
    app.run()
````

### Example 4: Error Handler with Rising Edge Detection

```python
import logging
import motorcortex
from src.mcx_client_app import McxClientApp, McxClientAppConfiguration

class ErrorHandlerApp(McxClientApp):
    """
    Example demonstrating error handling with different severity levels.
    Monitors input parameter and triggers appropriate errors based on value.
    Uses rising edge detection to trigger errors only once per range entry.
    """
    def __init__(self, options: McxClientAppConfiguration):
        super().__init__(options)
        self.__last_value: int = 0

    def startOp(self) -> None:
        """
        Initialize error handler with subsystem ID and acknowledge callback.
        """
        # Set subsystem ID (helpful to identify which subsystem the error belongs to)
        self.errorHandler.set_subsystem_id(1)

        # Set callback for error acknowledgment
        self.errorHandler.set_acknowledge_callback(self.on_error_acknowledged)

        logging.info("Error handler configured")

    def on_error_acknowledged(self) -> None:
        """
        Callback when user acknowledges an error.
        Reset the input parameter to clear the error condition.
        """
        result = self.req.setParameter(
            f"{self.options.get_service_parameter_path}/input",
            0
        ).get()

        if result is not None and result.status != motorcortex.OK:
            logging.error("Failed to reset input parameter after error acknowledgment.")
        else:
            logging.info("Error acknowledged - input parameter reset to 0")

    def iterate(self) -> None:
        """
        Monitor input parameter and trigger errors based on value ranges.
        Uses rising edge detection to avoid repeated error triggers.
        """
        result = self.req.getParameter(
            f"{self.options.get_service_parameter_path}/input"
        ).get()

        if result is not None and result.status == motorcortex.OK:
            value = result.value[0]

            # Rising edge detection - only trigger when value changes
            if self.__last_value != value:
                # Value ranges trigger different error levels
                if 10 < value < 20:
                    logging.info("Triggering WARNING level error.")
                    self.errorHandler.trigger_warning(error_code=1001)

                elif 20 <= value < 30:
                    logging.info("Triggering FORCED_DISENGAGE level error.")
                    self.errorHandler.trigger_forced_disengage(error_code=2001)

                elif 30 <= value < 40:
                    logging.info("Triggering SHUTDOWN level error.")
                    self.errorHandler.trigger_shutdown(error_code=3001)

                elif 40 <= value < 50:
                    logging.info("Triggering EMERGENCY_STOP level error.")
                    self.errorHandler.trigger_emergency_stop(error_code=4001)

                self.__last_value = value

        # Use self.wait() to keep watchdog alive
        self.wait(0.5)

    def onExit(self) -> None:
        """
        Cleanup on exit.
        """
        logging.info("Error handler app exiting")

if __name__ == "__main__":
    config = McxClientAppConfiguration(name="ErrorExample")
    config.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/services_config.json",
        non_deployed_config="services_config.json"
    )
    config.load_config()
    app = ErrorHandlerApp(config)
    app.run()
```

**services_config.json for Error Handler Example:**

```json
{
  "Services": [
    {
      "Name": "ErrorExample",
      "Enabled": true,
      "Config": {
        "login": "admin",
        "password": "password",
        "target_url": "wss://192.168.1.100",
        "autoStart": true
      },
      "Parameters": {
        "Version": "1.0",
        "Children": [
          {
            "Name": "userParameters",
            "Children": [
              {
                "Name": "input",
                "Type": "int, input",
                "Value": 0
              }
            ]
          }
        ]
      },
      "Watchdog": {
        "Enabled": true,
        "Disabled": false,
        "high": 1000000,
        "tooHigh": 5000000
      }
    }
  ]
}
```

```python
import logging
import time
import json
from pathlib import Path
from src.mcx_client_app import McxClientApp, McxClientAppConfiguration, ThreadSafeValue

class DataLoggerConfiguration(McxClientAppConfiguration):
    """Configuration for data logger with custom parameters."""

    def __init__(self, log_interval: float = 1.0,
                 log_file: str = "data_log.json",
                 parameters_to_log: list = None,
                 **kwargs):
        self.log_interval = log_interval
        self.log_file = log_file
        self.parameters_to_log = parameters_to_log or []
        super().__init__(**kwargs)

class DataLogger(McxClientApp):
    """Logs specified parameters to file at regular intervals."""

    def __init__(self, options: DataLoggerConfiguration):
        super().__init__(options)
        self.options: DataLoggerConfiguration  # Type hint for IDE
        self.logged_data = []
        self.latest_values = ThreadSafeValue({})
        self.data_subscription = None

    def startOp(self) -> None:
        """Subscribe to parameters to log."""
        if not self.options.parameters_to_log:
            logging.warning("No parameters configured for logging")
            return

        self.data_subscription = self.sub.subscribe(
            self.options.parameters_to_log,
            group_alias="data_logger",
            frq_divider=10
        )
        result = self.data_subscription.get()
        if result and result.status == motorcortex.OK:
            self.data_subscription.notify(self._onDataUpdate)
            logging.info(f"Logging {len(self.options.parameters_to_log)} parameters")

    def _onDataUpdate(self, msg) -> None:
        """Update latest values from subscription."""
        data = {}
        for i, param_path in enumerate(self.options.parameters_to_log):
            data[param_path] = msg[i].value[0]
        self.latest_values.set(data)

    def iterate(self) -> None:
        """Log current values to file."""
        values = self.latest_values.get()
        if values:
            log_entry = {
                "timestamp": time.time(),
                "data": values
            }
            self.logged_data.append(log_entry)
            logging.debug(f"Logged: {log_entry}")

        self.wait(self.options.log_interval)

    def onExit(self) -> None:
        """Save logged data to file."""
        if self.data_subscription:
            self.data_subscription.unsubscribe()

        self._saveLogFile()
        logging.info(f"Data logger stopped. {len(self.logged_data)} entries saved.")

    def _saveLogFile(self) -> None:
        """Write logged data to JSON file."""
        try:
            with open(self.options.log_file, 'w') as f:
                json.dump(self.logged_data, f, indent=2)
            logging.info(f"Log saved to {self.options.log_file}")
        except Exception as e:
            logging.error(f"Failed to save log: {e}")

if __name__ == "__main__":
    config = DataLoggerConfiguration(
        target_url="wss://192.168.1.100",
        log_interval=0.5,
        log_file="sensor_data.json",
        parameters_to_log=[
            "root/Sensors/Temperature",
            "root/Sensors/Pressure",
            "root/Sensors/Humidity"
        ]
    )
    # Update the config paths below to match your deployment requirements
    # deployed_config: Path used when DEPLOYED env var is set (on production systems)
    # non_deployed_config: Path used during local development
    config.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/data_logger.json",
        non_deployed_config="config.json"
    )
    app = DataLogger(config)
    app.run()
```

---

## API Reference

This section provides comprehensive documentation for the key APIs used in Motorcortex client applications.

### Robot Control API

#### MotionProgram

**Purpose:** Create and send motion programs to the robot manipulator.

**Import:**

```python
from robot_control.motion_program import MotionProgram, Waypoint
```

**Key Classes:**

**`Waypoint`** - Represents a waypoint in the motion path:

```python
Waypoint(
    pose: list[float],                    # Cartesian [x, y, z, rx, ry, rz] or joint angles
    smoothing_factor: float = 0.1,        # Waypoint smoothing [0..1]
    next_segment_velocity_factor: float = 1.0  # Segment velocity factor [0..1]
)
```

**`MotionProgram`** - Build and send motion programs:

```python
# Initialize
mp = MotionProgram(self.req, self.motorcortex_types)

# Add Linear Motion
mp.addMoveL(
    waypoint_list: list[Waypoint],
    velocity: float = 0.1,              # m/s
    acceleration: float = 0.2,          # m/s²
    rotational_velocity: float = 3.18,  # rad/s
    rotational_acceleration: float = 6.37  # rad/s²
)

# Add Joint Motion
mp.addMoveJ(
    waypoint_list: list[Waypoint],
    rotational_velocity: float = 3.18,  # rad/s
    rotational_acceleration: float = 6.37  # rad/s²
)

# Add Circular Motion
mp.addMoveC(
    waypoint_list: list[Waypoint],
    angle: float,                       # Rotation angle in rad
    velocity: float = 0.1,              # m/s
    acceleration: float = 0.2           # m/s²
)

# Add Wait Command
mp.addWait(
    timeout_s: float,                   # Wait duration in seconds
    path: str = None,                   # Optional parameter to wait for
    value: float = 1                    # Value to compare
)

# Add Set Parameter Command
mp.addSet(
    path: str,                          # Parameter path
    value: float | int | bool           # Value to set
)

# Send Program
mp.send(program_name: str = "Undefined") -> motorcortex.ParameterTree
```

**Example:**

```python
import math
from robot_control.motion_program import MotionProgram, Waypoint

# Create waypoints
home = Waypoint([0.4, 0.0, 0.35, 0, math.pi, 0])
target = Waypoint([0.5, 0.2, 0.1, 0, math.pi, 0])

# Build motion program
mp = MotionProgram(self.req, self.motorcortex_types)
mp.addMoveL([home, target], velocity=0.3, acceleration=0.5)
mp.send("my_program").get()
```

#### RobotCommand

**Purpose:** Control robot state machine (engage, play, stop, etc.)

**Import:**

```python
from robot_control.robot_command import RobotCommand
```

**Initialize:**

```python
robot = RobotCommand(self.req, self.motorcortex_types, system_id=0)
```

**State Control Methods:**

```python
# State transitions
robot.off() -> bool                    # Switch to Off state
robot.disengage() -> bool              # Switch to Disengage state
robot.engage() -> bool                 # Switch to Engage state
robot.acknowledge(timeout_s=20.0) -> bool  # Acknowledge errors

# Mode control
robot.manualCartMode() -> bool         # Manual Cartesian motion
robot.manualJointMode() -> bool        # Manual joint motion
robot.semiAutoMode() -> bool           # Semi-auto mode

# Motion control
robot.moveToPoint(
    target_joint_coord_rad: list[float],
    v_max: float = 0.5,                # rad/s
    a_max: float = 1.0                 # rad/s²
) -> bool

robot.moveToStart(timeout_s: float) -> bool

# Program control
robot.play(wait_time=1.0) -> InterpreterStates
robot.pause(wait_time=1.0) -> InterpreterStates
robot.stop(wait_time=1.0) -> InterpreterStates
robot.reset(wait_time=1.0) -> InterpreterStates

# State query
robot.getState() -> InterpreterStates
```

**Example:**

```python
from robot_control.robot_command import RobotCommand
from robot_control.system_defs import InterpreterStates

robot = RobotCommand(self.req, self.motorcortex_types)

# Engage robot
if robot.engage():
    logging.info("Robot engaged")

# Play program
state = robot.play()
if state == InterpreterStates.MOTION_NOT_ALLOWED_S.value:
    robot.moveToStart(10)
    robot.play()
```

#### System Definitions

**Purpose:** Enums for robot states, modes, and interpreter states.

**Import:**

```python
from robot_control.system_defs import (
    States, StateEvents, Modes, ModeCommands,
    InterpreterStates, InterpreterEvents,
    MotionGeneratorStates, FrameTypes
)
```

**Key Enums:**

**`States`** - Robot state machine states:

- `OFF_S` (1), `DISENGAGED_S` (2), `ENGAGED_S` (4), `ESTOP_OFF_S` (7)

**`InterpreterStates`** - Motion program interpreter states:

- `PROGRAM_STOP_S` (0) - Program stopped
- `PROGRAM_RUN_S` (1) - Program running
- `PROGRAM_PAUSE_S` (2) - Program paused
- `MOTION_NOT_ALLOWED_S` (3) - Motion not allowed
- `PROGRAM_IS_DONE` (200) - Program completed

**`Modes`** - Robot operation modes:

- `PAUSE_M` (1), `AUTO_RUN_M` (2), `MANUAL_JOINT_MODE_M` (3), `MANUAL_CART_MODE_M` (4)

**Example:**

```python
from robot_control.system_defs import InterpreterStates

state = self.robot.getState()
if state == InterpreterStates.PROGRAM_STOP_S.value:
    logging.info("Program is stopped")
```

### Motorcortex Python API

#### Request

**Purpose:** Send requests to Motorcortex server (get/set parameters).

**Key Methods:**

```python
# Get parameter
req.getParameter(path: str) -> Reply
# Returns: Reply with .value attribute

# Set parameter
req.setParameter(
    path: str,
    value: Any,
    type_name: str = None
) -> Reply

# Set multiple parameters
req.setParameterList(param_list: list[dict]) -> Reply
# param_list format: [{"path": "...", "value": ...}, ...]

# Create subscription group
req.createGroup(
    path_list: list[str],
    group_alias: str,
    frq_divider: int = 1
) -> Reply
```

**Example:**

```python
# Get parameter
result = self.req.getParameter("root/Sensors/Temperature").get()
if result and result.status == motorcortex.OK:
    temp = result.value[0]

# Set parameter
self.req.setParameter("root/Control/Speed", 0.5).get()
```

#### Subscription

**Purpose:** Subscribe to real-time parameter updates.

**Key Methods:**

```python
# Subscribe to parameters
sub.subscribe(
    path_list: list[str] | str,
    group_alias: str,
    frq_divider: int = 1
) -> Subscription

# Subscription object methods
subscription.get(timeout_sec=1.0) -> StatusMsg  # Wait for subscription
subscription.notify(callback: Callable) -> None  # Register observer
subscription.read() -> list[Parameter]          # Read latest values
subscription.layout() -> list[str]              # Get parameter paths
subscription.unsubscribe() -> None              # Unsubscribe
```

**Example:**

```python
# Subscribe to parameters
self.sensor_sub = self.sub.subscribe(
    ["root/Sensors/Temperature", "root/Sensors/Pressure"],
    group_alias="sensors",
    frq_divider=100
)

result = self.sensor_sub.get()
if result and result.status == motorcortex.OK:
    self.sensor_sub.notify(self._onSensorUpdate)

def _onSensorUpdate(self, msg):
    temp = msg[0].value[0]
    pressure = msg[1].value[0]
    # Process values...
```

#### ParameterTree

**Purpose:** Represents the parameter tree structure from the server.

**Key Methods:**

```python
# Load parameter tree
parameter_tree.load(parameter_tree_msg)

# Get parameter info
parameter_tree.getInfo(parameter_path: str) -> ParameterInfo
parameter_tree.getDataType(parameter_path: str) -> DataType
parameter_tree.getParameterTree() -> list[ParameterInfo]
```

### McxClientApp Framework

#### McxClientApp

**Base class for main-thread execution.**

**Inherited Attributes:**

```python
self.req                # motorcortex.Request
self.sub                # motorcortex.Subscription
self.parameter_tree     # motorcortex.ParameterTree
self.motorcortex_types  # motorcortex.MessageTypes
self.options            # McxClientAppConfiguration
self.running            # ThreadSafeValue[bool]
self.watchdog           # McxWatchdog
self.errorHandler       # McxErrorHandler
```

**Methods to Override:**

```python
def startOp(self) -> None:
    """Called after connection, before iterate starts."""
    pass

def iterate(self) -> None:
    """Main application logic (called repeatedly)."""
    pass

def onExit(self) -> None:
    """Cleanup before disconnect."""
    pass
```

**Inherited Methods:**

```python
self.wait(timeout: float = 30, testinterval: float = 0.2) -> bool
self.wait_for(param: str, value: object, timeout: float = 30, operat: str = "==") -> bool
self.reset() -> None  # Set running to False
```

#### McxClientAppConfiguration

**Configuration class for client applications.**

**Complete Class Definition:**

```python
import logging
import os
import json
from .state_def import State


def load_config_json(path: str, name: str) -> dict:
    """
    Load and validate configuration JSON from `path`.

    Args:
        path (str): Path to the configuration JSON file.
        name (str): Name of the service to extract configuration for.

    Returns:
        dict: Configuration dictionary for the specified service.
    """
    assert path is not None, "Configuration path must be provided"
    if not os.path.exists(path):
        raise AssertionError(f"[ERROR] Configuration file not found: {path}")

    with open(path, 'r') as f:
        data = json.load(f)

    services_data = data.get("Services", [])
    if services_data is None or type(services_data) is not list or len(services_data) == 0:
        raise ValueError(f"[ERROR] No service data found in deployed configuration file: {path}")

    matched = None
    for service in services_data:
        if service.get("Name", "") == name:
            matched = service
            break
    else:
        raise ValueError(f"[ERROR] No service with name '{name}' found in configuration file: {path}")

    config_data = matched.get("Config", {}) if matched is not None else {}

    if not isinstance(config_data, dict):
        raise ValueError(f"[ERROR] Invalid configuration format in {path}; expected object/dict.")

    return config_data


class McxClientAppConfiguration:
    """
    Configuration options for McxClientApp.

    Attributes:
        name (str): Name of the client application.
        login (str): Username for authenticating with the Motorcortex server.
        password (str): Password for authenticating with the Motorcortex server.
        target_url (str): Local Development WebSocket URL (e.g., 'wss://localhost').
        target_url_deployed (str): Deployed WebSocket URL (default: 'wss://localhost').
        cert (str): Local Development path to SSL certificate (e.g., 'mcx.cert.crt').
        cert_deployed (str): Deployed path to SSL certificate (default: '/etc/ssl/certs/mcx.cert.pem').
        statecmd_param (str): Parameter path for state commands (default: 'root/Logic/stateCommand').
        state_param (str): Parameter path for current state (default: 'root/Logic/state').
        run_during_states (list[State]|None): List of allowed states for iterate() (default None).
        autoStart (bool): Start automatically upon connection (default: True).
        start_button_path (str|None): Custom start button path (default: None).
        enable_watchdog (bool): Enable watchdog functionality (default: True).
        enable_error_handler (bool): Enable error handler functionality (default: True).
        error_reset_param (str): Error reset parameter path (default: 'root/Services/:fromState/resetErrors').

    Note:
        When inheriting, call super().__init__(**kwargs) AFTER setting custom attributes.
    """
    def __init__(
        self,
        name: str,
        login: str | None = None,
        password: str | None = None,
        target_url: str = "wss://localhost",
        target_url_deployed: str = "wss://localhost",
        cert: str = "mcx.cert.crt",
        cert_deployed: str = "/etc/ssl/certs/mcx.cert.pem",
        statecmd_param: str | None = "root/Logic/stateCommand",
        state_param: str | None = "root/Logic/state",
        run_during_states: list = None,
        autoStart: bool = True,
        start_button_path: str | None = None,
        enable_watchdog: bool = True,
        enable_error_handler: bool = True,
        error_reset_param: str = "root/Services/:fromState/resetErrors",
        **kwargs
    ) -> None:
        self.name = name
        self.login = login
        self.password = password
        self.target_url = target_url
        self.target_url_deployed = target_url_deployed
        self.cert = cert
        self.cert_deployed = cert_deployed
        self.statecmd_param = statecmd_param
        self.state_param = state_param
        self._run_during_states = State.list_from(run_during_states)
        self.autoStart = autoStart
        self.start_button_path = start_button_path
        self.enable_watchdog = enable_watchdog
        self.enable_error_handler = enable_error_handler
        self.error_reset_param = error_reset_param

        self.deployed_config: str = "/etc/motorcortex/config/services/services_config.json"
        self.non_deployed_config: str | None = None

        for key, value in kwargs.items():
            setattr(self, key, value)

        self.__has_config = False

    def load_config(self) -> None:
        """Load configuration from the set config paths."""
        if self.is_deployed:
            config_file = self.deployed_config
        else:
            config_file = self.non_deployed_config

        config_data = load_config_json(config_file, name=self.name)
        for key, value in config_data.items():
            if key == "run_during_states":
                self._run_during_states = State.list_from(value)
            elif hasattr(self, key):
                setattr(self, key, value)

        self.__has_config = True
        logging.info(f"Configuration loaded from {'deployed' if self.is_deployed else 'non-deployed'} config file: {config_file}")

    def set_config_paths(self, deployed_config: str | None = None, non_deployed_config: str | None = None) -> None:
        """Set the configuration file paths for deployed and non-deployed environments."""
        if deployed_config is not None:
            self.deployed_config = deployed_config
        if non_deployed_config is not None:
            self.non_deployed_config = non_deployed_config

    @property
    def is_deployed(self) -> bool:
        """Check if running in deployed environment (checks DEPLOYED env var)."""
        return os.environ.get("DEPLOYED", False) is not False

    @property
    def certificate(self) -> str:
        """Get certificate path based on deployment status."""
        return self.cert_deployed if self.is_deployed else self.cert

    @property
    def ip_address(self) -> str:
        """Get target URL based on deployment status."""
        return self.target_url_deployed if self.is_deployed else self.target_url

    @property
    def get_parameter_path(self) -> str:
        """Get parameter path root for the service."""
        return f"root/Services/{self.name}"

    @property
    def get_service_parameter_path(self) -> str:
        """Get service parameter path root."""
        return f"root/Services/{self.name}/serviceParameters"

    @property
    def get_start_button_parameter_path(self) -> str:
        """Get parameter path for start button control."""
        if self.start_button_path is not None:
            if "root/" in self.start_button_path:
                return self.start_button_path
            else:
                return f"{self.get_parameter_path}/{self.start_button_path}"
        return f"{self.get_parameter_path}/enableService"
```

**Key Properties:**

```python
options.get_parameter_path -> str          # "root/Services/{ServiceName}"
options.get_service_parameter_path -> str  # "root/Services/{ServiceName}/serviceParameters"
options.is_deployed -> bool                # True if DEPLOYED env var set
options.certificate -> str                 # Cert path based on deployment
options.ip_address -> str                  # URL based on deployment
```

**Key Methods:**

```python
config.set_config_paths(
    deployed_config: str,
    non_deployed_config: str
)
config.load_config()  # Load from JSON
```

#### Using commandWord for External Commands

**CRITICAL: commandWord is a built-in service parameter** that allows external systems (DESK tool, other services, web interfaces) to send commands to your service.

**Path:** `root/Services/{ServiceName}/commandWord`

**Best Practices:**

✅ **DO:**

- Use ChangeDetector with `trigger_on_zero=False` to monitor commandWord
- Define command values clearly (1=reset, 2=pause, 3=resume, etc.)
- Acknowledge commands by resetting commandWord to 0 after processing
- Document command values in your class/file docstring
- Check for changes in `iterate()`, not in subscription callback

❌ **DON'T:**

- Create custom button parameters when commandWord exists
- Process commands in subscription callback (too fast, wrong thread)
- Forget to reset commandWord to 0 after processing (prevents re-triggering)
- Use `trigger_on_zero=True` for commands (will trigger on acknowledgment)

**Example Pattern:**

```python
class MyService(McxClientApp):
    """
    My Service Application.

    Command Values (via commandWord):
    - 1: Reset counter
    - 2: Pause operation
    - 3: Resume operation
    - 4: Double speed
    """
    def __init__(self, options):
        super().__init__(options)
        self.command_detector = ChangeDetector()

    def startOp(self):
        # Subscribe to commandWord
        self.cmd_sub = self.sub.subscribe(
            [f"{self.options.get_parameter_path}/commandWord"],
            "cmd", frq_divider=10
        ).get()
        self.cmd_sub.notify(lambda msg: self.command_detector.set_value(msg[0].value[0]))

    def iterate(self):
        # Check for commands (ignore changes TO zero)
        if self.command_detector.has_changed(trigger_on_zero=False):
            cmd = self.command_detector.get_value()
            self._process_command(cmd)
            # Acknowledge command
            self.req.setParameter(
                f"{self.options.get_parameter_path}/commandWord", 0
            ).get()

        # Your main logic here
        self.wait(1.0)

    def _process_command(self, cmd: int):
        """Process commandWord values."""
        if cmd == 1:
            self.counter = 0
        elif cmd == 2:
            self.paused = True
        elif cmd == 3:
            self.paused = False
        elif cmd == 4:
            self.speed *= 2
```

**Why This Pattern Works:**

1. **External control** - DESK tool or other systems can send commands by setting commandWord
2. **No custom parameters** - Uses built-in commandWord, no need to define button parameters
3. **Change detection** - Only processes when value actually changes (not every subscription update)
4. **Acknowledgment** - Resetting to 0 allows same command to be sent again
5. **Main thread processing** - Commands handled in iterate(), not subscription callback

#### ChangeDetector

**Thread-safe value change detector for monitoring parameter changes.**

**Purpose:** Detect when a parameter value changes and check for changes in your iterate() loop. Perfect for command words, state changes, or any parameter requiring change detection. Unlike callbacks, this gives you full control over when to check and process changes.

**Import:**

```python
from src.mcx_client_app.ChangeDetector import ChangeDetector
```

**Constructor:**

```python
ChangeDetector()  # No parameters needed
```

**Key Methods:**

```python
detector.set_value() -> None              # Call after updating internal value to check for changes
detector.get_value() -> Any               # Get current value
detector.has_changed(keep: bool = False) -> bool  # Check if value changed (clears flag unless keep=True)
detector.reset() -> None                  # Reset internal state
```

**Complete Usage Example:**

```python
from src.mcx_client_app import McxClientApp
from src.mcx_client_app.ChangeDetector import ChangeDetector
import motorcortex

class MyApp(McxClientApp):
    def __init__(self, options):
        super().__init__(options)
        # Create detector for commandWord parameter
        self.command_detector = ChangeDetector()
        self.command_subscription = None

    def startOp(self):
        # Subscribe to the parameter
        self.command_subscription = self.sub.subscribe(
            [f"{self.options.get_parameter_path}/commandWord"],
            "command_group",
            frq_divider=10
        )
        result = self.command_subscription.get()
        if result and result.status == motorcortex.OK:
            self.command_subscription.notify(self._on_command_update)

    def _on_command_update(self, msg):
        """Callback for commandWord updates (runs in subscription thread)."""
        value = msg[0].value[0]
        # Update detector value (fast operation in subscription thread)
        self.command_detector._ChangeDetector__value.set(value)
        self.command_detector.set_value()

    def iterate(self):
        # Check if commandWord changed and process in main thread
        if self.command_detector.has_changed():
            value = self.command_detector.get_value()
            logging.info(f"Command received: {value}")

            if value == 1:
                logging.info("Reset command received")
                self.reset()
            elif value == 2:
                logging.info("Start command received")
                self.start()
            elif value == 3:
                logging.info("Stop command received")
                self.stop()

        self.wait(0.1)
```

**Use Cases:**

- **Command words**: Multiple command values (1=reset, 2=start, 3=stop)
- **State monitoring**: Detect when states change
- **Configuration changes**: React when settings are updated
- **Multi-value inputs**: Switches with multiple positions

**Important Notes:**

- ✅ **Check changes in iterate()** - Use `has_changed()` to detect changes in main thread
- ✅ **Full control** - You decide when to check and process changes
- ✅ **Thread-safe** - Uses `ThreadSafeValue` internally for cross-thread communication
- ✅ **Simple pattern** - Subscription updates value, iterate() checks for changes
- ⚠️ **Subscription callback is fast** - Only updates internal value, no processing
  **Thread-safe container for sharing data between threads.**

```python
from src.mcx_client_app import ThreadSafeValue

value = ThreadSafeValue(initial_value)
value.set(new_value)    # Thread-safe write
current = value.get()   # Thread-safe read
```

### Client App Examples

Reference implementations in [examples/](examples/) directory:

- [examples/start_button.py](examples/start_button.py) - Start/stop button control
- [examples/robot_app.py](examples/robot_app.py) - Robot motion application
- [examples/custom_button.py](examples/custom_button.py) - Custom button handling with subscriptions
- [examples/error_app.py](examples/error_app.py) - Error handler demonstration
- [examples/datalogger.py](examples/datalogger.py) - Data logging application

---

## Coding Conventions

### Naming Conventions

- **Methods**: `camelCase` (e.g., `moveToPoint`, `addMoveL`, `getParameter`)
- **Classes**: `PascalCase` (e.g., `RobotCommand`, `MotionProgram`, `McxClientApp`)
- **Variables**: `snake_case` (e.g., `motorcortex_types`, `waypoint_list`, `current_temperature`)
- **Private methods**: Prefix with `_` (e.g., `_setupSubscriptions`, `_onButtonPress`)
- **Constants/Enums**: `UPPER_CASE` (e.g., `State.ENGAGED_S`, `MAX_RETRIES`)

### Type Hints

Always use type hints for function parameters and return values:

```python
def processData(self, values: list[float], threshold: float = 10.0) -> bool:
    """Process sensor values against threshold."""
    pass

def _onUpdate(self, msg) -> None:
    """Callback receives motorcortex message (no type hint needed)."""
    pass
```

Use modern Python 3.9+ syntax:

- `list[str]` instead of `List[str]`
- `dict[str, int]` instead of `Dict[str, int]`
- `str | None` instead of `Optional[str]`

### Docstrings

Every public class and method must have a docstring:

```python
def wait_for(self, param: str, value: object, timeout: float = 30,
             operat: str = "==") -> bool:
    """
    Wait for a parameter to meet a condition.

    Args:
        param (str): Parameter path to monitor.
        value (object): Value to compare against.
        timeout (float): Timeout in seconds. Default 30.
        operat (str): Comparison operator ("==", "!=", "<", "<=", ">", ">=", "in").

    Returns:
        bool: True if condition met, False if timeout.

    Raises:
        StopSignal: If stop signal received before condition met.
    """
```

### Error Handling

1. **Check return values** - Many methods return `bool` for success/failure:

```python
if self.robot.engage():
    logging.info("Robot engaged")
else:
    logging.error("Failed to engage robot")
    return
```

2. **Use specific exceptions**:

```python
if not isinstance(speed, float):
    raise TypeError(f"Speed must be float, got {type(speed)}")

if speed < 0:
    raise ValueError(f"Speed must be positive, got {speed}")
```

3. **Handle StopSignal** gracefully:

```python
try:
    self.wait(10)
except StopSignal:
    logging.info("Operation stopped by user")
    # Cleanup here
```

4. **Log errors with context**:

```python
try:
    result = self.req.setParameter(param, value).get()
except Exception as e:
    logging.error(f"Failed to set {param} to {value}: {e}")
```

### Code Structure

1. **Imports at top** - Group by standard library, third-party, local:

```python
# Standard library
import logging
import time
from pathlib import Path

# Third-party
import motorcortex

# Local
from src.mcx_client_app import McxClientApp, McxClientAppConfiguration
from robot_control.robot_command import RobotCommand
```

2. **Class organization**:

```python
class MyApp(McxClientApp):
    """Docstring."""

    def __init__(self, options):
        """Initialize."""
        pass

    # Lifecycle methods
    def startOp(self):
        pass

    def iterate(self):
        pass

    def onExit(self):
        pass

    # Private helper methods (alphabetical)
    def _doSomething(self):
        pass

    def _onCallback(self, msg):
        pass
```

3. **Keep methods focused** - One responsibility per method, max ~30 lines

### Best Practices Summary

✅ **DO:**

- Use descriptive variable names (`current_temperature` not `temp`)
- Extract logic into private helper methods
- Use subscriptions for real-time data
- Check return values and handle errors
- Log important events at INFO level
- Log detailed data at DEBUG level
- Use `self.wait()` instead of `time.sleep()`
- Unsubscribe in `onExit()`
- Use `ThreadSafeValue` for shared data between threads

❌ **DON'T:**

- Poll parameters in `iterate()` - use subscriptions
- Block in subscription callbacks
- Access `self.req` or `self.sub` before connection
- Initialize in `iterate()` - use `__init__()` or `startOp()`
- Use `time.sleep()` - use `self.wait()`
- Create new subscriptions in `iterate()`
- Ignore return values from robot commands
- Leave subscriptions active after exit

---

## Code Generation servicesdelines for AI Agents

When asked to create an mcx-client-app:

1. **Ask clarifying questions** if the user's intent is unclear:
   - What should the app do? (monitor, control, automate, log)
   - What parameters to interact with?
   - Should it use start/stop button or state-based execution?
   - Any custom configuration needed?

2. **Start with the simplest solution**:
   - Use `McxClientApp` unless threading is explicitly needed
   - Use built-in `McxClientAppConfiguration` unless custom parameters needed
   - Keep `iterate()` focused and delegate to helper methods

3. **Follow the structure**:
   - Custom configuration class (if needed)
   - Main application class inheriting from `McxClientApp` or `McxClientAppThread`
   - Lifecycle methods: `__init__`, `startOp`, `iterate`, `onExit`
   - Private helper methods for logic
   - Subscription callbacks
   - Main block with configuration and `app.run()`

4. **Include comprehensive docstrings** - Other AI agents will read your code

5. **Add logging** at key points for debugging

6. **Handle errors gracefully** with try/except and logging

7. **Show config.json example** with required parameters

8. **Explain what the app does** in comments

---

**Remember:** The goal is to create clean, maintainable, production-ready code that other developers (and AI agents) can understand and modify easily. Always double-check for mistakes and avoid duplicating functions or classes that already exist.

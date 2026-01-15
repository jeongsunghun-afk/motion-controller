
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
8. [Keep iterate() Clean - Best Practices](#keep-iterate-clean---best-practices)
9. [Complete Working Examples](#complete-working-examples)
10. [API Reference](#api-reference)
11. [Coding Conventions](#coding-conventions)

---

## How Client Apps Interact with Motorcortex

MCX-Client-Apps connect to a **Motorcortex server on a Target** via WebSocket (e.g., `wss://192.168.1.100`) and interact with the **parameter tree** - a hierarchical structure with existing Motorcortex parameters (like `root/AGVControl/actualVelocityLocal`, `root/Sensors/Temperature`) and user-defined parameters under `root/UserParameters/` (like `root/UserParameters/services/StartButton`).

**Operations:** Read with `self.req.getParameter()`, write with `self.req.setParameter()`, subscribe for real-time updates with `self.sub.subscribe()`.

### Adding Custom Parameters

**CRITICAL:** All custom client-app parameters **MUST** be under `root/UserParameters/...` - NEVER directly under `root/`!

**IMPORTANT:** Only add parameters for **client-app-specific** controls (buttons, counters, settings). If a parameter path is provided like `root/AGVControl/actualVelocityLocal` or `root/Sensors/Temperature`, these **already exist** in the Motorcortex application's parameter tree - just read/subscribe to them directly. Do NOT document them as "required parameters".

When your app needs **new UserParameters** that don't exist on the Target, **document them at the top of your file** so users know what to add to `parameters.json` in the Motorcortex application's `config/user` folder. These parameters are **always** placed under `root/UserParameters/...` in the tree.

### UserParameters vs McxClientAppConfiguration

**Critical distinction:**

**UserParameters (in parameter tree):**
- ✅ Use for values that **change during runtime** (buttons, setpoints, thresholds that users adjust)
- ✅ Can be modified via DESK tool or other clients while app is running
- ✅ Access with `self.req.getParameter()` or `self.sub.subscribe()`
- ✅ Changes take effect immediately
- Example: `{"Name": "MaxSpeed", "Type": "double, input"}` in UserParameters

**McxClientAppConfiguration (in config.json):**
- ✅ Use for values that are **set once at startup** and remain constant
- ✅ Cannot be changed while app is running (requires restart)
- ✅ Access via `self.options.connection_timeout`
- ✅ Simpler, faster access (no network calls)
- Example: `{"connection_timeout": 30}` in config.json

**Decision servicesde:**
```python
# ❌ WRONG: Static configuration in UserParameters when it never changes at runtime
# (Adds unnecessary complexity and network overhead)
{
  "Name": "Configuration",
  "Children": [
    {"Name": "LogFilePath", "Type": "string, parameter", "Value": "/var/log/app.log"}
  ]
}
# Then reading it with: self.req.getParameter("root/UserParameters/Configuration/LogFilePath")

# ✅ CORRECT: Static configuration in config.json
# config.json: {"log_file_path": "/var/log/app.log", "connection_timeout": 30}
# Access: self.options.log_file_path

# ✅ CORRECT: Runtime-adjustable parameter in UserParameters
{"Name": "VelocityThresholds", "Type": "double[6], parameter", "Value": [0.2, 0.4, 0.6, 0.8, 1.0, 1.5]}
# User can change thresholds in DESK tool, app responds immediately via subscription
```

**Required Docstring Format:**

```python
"""
MCX-Client-App: Robot Controller

REQUIRED PARAMETERS:
Add this to the end of the parameters.json file in the config/user folder:

{
  "Name": "services",
  "Children": [
    {
      "Name": "RobotController",
      "Children": [
        {
          "Name": "StartButton",
          "Type": "bool, input",
          "Value": 0
        },
        {
          "Name": "CycleCounter",
          "Type": "int, parameter_volatile",
          "Value": 0
        },
        {
          "Name": "TargetSpeed",
          "Type": "double, parameter",
          "Value": 0.5
        }
      ]
    }
  ]
}

SETUP: 1) Add JSON above to parameters.json, 2) Restart Motorcortex, 3) Verify in DESK tool

CONFIG FILE DEPLOYMENT (NEEDED WHEN YOU DEPLOY THE APP AS A DEBIAN PACKAGE):
To deploy the config.json file through the Motorcortex portal:
1. In the portal, navigate to your .conf folder (Configuration Files section)
2. Create a 'services' folder if it doesn't exist yet
3. Create a file named 'robot_controller.json' (use lowercase with underscores)
4. Paste your config.json content into this file:
   {
       "login": "admin",
       "password": "your_password",
       "target_url": "wss://localhost",
       "cert": "mcx.cert.crt",
       "run_during_states": [],
       "custom_field_1": "value1",
       "custom_field_2": 123
   }
5. In your code, configure the deployed config path:
   config.set_config_paths(
       deployed_config="/etc/motorcortex/config/services/robot_controller.json",
       non_deployed_config="config.json"
   )
"""

import logging
from src.mcx_client_app import McxClientApp
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

**IMPORTANT:** Always store parameter paths in your custom `McxClientAppConfiguration` class so they can be configured in `config.json`. **Never hardcode parameter paths** directly in `getParameter()` or `setParameter()` calls.

✅ **CORRECT - Configurable parameter paths:**
```python
class MyAppConfiguration(McxClientAppConfiguration):
    """Configuration with parameter paths that can be changed in config.json."""
    def __init__(
        self,
        start_button_param: str = "root/UserParameters/services/MyApp/StartButton",
        counter_param: str = "root/UserParameters/services/MyApp/Counter",
        velocity_param: str = "root/AGVControl/actualVelocityLocal",
        **kwargs
    ):
        self.start_button_param = start_button_param
        self.counter_param = counter_param
        self.velocity_param = velocity_param
        super().__init__(**kwargs)

class MyApp(McxClientApp):
    def __init__(self, options: MyAppConfiguration):
        super().__init__(options)
        self.options: MyAppConfiguration  # Type hint
    
    def iterate(self):
        # ✅ Use self.options.parameter_name - configurable via config.json
        value = self.req.getParameter(self.options.start_button_param).get().value[0]
        self.req.setParameter(self.options.counter_param, 42).get()
```

**config.json:**
```json
{
    "login": "",
    "password": "",
    "target_url": "wss://192.168.1.100",
    "cert": "mcx.cert.crt",
    "start_button_param": "root/UserParameters/services/CustomApp/StartButton",
    "counter_param": "root/UserParameters/services/CustomApp/Counter",
    "velocity_param": "root/AGVControl/actualVelocityLocal"
}
```

❌ **WRONG - Hardcoded parameter paths:**
```python
def iterate(self):
    # ❌ Hardcoded paths - cannot be changed without modifying code!
    value = self.req.getParameter("root/UserParameters/services/StartButton").get().value[0]
    self.req.setParameter("root/UserParameters/services/Counter", 42).get()
```

**Parameter Access Patterns:**

```python
# Read parameter (any type) - use self.options.param_name
value = self.req.getParameter(self.options.start_button_param).get().value[0]

# Write parameter (only works on "input" and "parameter" types!)
self.req.setParameter(self.options.counter_param, 42).get()  # ✅ OK if Counter is "input"
self.req.setParameter(self.options.status_param, "ready").get()  # ❌ FAILS if Status is "output"

# Array parameter
speeds = self.req.getParameter(self.options.speeds_param).get().value
# Returns: [0.1, 0.2, 0.3, ...]

# Subscribe for real-time updates - use self.options.param_name
self.sub.subscribe([self.options.start_button_param], group_alias="btn").get().notify(self._onButtonChange)
```

**Why This Matters:**
- ✅ Users can customize parameter paths in `config.json` without editing code
- ✅ Makes apps reusable across different Motorcortex configurations
- ✅ Easier to maintain and test with different parameter structures
- ✅ Follows configuration best practices
- **`parameter`**: Configuration values (writable but typically set once during setup)

### Example: Complete Documentation

```python
"""
MCX-Client-App: Pick and Place Robot Controller

REQUIRED PARAMETERS:
Add this to the end of the parameters.json file in the config/user folder 
of the Motorcortex Anthropomorphic Robot application:

{
  "Name": "services",
  "Children": [
    {
      "Name": "PickPlaceController",
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

INSTRUCTIONS: Add JSON to config/user/parameters.json in Motorcortex app, restart, verify in DESK tool.
"""

# Read parameter:  self.req.getParameter("root/UserParameters/services/PickPlaceController/StartButton").get().value[0]
# Write parameter: self.req.setParameter("root/UserParameters/services/PickPlaceController/CycleCounter", 42).get()
# Subscribe:       self.sub.subscribe(["root/UserParameters/services/PickPlaceController/..."], "alias").get().notify(callback)
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
     "PYTHON_SCRIPT": "my_new_script.py",  // ← Update when renaming mcx-client-app.py
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
     "my_custom_field": 123  // ← Add your custom fields here
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
```

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
self.wait(timeout: float = 30, testinterval: float = 0.2, block_stop_signal: bool = False) -> bool
# Wait for timeout seconds, checking for stop signal. Raises StopSignal when stopped.

self.wait_for(param: str, value: object, index: int = 0, timeout: float = 30, 
              testinterval: float = 0.2, operat: str = "==", block_stop_signal: bool = False) -> bool
# Wait for parameter to meet condition. Raises StopSignal when stopped.
# Operators: "==", "!=", "<", "<=", ">", ">=", "in"

self.reset() -> None
# Set running flag to False (stops the iterate loop)
```

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

**Update config.json with your custom fields:**
```json
{
    "login": "",
    "password": "",
    "target_url": "wss://192.168.1.100",
    "cert": "mcx.cert.crt",
    "speed": 0.8,
    "cycle_count": 20
}
```

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
        # Set initial parameter values
        try:
            self.req.setParameter("root/Operations/Counter", 0).get()
            logging.info("Counter parameter initialized.")
        except Exception as e:
            logging.error(f"Failed to initialize counter: {e}")
        
        # Setup subscriptions (see Subscription Patterns section)
        self._setupSubscriptions()
    
    def iterate(self) -> None:
        """
        Main application logic - called repeatedly while running.
        Keep this method clean and focused (see Best Practices section).
        """
        # Your main logic here
        self.counter += 1
        logging.info(f"Iteration {self.counter}")
        
        # Use self.wait() to allow stop signal checking
        self.wait(1.0)  # Wait 1 second
    
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

**Minimal config.json:**
```json
{
    "login": "",
    "password": "",
    "target_url": "wss://localhost",
    "cert": "mcx.cert.crt"
}
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

Monitor a Motorcortex parameter as a start/stop button:

```python
config = MyAppConfiguration(
    target_url="wss://192.168.1.100",
    start_stop_param="root/UserParameters/services/PythonScript01/StartButton",
)
```

When the parameter is non-zero, `iterate()` runs. When zero, it stops.

**Combining both:**
```python
config = MyAppConfiguration(
    run_during_states=[State.ENGAGED_S],
    start_stop_param="root/UserParameters/services/StartButton",
)
# iterate() runs only when state is ENGAGED AND start_stop_param is non-zero
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

| Scenario | Use | Reason |
|----------|-----|--------|
| Sequential steps with waits | `McxClientApp` | Simple, clear flow |
| Robot motion programs | `McxClientApp` | Sequential motion commands |
| Data logging every N seconds | `McxClientApp` | Simple periodic task |
| Long computation | `McxClientAppThread` | Can stop mid-computation |
| Real-time monitoring | `McxClientAppThread` | Independent monitoring |
| Complex state machines | `McxClientApp` | Easier to debug |

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

### Rule 4: Initialize Data in __init__, Not iterate()

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
        self.req.setParameter("root/Operations/Counter", 0).get()
        logging.info("Counter initialized")
    
    def iterate(self) -> None:
        """Increment counter every second."""
        self.counter += 1
        self.req.setParameter("root/Operations/Counter", self.counter).get()
        logging.info(f"Counter: {self.counter}")
        self.wait(1)
    
    def onExit(self) -> None:
        """Log final count."""
        logging.info(f"Exiting. Final count: {self.counter}")

if __name__ == "__main__":
    config = McxClientAppConfiguration()
    # Update the config paths below to match your deployment requirements
    # deployed_config: Path used when DEPLOYED env var is set (on production systems)
    # non_deployed_config: Path used during local development
    config.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/counter_app.json",
        non_deployed_config="config.json"
    )
    config.start_stop_param = "root/UserParameters/services/StartButton"
    app = CounterApp(config)
    app.run()
```

### Example 2: Temperature Monitor with Alarm

```python
import logging
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
    config = McxClientAppConfiguration()
    # Update the config paths below to match your deployment requirements
    # deployed_config: Path used when DEPLOYED env var is set (on production systems)
    # non_deployed_config: Path used during local development
    config.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/temperature_monitor.json",
        non_deployed_config="config.json"
    )
    app = TemperatureMonitor(config)
    app.run()
```

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
```

### Example 4: Data Logger with Custom Configuration

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

### API Reference for `.github/stubs` Folder

**ALWAYS consult the stub files for detailed type information and docstrings.**

#### Robot Control API

Use type stubs in [stubs/robot_control/](stubs/robot_control/):
- [motion_program.pyi](stubs/robot_control/motion_program.pyi) - Create motion programs (MoveL, MoveJ, MoveC, etc.)
- [robot_command.pyi](stubs/robot_control/robot_command.pyi) - Robot control commands (engage, play, stop, etc.)
- [system_defs.pyi](stubs/robot_control/system_defs.pyi) - System definitions and states

Examples in [stubs/robot_control/examples/](stubs/robot_control/examples/)

#### Motorcortex Python API

Use type stubs in [stubs/motorcortex/](stubs/motorcortex/):
- [request.pyi](stubs/motorcortex/request.pyi) - Get/set parameters
- [subscription.pyi](stubs/motorcortex/subscription.pyi) - Subscribe to parameter updates
- [parameter_tree.pyi](stubs/motorcortex/parameter_tree.pyi) - Parameter tree structure

Examples in [stubs/motorcortex/examples/](stubs/motorcortex/examples/)

#### Client App Examples

Reference implementations in [stubs/clientApp/Examples/](stubs/clientApp/Examples/):
- [start_button.py](stubs/clientApp/Examples/start_button.py) - Start/stop button control
- [robot_app.py](stubs/clientApp/Examples/robot_app.py) - Robot motion application
- [custom_button.py](stubs/clientApp/Examples/custom_button.py) - Custom button handling

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
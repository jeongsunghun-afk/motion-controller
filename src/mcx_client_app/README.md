
# mcx_client_app Python Package

This package provides the main application logic for building Motorcortex client applications in Python. It enables robust communication, state management, and automation for Motorcortex-based robotic and industrial systems.

## Overview

The package provides two main classes for building Motorcortex client applications:

1. **`MCxClientApp`** - Base class that runs actions in the main thread
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
- Connect to Motorcortex servers using secure WebSocket and certificate authentication
- Monitor and control robot/system state via parameter tree
- Send state commands and handle start/stop logic
- Run custom automation routines with safe engagement/disengagement
- Support for external start/stop control via parameter subscription
- Extensible via inheritance - override methods for custom behavior
- Built-in stop signal handling for safe interruption of running operations
- Graceful keyboard interrupt (Ctrl+C) handling with proper cleanup
- Thread-safe value container for cross-thread communication

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

### `MCxClientApp`
Base client class that runs the `action()` method in the main thread. Use this when you want simple, sequential execution without threading complexity.

### `McxClientAppThread`
Derived class that runs the `action()` method in a separate thread while the main thread monitors start/stop signals. Use this when you need concurrent execution or when actions should run independently of signal monitoring.

### `ThreadSafeValue[T]`
Generic thread-safe single-value container for cross-thread communication.
- `__init__(initial_value: T)`: Initialize with a value
- `set(value: T)`: Set a new value (thread-safe)
- `get() -> T`: Get the current value

**Key Methods (both classes):**
- `connect()`: Establishes WebSocket connection to Motorcortex server
- `wait_for(param, value, ...)`: Polls a parameter until it matches a condition or timeout/stop signal occurs
- `wait(timeout, ...)`: Waits for a specified duration, interruptible by stop signal
- `engage()`: Commands system to ENGAGED state and blocks until transition completes
- `disengage()`: Commands system to OFF state and blocks until transition completes
- `run()`: Main execution loop - handles full lifecycle
- `reset()`: Resets the internal running flag to False

**Methods to Override:**
- `action()`: Main action loop (called repeatedly while running) - **Required**
- `startOp()`: Called after connection but before engagement - Optional
- `onExit()`: Called before disconnecting - Optional

**Internal State:**
- `_running`: ThreadSafeValue[bool] indicating whether the action should continue running
  - Set to `True` when `start_stop_param` is not configured (always running mode)
  - Automatically updated when `start_stop_param` changes (via background thread subscription)
  - Checked by `wait()` and `wait_for()` methods to raise `StopSignal` when `False`

## Usage Examples

### Example 1: Basic Usage (Inheritance Pattern)

```python
from mcx_client_app import MCxClientApp, McxClientAppOptions

class MyApp(MCxClientApp):
    """Simple application running in main thread."""
    
    def action(self) -> None:
        """Main action loop."""
        print("Running custom action...")
        self.wait(2)  # Wait for 2 seconds

options = McxClientAppOptions(
    login="admin",
    password="vectioneer",
    target_url="wss://192.168.2.100",
    start_stop_param="root/UserParameters/GUI/PythonScript01/StartStop"
)

app = MyApp(options)
app.run()
```

### Example 2: Threaded Execution

```python
from mcx_client_app import McxClientAppThread, McxClientAppOptions

class MyThreadedApp(McxClientAppThread):
    """Application running action in separate thread."""
    
    def action(self) -> None:
        """Runs in separate thread."""
        print("Running in thread...")
        self.wait(1)

app = MyThreadedApp(options)
app.run()  # Main thread monitors signals, action runs in separate thread
```

## Method Reference

### `connect()`
Establishes connection to the Motorcortex server using credentials and certificate from options.
- Creates `req` (Request) and `sub` (Subscription) objects for parameter operations
- Enables auto-reconnect on connection loss
- Raises exception if connection fails

### `wait_for(param, value, index=0, timeout=30, testinterval=0.2, operat="==", block_stop_signal=False)`
Polls a parameter at regular intervals until a condition is met.

**Parameters:**
- `param`: Parameter path to monitor (e.g., `"root/Logic/state"`)
- `value`: Target value to compare against
- `index`: Array index for parameters with multiple values (default: 0)
- `timeout`: Maximum wait time in seconds; -1 or 0 for infinite (default: 30)
- `testinterval`: Polling interval in seconds (default: 0.2)
- `operat`: Comparison operator: `"=="`, `"!="`, `"<"`, `"<="`, `">"`, `">="` (default: `"=="`)
- `block_stop_signal`: If `True`, ignores stop signals and continues waiting (default: `False`)

**Returns:** `True` if condition met, `False` if timeout occurred

**Raises:** `StopSignal` if stop signal received and `block_stop_signal=False`

### `wait(timeout=30, testinterval=0.2, block_stop_signal=False)`
Waits for a specified duration, checking for stop signals at regular intervals.

**Parameters:**
- `timeout`: Wait duration in seconds; -1 or 0 for infinite (default: 30)
- `testinterval`: Interval to check for stop signals in seconds (default: 0.2)
- `block_stop_signal`: If `True`, ignores stop signals (default: `False`)

**Returns:** `True` if full timeout elapsed, `False` if timeout occurred

**Raises:** `StopSignal` if stop signal received and `block_stop_signal=False`

### `engage()`
Commands the system to transition to ENGAGED state and waits until the transition completes.
- Sends `GOTO_ENGAGED_E` command to `statecmd_param`
- Blocks until `state_param` equals `ENGAGED_S`
- Stop signals are **blocked** during engagement for safety

### `disengage()`
Commands the system to transition to OFF state and waits until the transition completes.
- Sends `GOTO_OFF_E` command to `statecmd_param`
- Blocks until `state_param` equals `OFF_S`
- Stop signals are **blocked** during disengagement for safety

### `run()`
Main execution loop that orchestrates the complete application lifecycle.

**Execution Flow:**
1. Calls `connect()` to establish connection
2. Calls `startOp()` for initialization
3. If `start_stop_param` is configured:
   - Sets it to 0 (stopped)
   - Subscribes to parameter changes (monitored in background thread)
4. Calls `engage()` to enter ENGAGED state
5. Enters infinite loop:
   - If `start_stop_param` configured, waits for it to become non-zero
   - Sets `_running = True`
   - **MCxClientApp**: Repeatedly calls `action()` in main thread while `_running=True`
   - **McxClientAppThread**: Starts `action()` in separate thread, main thread monitors `_running`
6. When stop signal received (keyboard interrupt or `_running=False`):
   - Stops action execution
   - Calls `disengage()` to safely stop (skips wait on keyboard interrupt)
   - Calls `onExit()` for cleanup
   - Closes connections and exits

**Keyboard Interrupt Handling:**
- Pressing Ctrl+C triggers graceful shutdown
- Sets `_running = False` to stop action
- Sends disengage command and waits for robot to reach OFF state
- All cleanup operations are protected with error handling
- Threads are given 5 seconds to stop before forceful termination

### `reset()`
Resets the `_running` flag to `False`.
- Used internally when stop signals are detected
- You typically don't need to call this directly

## Advanced Usage

### Lifecycle Methods (Override Pattern)
Three methods provide hooks into different stages of the application lifecycle:

1. **`__init__()`**:
   - Override to add custom attributes to your app
   - Always call `super().__init__(options)` first
   
2. **`startOp()`**:
   - Called after connection but before engagement
   - Use to set parameters, load configurations, or perform pre-engagement setup
   - Override in your subclass

3. **`onExit()`**:
   - Called in the `finally` block before disconnection
   - Use for cleanup, saving state, or logging final status
   - Override in your subclass

**Example:**
```python
class CustomApp(MCxClientApp):
    def __init__(self, options):
        super().__init__(options)
        self.counter = 0
        self.data = []
    
    def startOp(self):
        self.req.setParameter("root/Config/Mode", 1).get()
    
    def action(self):
        self.counter += 1
        self.data.append(self.counter)
        self.wait(1)
    
    def onExit(self):
        print(f"Exiting after {self.counter} cycles")
        print(f"Collected {len(self.data)} data points")
```

### Start/Stop Control Modes

**Automatic Mode** (`start_stop_param=None`, default):
- Application runs continuously once engaged
- `_running` is always `True`
- Stop only via `StopSignal` in your action callback

**Manual Mode** (`start_stop_param` configured):
- Application waits for external start signal (parameter becomes non-zero)
- Background thread monitors parameter changes
- When parameter set to 0, `_running` becomes `False`, triggering `StopSignal`
- Automatically disengages, waits for next start signal, and re-engages

**Important:** When using `start_stop_param`, the parameter is monitored in a separate thread. Changes to this parameter instantly affect the `_running` flag, allowing immediate interruption of your action callback.

## Exception Handling

### `StopSignal`
Raised when a stop signal is received (i.e., `_running` becomes `False`).

**When raised:**
- During `wait()` or `wait_for()` calls when `_running=False` and `block_stop_signal=False`
- Triggers safe disengagement in the `run()` loop

**Handling:**
- Automatically caught by `run()` method - no need to handle in your action callback
- If you catch it manually, ensure you don't block the disengagement process

**Triggering conditions:**
- `start_stop_param` set to 0 (in manual mode)
- Custom logic in your `action_callback` that sets `_running=False` (though not recommended)

### State Commands and States

The module provides dictionaries for robot state control:

**`stateCommand` dictionary:**
```python
"GOTO_OFF_E": 0          # Transition to OFF state
"GOTO_IDLE_E": 1         # Transition to IDLE state
"GOTO_ENGAGED_E": 2      # Transition to ENGAGED state
"GOTO_REFERENCING_E": 4  # Transition to REFERENCING state
"FORCE_IDLE_E": 10       # Force IDLE state
"EMERGENCY_STOP_E": 20   # Trigger emergency stop
"ACKNOWLEDGE_ERROR": 255 # Acknowledge and clear errors
```

**`state` dictionary:**
```python
"OFF_S": 1              # System is off
"IDLE_S": 2             # System is idle (powered but not moving)
"ENGAGED_S": 4          # System is engaged (ready for motion)
"HOMING_S": 5           # System is homing/referencing
"ESTOP_OFF_S": 7        # Emergency stop active
# ... transition states and others
```

**Usage example:**
```python
# Send custom state command
app.req.setParameter(app.options.statecmd_param, stateCommand["GOTO_IDLE_E"]).get()

# Wait for specific state
app.wait_for(app.options.state_param, state["IDLE_S"], block_stop_signal=True)
```

## Complete Examples

### Example 1: Basic Continuous Operation
```python
from mcx_client_app import MCxClientApp, McxClientAppOptions

class MyApp(MCxClientApp):
    """Runs continuously while engaged."""
    
    def action(self):
        print("Running cycle...")
        self.wait(1)  # Wait 1 second between cycles

options = McxClientAppOptions(
    login="",
    password="",
    target_url="",
    cert="mcx.cert.crt"
)

app = MyApp(options)
app.run()
```

### Example 2: Full Customization with All Lifecycle Methods
```python
from mcx_client_app import MCxClientApp, McxClientAppOptions

class FullCustomApp(MCxClientApp):
    """Application with full lifecycle customization."""
    
    def __init__(self, options):
        super().__init__(options)
        self.custom_attr = "Initialized!"
        self.cycle_count = 0
        print(f"Created app with custom attribute: {self.custom_attr}")
    
    def startOp(self):
        """Set parameters before engagement."""
        self.req.setParameter("root/Operations/StartOperation", 1).get()
        self.req.setParameter("root/UserParameters/Speed", 100.0).get()
        print("Start operation configured.")
    
    def action(self):
        """Main automation logic."""
        self.cycle_count += 1
        print(f"Cycle {self.cycle_count}: Running automation...")
        self.wait(2)
    
    def onExit(self):
        """Cleanup before disconnection."""
        print(f"Exiting after {self.cycle_count} cycles.")
        self.req.setParameter("root/Operations/StartOperation", 0).get()

options = McxClientAppOptions(
    login="",
    password="",
    target_url="",
    cert="mcx.cert.crt",
    start_stop_param="root/UserParameters/GUI/PythonScript01/StartStop"
)

app = FullCustomApp(options)
app.run()
```

### Example 3: Using Manual Start/Stop Control
```python
from mcx_client_app import McxClientAppThread, McxClientAppOptions

class MonitorApp(McxClientAppThread):
    """Action that can be started/stopped externally (runs in thread)."""
    
    def action(self):
        position = self.req.getParameter("root/Robot/Position").get().value[0]
        print(f"Current position: {position}")
        self.wait(0.5)  # Check every 500ms

options = McxClientAppOptions(
    login="",
    password="",
    target_url="",
    cert="mcx.cert.crt",
    start_stop_param=""
)

app = MonitorApp(options)
app.run()

# User sets start_stop_param to 1 to start
# User sets start_stop_param to 0 to stop
# Application automatically engages/disengages on start/stop
```

### Example 4: Waiting for Conditions
```python
from mcx_client_app import MCxClientApp, McxClientAppOptions

class PositionWaitApp(MCxClientApp):
    """Wait for robot to reach target position."""
    
    def action(self):
        target = 1000.0
        self.req.setParameter("root/Robot/TargetPosition", target).get()
        
        # Wait for position to reach target (within tolerance)
        reached = self.wait_for(
            param="root/Robot/Position",
            value=target,
            timeout=10,
            operat="==",
            block_stop_signal=False
        )
        
        if reached:
            print("Target reached!")
        else:
            print("Timeout - target not reached")
        
        self.wait(1)

options = McxClientAppOptions(
    login="",
    password="",
    target_url=""
)

app = PositionWaitApp(options)
app.run()
```

### Example 5: Thread-Safe Communication
```python
from mcx_client_app import McxClientAppThread, McxClientAppOptions, ThreadSafeValue

class ToolPoseMonitor(McxClientAppThread):
    """Monitor tool pose with thread-safe value storage."""
    
    def __init__(self, options):
        super().__init__(options)
        self.tool_pose: ThreadSafeValue[list[float]] = ThreadSafeValue([0, 0, 0, 0, 0, 0])
    
    def startOp(self):
        """Subscribe to tool pose updates."""
        subscription = self.sub.subscribe(
            'root/ManipulatorControl/manipulatorToolPoseActual',
            "ToolPoseGroup",
            frq_divider=1000
        )
        subscription.notify(lambda msg: self.tool_pose.set(msg[0].value))
    
    def action(self):
        """Print current tool pose from thread-safe storage."""
        pose = self.tool_pose.get()
        print(f"Tool pose: {pose}")
        self.wait(1)

options = McxClientAppOptions(
    login="",
    password="",
    target_url="",
    start_stop_param="root/UserParameters/GUI/PythonScript01/StartStop"
)

app = ToolPoseMonitor(options)
app.run()
```

## Common Patterns

### Pattern 1: Single Execution (Run Once and Exit)
```python
class OneTimeApp(MCxClientApp):
    """Runs once then stops."""
    
    def action(self):
        print("Performing single task...")
        self.wait(5)
        self._running.set(False)  # Trigger stop after completion
        # Note: This will raise StopSignal on next wait() call
```

### Pattern 2: Conditional Loop
```python
class CountedApp(MCxClientApp):
    """Runs until a condition is met."""
    
    def __init__(self, options):
        super().__init__(options)
        self.cycles = 0
    
    def action(self):
        if self.cycles >= 10:  # Stop after 10 cycles
            self._running.set(False)
            return
        
        print(f"Cycle {self.cycles}")
        self.wait(1)
        self.cycles += 1
```

### Pattern 3: Monitoring with Alerts
```python
class TemperatureMonitor(MCxClientApp):
    """Monitor a parameter and alert on threshold."""
    
    def action(self):
        temperature = self.req.getParameter("root/Sensor/Temperature").get().value[0]
        
        if temperature > 80.0:
            print(f"WARNING: Temperature high: {temperature}°C")
            # Trigger alert parameter
            self.req.setParameter("root/Alerts/HighTemp", 1).get()
        
        self.wait(0.1)  # Check every 100ms
```

## Troubleshooting

### Connection Issues
- Verify `target_url` is correct (e.g., `wss://192.168.2.100`)
- Check certificate path exists and is valid
- Ensure credentials are correct
- Check network connectivity to Motorcortex server

### Stop Signal Not Working
- Ensure `action_callback` calls `wait()` or `wait_for()` regularly
- Check that `block_stop_signal=False` (default)
- Verify `start_stop_param` is set correctly if using manual mode

### Application Doesn't Start
- If using `start_stop_param`, check that parameter exists on server
- Verify parameter is set to non-zero value to trigger start
- Check logs for connection or engagement errors

### Action Callback Not Running
- Ensure `engage()` completes successfully (check system state)
- If using manual mode, verify `start_stop_param` is set to 1
- Check for exceptions in `action_callback` (will trigger disengagement)

## Choosing Between MCxClientApp and McxClientAppThread

### Use `MCxClientApp` (Main Thread) when:
- You have simple, sequential logic
- You don't need concurrent execution
- You want simpler code without threading complexity
- Your action completes quickly and returns

### Use `McxClientAppThread` (Separate Thread) when:
- You need the main thread to remain responsive
- Your action has long-running operations
- You want cleaner separation between signal monitoring and action execution
- You're working with subscriptions that update shared state (use `ThreadSafeValue`)

## Best Practices

1. **Always use `wait()` or `wait_for()` in action()** to enable stop signal detection
2. **Keep action() execution time reasonable** - it's called repeatedly in a loop
3. **Use `startOp()` for one-time setup** rather than in `action()`
4. **Handle errors gracefully** - uncaught exceptions will trigger disengagement
5. **Use `block_stop_signal=True` sparingly** - only when you need uninterruptible operations
6. **Test stop signal behavior** before deploying to production
7. **Log important state changes** for debugging and monitoring
8. **Use `ThreadSafeValue[T]` for cross-thread communication** when using `McxClientAppThread` or subscriptions
9. **Always call `super().__init__(options)`** when overriding `__init__()`
10. **Press Ctrl+C to safely exit** - the app will disengage and clean up properly

## Import Statement

```python
from mcx_client_app import McxClientApp, McxClientAppThread, McxClientAppOptions, StopSignal, ThreadSafeValue

# Recommended imports:
from mcx_client_app import McxClientApp          # Base class (main thread)
from mcx_client_app import McxClientAppThread    # Threaded version
from mcx_client_app import McxClientAppOptions   # Configuration
from mcx_client_app import ThreadSafeValue       # Thread-safe container
from mcx_client_app import StopSignal            # Exception for stop signals
```

---
For more details, see the docstrings in `app.py`.

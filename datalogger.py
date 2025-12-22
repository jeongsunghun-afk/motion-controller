"""
For this example the basic Motorcortex Anthropomorphic Robot application is used. 
You can download it from the Motorcortex Store. 
Make sure to have the Motorcortex Anthropomorphic Robot application running and that you can connect to it using the DESK-Tool.

This example implements a data logger client application that subscribes to multiple parameters
and logs their values to a CSV file in a thread-safe manner. The data is collected in the subscription
callback and saved to the file in the action thread to avoid blocking the subscription thread.
"""
#
#   Developer : Coen Smeets (Coen@vectioneer.com)
#   All rights reserved. Copyright (c) 2025 VECTIONEER.
#

import sys
from pathlib import Path

# Add parent directory to path to import mcx_client_app
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mcx_client_app import McxClientApp, McxClientAppOptions, ThreadSafeValue
from motorcortex import Subscription
import os
import csv
from datetime import datetime # For timestamping files
from queue import Queue # Thread-safe queue
import time
import logging

#
#   Developer : Coen Smeets (Coen@vectioneer.com)
#   All rights reserved. Copyright (c) 2025 VECTIONEER.
#

def timespec_to_msec(timestamp):
    return timestamp.sec * 1000 + timestamp.nsec / 1000000
    
class dataLoggerClientApp(McxClientApp):
    """
    Application that implements thread-safe data logging with subscriptions.
    Data is collected from subscription callbacks and saved to CSV in the action thread.
    """
    def __init__(self, options: McxClientAppOptions):
        """Initialize the data logger client app.
        
        Args:
            options (McxClientAppOptions): Options for the MCX client app.
            paths (list[str]): List of parameter paths to log.
            file_path (str): Path to the file where data will be logged.
            divider (int, optional): Frequency divider for logging. Defaults to 10.
            save_interval (int, optional): Interval for saving data to file in seconds. Defaults to 10.
            batch_size (int, optional): Maximum items to process per iteration. Defaults to 100.
        """
        super().__init__(options)
        self.__subscription: Subscription = None # Placeholder for subscription
        self.__data_queue: Queue = Queue()  # Unbounded thread-safe queue
        self.__buffer: list[dict] = []  # Buffer to accumulate data before writing
        self.__last_save_time: float = time.time() # Last time data was saved
        self.__field_mapping: dict = {}  # Maps path to expanded field names
        self.__fieldnames: list[str] = []  # All CSV column names
        
    def startOp(self) -> None:
        """Start the data logging operation by subscribing to parameters."""
        logging.info(f"Subscribing to {len(self.options.paths_to_log)} parameters...")
        self.__subscription = self.sub.subscribe(
            self.options.paths_to_log, 
            "DataLoggerGroup", 
            frq_divider=self.options.divider
        )
        self.__subscription.notify(self.__sub_callback)
        
        # Initialize CSV file with headers
        self.__initialize_csv()
        logging.info("Data logger initialized and subscribed.")
        
    def __get_unique_filepath(self) -> str:
        """Get a unique filepath by appending date and time.
        
        Returns:
            str: Unique filepath (e.g., robot_data_2024-12-12_14-30-45.csv)
        """
        # Split path into directory, name, and extension
        directory = os.path.dirname(self.options.log_file)
        basename = os.path.basename(self.options.log_file)
        name, ext = os.path.splitext(basename)
        
        # Append current date and time
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        new_filepath = os.path.join(directory, f"{name}_{timestamp}{ext}")
        
        return new_filepath
    
    def __initialize_csv(self) -> None:
        """Initialize the CSV file with headers."""
        # Get unique filepath if file already exists
        self.options.log_file = self.__get_unique_filepath()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.options.log_file), exist_ok=True)
        
        # Get parameter tree to determine array sizes
        tree = self.parameter_tree.getParameterTree()
        
        # Build expanded fieldnames for arrays/matrices
        expanded_fieldnames = ['timestamp']
        self.__field_mapping = {}  # Maps original path to list of expanded field names
        
        for path in self.options.paths_to_log:
            # Find parameter info in tree
            param_info = None
            for param in tree:
                if param.path == path:
                    param_info = param
                    break
            
            if param_info and param_info.number_of_elements > 1:
                # Array/matrix - expand into multiple columns
                field_list = []
                for i in range(param_info.number_of_elements):
                    field_name = f"{path}[{i}]"
                    expanded_fieldnames.append(field_name)
                    field_list.append(field_name)
                self.__field_mapping[path] = field_list
            else:
                # Scalar - single column
                expanded_fieldnames.append(path)
                self.__field_mapping[path] = [path]
        
        self.__fieldnames = expanded_fieldnames
        
        # Write header row
        with open(self.options.log_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.__fieldnames)
            writer.writeheader()
        logging.info(f"CSV file initialized: {self.options.log_file}")
        logging.info(f"Field mapping: {self.__field_mapping}")
        
    def __sub_callback(self, msg) -> None:
        """Callback for subscription updates (runs in subscription thread).
        
        Args:
            msg: Message containing updated parameter values.
        """
        if (not self.running.get()):
            return
        
        # Collect all values from this message with timestamp
        data_row = {'timestamp': timespec_to_msec(msg[0].timestamp)}
        
        for item, param in enumerate(msg):
            path = self.options.paths_to_log[item]
            value = param.value
            
            # Get the field names for this path
            field_names = self.__field_mapping.get(path, [path])
            
            if len(field_names) == 1:
                # Scalar value
                data_row[field_names[0]] = value[0] if isinstance(value, (list, tuple)) and len(value) > 0 else value
            else:
                # Array/matrix - split into individual columns
                for i, field_name in enumerate(field_names):
                    data_row[field_name] = value[i] if i < len(value) else None
        
        # Put data in thread-safe queue (unbounded, no blocking)
        self.__data_queue.put(data_row)
            
    def __save_data(self) -> None:
        """Save buffered data to CSV file."""
        if not self.__buffer:
            return
            
        try:
            with open(self.options.log_file, 'a', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.__fieldnames)
                writer.writerows(self.__buffer)
            
            logging.info(f"Saved {len(self.__buffer)} rows to {self.options.log_file}")
            self.__buffer.clear()
            self.__last_save_time = time.time()
        except Exception as e:
            logging.error(f"Error saving data: {e}")
                
    def action(self) -> None:
        """Perform the data logging action (runs in action thread).
        
        Retrieves data from the queue in batches and saves it periodically to CSV.
        """
        # Process up to batch_size items from queue
        processed = 0
        
        while processed < self.options.batch_size and not self.__data_queue.empty():
            data_row = self.__data_queue.get()
            self.__buffer.append(data_row)
            processed += 1
        
        # Check if it's time to save to file
        current_time = time.time()
        should_save = (current_time - self.__last_save_time >= self.options.save_interval) or len(self.__buffer) >= 1000
        
        if should_save:
            self.__save_data()
    
    def onExit(self) -> None:
        """Cleanup: save any remaining buffered data before exit."""
        logging.info("Saving remaining data before exit...")
        
        # Check if it's time to save to file
        current_time = time.time()
        should_save = (current_time - self.__last_save_time >= self.options.save_interval) or len(self.__buffer) >= 1000
        
        if should_save:
            self.__save_data()
        
        # Small sleep to prevent busy waiting and block the stop signal
        self.wait(0.1, block_stop_signal=True)
        
        remaining = 0
        while not self.__data_queue.empty():
            data_row = self.__data_queue.get()
            self.__buffer.append(data_row)
            remaining += 1
            
            if len(self.__buffer) >= self.options.batch_size:
                self.__save_data()
        
        if remaining > 0:
            logging.info(f"Processing {remaining} remaining samples from queue...")
        
        # Save final buffer
        self.__save_data()
        logging.info("Data logger cleanup complete.")
        
if __name__ == "__main__":
    class DataLoggerOptions(McxClientAppOptions):
        def __init__(self, **args):
            self.paths_to_log: list[str] = []
            self.log_file: str = ""
            self.divider: int = 10
            self.save_interval: int = 5
            self.batch_size: int = 100
            
            super().__init__(**args)
            
    # Add current script directory to path so dataLogger_config.json can be found
    config_path = os.path.join(os.path.dirname(__file__), 'examples/dataLogger_config.json')
    options = DataLoggerOptions.from_json(config_path)
            
    logging.info(f"McxClientAppOptions initialized: {options.as_dict()}")
    
    app = dataLoggerClientApp(
        options=options
    )
    app.run()
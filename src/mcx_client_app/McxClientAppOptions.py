import logging
import os
import json
from .state_def import State

class McxClientAppOptions:
    """
    Configuration options for McxClientApp.

    Attributes:
        login (str): Username for authenticating with the Motorcortex server.
        password (str): Password for authenticating with the Motorcortex server.
        target_url (str): Local Development WebSocket URL of the Motorcortex server (e.g., 'wss://localhost').
            This is the endpoint used to establish the connection.
        target_url_deployed (str): Deployed WebSocket URL of the Motorcortex server (default: 'wss://localhost').
            This is the endpoint used when the application is deployed on a system.
        cert (str): Local Development path to the SSL certificate file for secure connection (e.g., 'mcx.cert.crt').
            Required for encrypted communication with the server. This is only used with local development (Not deployed)
        cert_deployed (str): Deployed path to the SSL certificate file for secure connection (default: '/etc/ssl/certs/mcx.cert.pem').
            Required for encrypted communication with the server. This is only used when deployed on a system with the certificate installed.
        statecmd_param (str): Parameter path for sending state commands to the server (default: 'root/Logic/stateCommand').
            Used to control the robot or system state.
        state_param (str): Parameter path for reading the current state from the server (default: 'root/Logic/state').
            Used to monitor the robot or system state.
        run_during_states (list[State]|None): List of allowed states during which the iterate() method can run (default None).
            If the system is not in one of these states, the iterate() method will not execute.
            If empty or None, the iterate() method can run in any state.
        start_stop_param (str|None): Optional parameter path for start/stop control (default: None).
            If provided, the application will monitor this parameter to start or stop operations.
    
    Note:
        When inheriting from this class, ensure to call super().__init__(**kwargs) after initialising the class parameters. For example,
            class CustomOptions(McxClientAppOptions):
                def __init__(self, custom_param: str = "default", **kwargs):
                    self.custom_param = custom_param
                    super().__init__(**kwargs)
    
    """
    def __init__(
        self,
        login: str | None = None,
        password: str | None = None,
        target_url: str = "wss://localhost",
        target_url_deployed: str = "wss://localhost",
        cert: str = "mcx.cert.crt",
        cert_deployed: str = "/etc/ssl/certs/mcx.cert.pem",
        statecmd_param: str | None = "root/Logic/stateCommand",
        state_param: str | None = "root/Logic/state",
        run_during_states: list = None,
        start_stop_param: str | None = None,
        **kwargs
    ) -> None:
        self.login = login
        self.password = password
        self.target_url = target_url
        self.target_url_deployed = target_url_deployed
        self.cert = cert
        self.cert_deployed = cert_deployed
        self.statecmd_param = statecmd_param
        self.state_param = state_param
        self._run_during_states = State.list_from(run_during_states)
        self.start_stop_param = start_stop_param

        for key, value in kwargs.items():
            setattr(self, key, value)

        config_path = os.environ.get("CONFIG_PATH", None)
        self.__deployed = config_path is not None
        logging.debug(f"Loading McxClientApp Options! [Deployed: {self.__deployed}]")
        if self.__deployed and config_path:
            with open(config_path, 'r') as f:
                data = json.load(f)
                for key, value in data.items():
                    if key == "run_during_states":
                        self._run_during_states = State.list_from(value)
                    elif hasattr(self, key):
                        setattr(self, key, value)

    def as_dict(self) -> dict:
        result = dict(self.__dict__)
        # Convert enums to names for serialization
        result["run_during_states"] = [state.name for state in self._run_during_states]
        result.pop('_McxClientAppOptions__deployed', None)
        return result

    def __str__(self) -> str:
        return str(self.as_dict())

    @classmethod
    def from_json(cls, json_file: str) -> 'McxClientAppOptions':
        config_path = os.environ.get("CONFIG_PATH", None)
        if config_path is not None:
            return cls()
        else:
            with open(json_file, 'r') as f:
                data = json.load(f)
            return cls(**data)

    @property
    def certificate(self) -> str:
        if getattr(self, "__deployed", False):
            return self.cert_deployed
        return self.cert

    @property
    def ip_address(self) -> str:
        if getattr(self, "__deployed", False):
            return self.target_url_deployed
        return self.target_url
    
    @property
    def run_during_states(self) -> list:
        return self._run_during_states

    @run_during_states.setter
    def run_during_states(self, value):
        self._run_during_states = State.list_from(value)

    @property
    def allowed_states(self) -> list:
        return self._run_during_states
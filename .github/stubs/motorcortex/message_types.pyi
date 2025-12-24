from _typeshed import Incomplete
from typing import NamedTuple

def importLibrary(name, path): ...

motorcortex_parameter_msg: int
motorcortex_parameter_list_msg: int

class ParameterMsg(NamedTuple):
    header: Incomplete
    info: Incomplete
    value: Incomplete
    status: Incomplete

class ParameterListMsg(NamedTuple):
    header: Incomplete
    params: Incomplete

StatusCode: Incomplete
UserLevel: Incomplete

class PrimitiveTypes:
    def __init__(self, type_name) -> None: ...
    def decode(self, value, number_of_elements): ...
    def encode(self, value): ...

class ModuleHashListPairContainer:
    module: Incomplete
    hash_list: Incomplete
    def __init__(self, module, hash_list) -> None: ...

class MessageTypes:
    """Class for handling motorcortex data types, loads proto files and hash files,
    creates a dictionary with all available data types, resolves data types by,
    name or by hash, performs encoding and decoding of the messages.

    """
    def __init__(self) -> None: ...
    def motorcortex(self):
        """Returns default motorcortex messages, provided with the package.
        System messages could be replaced at runtime with a newer version,
        by load([{'proto': 'path to the new message proto', 'hash': 'path to the new message hash'}])

        Returns:
            returns motorcortex messages
        """
    def load(self, proto_hash_pair_list=None):
        """Loads an array of .proto and .json file pairs.
            Args:
                proto_hash_pair_list([{'hash'-`str`,'proto'-`str`}]): list of hash and proto messages

            Returns:
                list(Module): list of loaded modules with protobuf messages.

            Examples:
                >>> motorcortex_msg, motionsl_msg = motorcortex_types.load(
                >>>     # motorcortex hashes and messages
                >>>     [{'proto': './motorcortex-msg/motorcortex_pb2.py',
                >>>       'hash': './motorcortex-msg/motorcortex_hash.json'},
                >>>     # robot motion hashes and messages
                >>>      {'proto': './motorcortex-msg/motionSL_pb2.py',
                >>>       'hash': './motorcortex-msg/motionSL_hash.json'}])

        """
    def createType(self, type_name):
        """Returns an instance of the loaded data type given type name.

            Args:
                type_name(str): type name

            Returns:
                an instance of the requested type.

        """
    def getTypeByHash(self, id):
        """Returns a data type given its hash.

            Args:
                id(int): type hash

            Returns:
                requested data type.
        """
    def getTypeByName(self, name):
        """Returns a data type given its name.

            Args:
                name(str): type name

            Returns:
                requested data type.
        """
    def getNamespace(self, name):
        '''Returns a module/namespace with data types.

            Args:
                name(str): module name

            Returns:
                requested module

            Examples:
                >>> # loading module motion_spec
                >>> MotionSpecType = motorcortex_types.getNamespace("motion_spec")
                >>> # instantiating a motion program from the module
                >>> motion_program = MotionSpecType.MotionProgram()
        '''
    def decode(self, wire_data):
        """Decodes data received from the server"""
    def encode(self, proto_data):
        """Encodes data to send to the server"""

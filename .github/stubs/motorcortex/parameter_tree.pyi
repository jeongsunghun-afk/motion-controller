class ParameterTree:
    """This class represents a parameter tree, obtained from the server.

        Reference to a parameter tree instance is needed for resolving parameters,
        data types and other information to build a correct request message.
    """
    def __init__(self) -> None: ...
    def load(self, parameter_tree_msg) -> None:
        """Loads a parameter tree from ParameterTreeMsg received from the server

            Args:
                parameter_tree_msg(ParameterTreeMsg): parameter tree message from the server

            Examples:
                >>> parameter_tree = motorcortex.ParameterTree()
                >>> parameter_tree_msg = param_tree_reply.get()
                >>> parameter_tree.load(parameter_tree_msg)
        """
    def getParameterTree(self):
        """
            Returns:
                list(ParameterInfo): a list of parameter descriptions
        """
    def getInfo(self, parameter_path):
        """
            Args:
                parameter_path(str): path of the parameter

            Returns:
                ParameterInfo: parameter description
        """
    def getDataType(self, parameter_path):
        """
            Args:
                parameter_path(str): path of the parameter

            Returns:
                DataType: parameter data type

        """

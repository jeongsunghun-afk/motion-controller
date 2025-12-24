class Reply:
    """Reply handle is a JavaScript-like Promise.

        It is resolved when a reply is received with successful status and fails otherwise.
    """
    def __init__(self, future) -> None: ...
    def get(self, timeout_ms=None):
        """A blocking call to wait for the reply and returns a value.

            Args:
                timeout_ms(integer): timeout for reply in milliseconds

            Returns:
                A protobuf message with a parameter description and value.

            Examples:
                  >>> param_tree_reply = req.getParameterTree()
                  >>> value = param_tree_reply.get()

        """
    def done(self):
        """
            Returns:
                bool: True if the call was successfully canceled or finished running.
        """
    def then(self, received_clb, *args, **kwargs):
        '''JavaScript-like promise, which is resolved when a reply is received.

                Args:
                    received_clb: callback which is resolved when the reply is received.

                Returns:
                    self pointer to add \'catch\' callback

                Examples:
                    >>> param_tree_reply.then(lambda reply: print("got reply: %s"%reply))
                    >>>                 .catch(lambda g: print("failed"))
        '''
    def catch(self, failed_clb, *args, **kwargs):
        '''JavaScript-like promise, which is resolved when receive has failed.

            Args:
                failed_clb: callback which is resolved when receive has failed

            Returns:
                self pointer to add \'then\' callback

            Examples:
                >>> param_tree_reply.catch(lambda g: print("failed")).then(lambda reply: print("got reply: %s"%reply))
        '''

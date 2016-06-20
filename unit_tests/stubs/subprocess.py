class SubprocessStub(object):
    """Testable stub for C{subprocess}.

    @ivar calls: A list of all calls that have been made.
    """
    def __init__(self):
        self.calls = []
        self.outputs = {}

    def check_call(self, command, **kwargs):
        self.calls.append((command, kwargs))

    def check_output(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return self.outputs.get(command, "")

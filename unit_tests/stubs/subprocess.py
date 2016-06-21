from collections import namedtuple

Call = namedtuple("Call", ["command", "kwargs"])


class SubprocessStub(object):
    """Testable stub for C{subprocess}.

    @ivar calls: A list of all calls that have been made.
    @ivar outputs: A dict mapping command lines to their expected output.
    """
    def __init__(self):
        self.calls = []
        self.outputs = {}

    def check_call(self, command, **kwargs):
        self.calls.append(Call(command, kwargs))

    def check_output(self, command, **kwargs):
        self.calls.append(Call(command, kwargs))
        return self.outputs.get(command, b"")

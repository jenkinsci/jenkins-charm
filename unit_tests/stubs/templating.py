from collections import namedtuple

Render = namedtuple(
    "Render", ["source", "target", "context", "owner", "group"])


class TemplatingStub(object):
    """Testable stub for charmhelpers.core.templating."""

    password = "eegh5ahGh5joiph"

    def __init__(self):
        self.renders = []

    def render(self, source, target, context, owner="root", group="root"):
        self.renders.append(Render(source, target, context, owner, group))

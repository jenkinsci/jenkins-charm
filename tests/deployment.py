from amulet import SKIP, Deployment, TimeoutError, raise_status

TIMEOUT = 990


class DeploymentSpec(object):

    def __init__(self, series="trusty"):
        self.series = series
        self.deployment = Deployment(series=self.series)
        self._run_hooks("init")

    def deploy(self):
        self._run_hooks("pre_setup")
        try:
            self.deployment.setup(timeout=TIMEOUT)
            self.deployment.sentry.wait()
        except TimeoutError:
            msg = "The model did not set up in % seconds!" % TIMEOUT
            raise_status(SKIP, msg=msg)
        self._run_hooks("post_setup")

    def _run_hooks(self, prefix):
        for attribute in dir(self):
            if attribute.startswith("_%s" % prefix):
                getattr(self, attribute)()


class DeploymentTest(object):

    spec = DeploymentSpec()

    @classmethod
    def setUpClass(cls):
        """Set up the deployment in the class."""
        cls.spec.deploy()

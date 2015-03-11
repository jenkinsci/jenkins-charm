import amulet
import os
import six


class AmuletDeployment(object):
    """Amulet deployment.

       This class provides generic Amulet deployment and test runner
       methods.
       """

    def __init__(self, series=None):
        """Initialize the deployment environment."""
        self.series = None

        if series:
            self.series = series
            self.d = amulet.Deployment(series=self.series)
        else:
            self.d = amulet.Deployment()

    def _add_services(self, this_service, other_services):
        """Add services.

           Add services to the deployment where this_service is the local charm
           that we're testing and other_services are the other services that
           are being used in the local amulet tests.
           """
        if this_service['name'] != os.path.basename(os.getcwd()):
            s = this_service['name']
            msg = "The charm's root directory name needs to be {}".format(s)
            amulet.raise_status(amulet.FAIL, msg=msg)

        if 'units' not in this_service:
            this_service['units'] = 1

        self.d.add(this_service['name'], units=this_service['units'])

        for svc in other_services:
            if 'location' in svc:
                branch_location = svc['location']
            elif self.series:
                branch_location = 'cs:{}/{}'.format(self.series, svc['name']),
            else:
                branch_location = None

            if 'units' not in svc:
                svc['units'] = 1

            self.d.add(svc['name'], charm=branch_location, units=svc['units'])

    def _add_relations(self, relations):
        """Add all of the relations for the services."""
        for k, v in six.iteritems(relations):
            self.d.relate(k, v)

    def _configure_services(self, configs):
        """Configure all of the services."""
        for service, config in six.iteritems(configs):
            self.d.configure(service, config)

    def _deploy(self):
        """Deploy environment and wait for all hooks to finish executing."""
        try:
            self.d.setup(timeout=900)
            self.d.sentry.wait(timeout=900)
        except amulet.helpers.TimeoutError:
            amulet.raise_status(amulet.FAIL, msg="Deployment timed out")
        except Exception:
            raise

    def run_tests(self):
        """Run all of the methods that are prefixed with 'test_'."""
        for test in dir(self):
            if test.startswith('test_'):
                getattr(self, test)()

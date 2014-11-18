from charmhelpers.contrib.amulet.deployment import (
    AmuletDeployment
)


class OpenStackAmuletDeployment(AmuletDeployment):
    """OpenStack amulet deployment.

       This class inherits from AmuletDeployment and has additional support
       that is specifically for use by OpenStack charms.
       """

    def __init__(self, series=None, openstack=None, source=None, stable=True):
        """Initialize the deployment environment."""
        super(OpenStackAmuletDeployment, self).__init__(series)
        self.openstack = openstack
        self.source = source
        self.stable = stable
        # Note(coreycb): this needs to be changed when new next branches come
        # out.
        self.current_next = "trusty"

    def _determine_branch_locations(self, other_services):
        """Determine the branch locations for the other services.

           Determine if the local branch being tested is derived from its
           stable or next (dev) branch, and based on this, use the corresonding
           stable or next branches for the other_services."""
        base_charms = ['mysql', 'mongodb', 'rabbitmq-server']

        if self.stable:
            for svc in other_services:
                temp = 'lp:charms/{}'
                svc['location'] = temp.format(svc['name'])
        else:
            for svc in other_services:
                if svc['name'] in base_charms:
                    temp = 'lp:charms/{}'
                    svc['location'] = temp.format(svc['name'])
                else:
                    temp = 'lp:~openstack-charmers/charms/{}/{}/next'
                    svc['location'] = temp.format(self.current_next,
                                                  svc['name'])
        return other_services

    def _add_services(self, this_service, other_services):
        """Add services to the deployment and set openstack-origin/source."""
        other_services = self._determine_branch_locations(other_services)

        super(OpenStackAmuletDeployment, self)._add_services(this_service,
                                                             other_services)

        services = other_services
        services.append(this_service)
        use_source = ['mysql', 'mongodb', 'rabbitmq-server', 'ceph',
                      'ceph-osd', 'ceph-radosgw']

        if self.openstack:
            for svc in services:
                if svc['name'] not in use_source:
                    config = {'openstack-origin': self.openstack}
                    self.d.configure(svc['name'], config)

        if self.source:
            for svc in services:
                if svc['name'] in use_source:
                    config = {'source': self.source}
                    self.d.configure(svc['name'], config)

    def _configure_services(self, configs):
        """Configure all of the services."""
        for service, config in configs.iteritems():
            self.d.configure(service, config)

    def _get_openstack_release(self):
        """Get openstack release.

           Return an integer representing the enum value of the openstack
           release.
           """
        (self.precise_essex, self.precise_folsom, self.precise_grizzly,
         self.precise_havana, self.precise_icehouse,
         self.trusty_icehouse) = range(6)
        releases = {
            ('precise', None): self.precise_essex,
            ('precise', 'cloud:precise-folsom'): self.precise_folsom,
            ('precise', 'cloud:precise-grizzly'): self.precise_grizzly,
            ('precise', 'cloud:precise-havana'): self.precise_havana,
            ('precise', 'cloud:precise-icehouse'): self.precise_icehouse,
            ('trusty', None): self.trusty_icehouse}
        return releases[(self.series, self.openstack)]

from charmhelpers.core.hookenv import (
    config,
    unit_get,
)
from charmhelpers.contrib.network.ip import (
    get_address_in_network,
    is_address_in_network,
    is_ipv6,
    get_ipv6_addr,
)
from charmhelpers.contrib.hahelpers.cluster import is_clustered

PUBLIC = 'public'
INTERNAL = 'int'
ADMIN = 'admin'

ADDRESS_MAP = {
    PUBLIC: {
        'config': 'os-public-network',
        'fallback': 'public-address'
    },
    INTERNAL: {
        'config': 'os-internal-network',
        'fallback': 'private-address'
    },
    ADMIN: {
        'config': 'os-admin-network',
        'fallback': 'private-address'
    }
}


def canonical_url(configs, endpoint_type=PUBLIC):
    """Returns the correct HTTP URL to this host given the state of HTTPS
    configuration, hacluster and charm configuration.

    :param configs: OSTemplateRenderer config templating object to inspect
                    for a complete https context.
    :param endpoint_type: str endpoint type to resolve.
    :param returns: str base URL for services on the current service unit.
    """
    scheme = 'http'
    if 'https' in configs.complete_contexts():
        scheme = 'https'
    address = resolve_address(endpoint_type)
    if is_ipv6(address):
        address = "[{}]".format(address)
    return '%s://%s' % (scheme, address)


def resolve_address(endpoint_type=PUBLIC):
    """Return unit address depending on net config.

    If unit is clustered with vip(s) and has net splits defined, return vip on
    correct network. If clustered with no nets defined, return primary vip.

    If not clustered, return unit address ensuring address is on configured net
    split if one is configured.

    :param endpoint_type: Network endpoing type
    """
    resolved_address = None
    vips = config('vip')
    if vips:
        vips = vips.split()

    net_type = ADDRESS_MAP[endpoint_type]['config']
    net_addr = config(net_type)
    net_fallback = ADDRESS_MAP[endpoint_type]['fallback']
    clustered = is_clustered()
    if clustered:
        if not net_addr:
            # If no net-splits defined, we expect a single vip
            resolved_address = vips[0]
        else:
            for vip in vips:
                if is_address_in_network(net_addr, vip):
                    resolved_address = vip
                    break
    else:
        if config('prefer-ipv6'):
            fallback_addr = get_ipv6_addr(exc_list=vips)[0]
        else:
            fallback_addr = unit_get(net_fallback)

        resolved_address = get_address_in_network(net_addr, fallback_addr)

    if resolved_address is None:
        raise ValueError("Unable to resolve a suitable IP address based on "
                         "charm state and configuration. (net_type=%s, "
                         "clustered=%s)" % (net_type, clustered))

    return resolved_address

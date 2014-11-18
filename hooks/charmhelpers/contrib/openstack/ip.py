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

_address_map = {
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
    '''
    Returns the correct HTTP URL to this host given the state of HTTPS
    configuration, hacluster and charm configuration.

    :configs OSTemplateRenderer: A config tempating object to inspect for
        a complete https context.
    :endpoint_type str: The endpoint type to resolve.

    :returns str: Base URL for services on the current service unit.
    '''
    scheme = 'http'
    if 'https' in configs.complete_contexts():
        scheme = 'https'
    address = resolve_address(endpoint_type)
    if is_ipv6(address):
        address = "[{}]".format(address)
    return '%s://%s' % (scheme, address)


def resolve_address(endpoint_type=PUBLIC):
    resolved_address = None
    if is_clustered():
        if config(_address_map[endpoint_type]['config']) is None:
            # Assume vip is simple and pass back directly
            resolved_address = config('vip')
        else:
            for vip in config('vip').split():
                if is_address_in_network(
                        config(_address_map[endpoint_type]['config']),
                        vip):
                    resolved_address = vip
    else:
        if config('prefer-ipv6'):
            fallback_addr = get_ipv6_addr(exc_list=[config('vip')])[0]
        else:
            fallback_addr = unit_get(_address_map[endpoint_type]['fallback'])
        resolved_address = get_address_in_network(
            config(_address_map[endpoint_type]['config']), fallback_addr)

    if resolved_address is None:
        raise ValueError('Unable to resolve a suitable IP address'
                         ' based on charm state and configuration')
    else:
        return resolved_address

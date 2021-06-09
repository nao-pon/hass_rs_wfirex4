"""RS-WFIREX4 Load Platform integration."""

from getmac import get_mac_address

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.helpers import discovery
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SCAN_INTERVAL

DOMAIN = 'rs_wfirex4'
DEFAULT_NAME = 'RS-WFIREX4'
DEFAULT_SCAN_INTERVAL = 60
PLATFORMS = ['remote', 'sensor']
CONF_TEMP_OFFSET = 'temp_offset'
CONF_HUMI_OFFSET = 'humi_offset'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema([
        vol.Schema({
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
            vol.Optional(CONF_TEMP_OFFSET, default=0.0): vol.All(vol.Coerce(float), vol.Range(min=-10, max=10)),
            vol.Optional(CONF_HUMI_OFFSET, default=0.0): vol.All(vol.Coerce(float), vol.Range(min=-20, max=20)),
        }),
    ])
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass, configs):
    for config in configs.get(DOMAIN):
        config['uid'] = get_mac_address(ip=config.get(CONF_HOST)).replace(':', '')
        for component in PLATFORMS:
            await hass.helpers.discovery.async_load_platform(component, DOMAIN, config, configs)

    return True

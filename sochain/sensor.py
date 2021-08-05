"""Support for watching multiple cryptocurrencies."""
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_ADDRESS, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

ATTRIBUTION = "Data provided by chain.so"

CONF_NETWORK = "network"

DEFAULT_NAME = "Crypto Balance"

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Required(CONF_NETWORK): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
}
)

import asyncio
import logging

import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)
_BASE_URL = 'https://chain.so/api/v2/'
_UNMINERABLE_URL = 'https://api.unminable.com/v3/stats'


class ChainSo(object):
    """A class for handling data from chain.so."""

    def __init__(self, network, address, loop, session):
        """Initialize the data retrieval."""
        self._loop = loop
        self._session = session
        self.network = network
        self.address = address
        self.data = {}

    @asyncio.coroutine
    def async_get_data(self):
        url = '{}/{}/{}/{}'.format(
            _BASE_URL, 'get_price', self.network, 'USD')

        try:
            with async_timeout.timeout(5, loop=self._loop):
                response = yield from self._session.get(url)

            _LOGGER.debug("Response from chain.so: %s", response.status)
            data = yield from response.json()
            if data['status'] == 'success':
                self.data['price'] = data['data']
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Can not load data from chain.so")


        # async_get_address_received_data
        url = '{}/{}/{}/{}'.format(
            _BASE_URL, 'get_address_received', self.network, self.address)

        try:
            with async_timeout.timeout(5, loop=self._loop):
                response = yield from self._session.get(url)

            _LOGGER.debug("Response from chain.so: %s", response.status)
            data = yield from response.json()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Can not load data from chain.so")

        if data['status'] == 'success':
            self.data['received'] = data['data']

        # async_get_address_spent_data
        url = '{}/{}/{}/{}'.format(
            _BASE_URL, 'get_address_spent', self.network, self.address)

        try:
            with async_timeout.timeout(5, loop=self._loop):
                response = yield from self._session.get(url)

            _LOGGER.debug("Response from chain.so: %s", response.status)
            data = yield from response.json()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Can not load data from chain.so")

        if data['status'] == 'success':
            self.data['spent'] = data['data']

        # async_get_unminerable_data
        url = '{}/{}?tz=8&coin={}'.format(_UNMINERABLE_URL, self.address, self.network)
        try:
            with async_timeout.timeout(5, loop=self._loop):
                response = yield from self._session.get(url)
            _LOGGER.debug("Response from unmineable.com: %s", response.status)
            data = yield from response.json()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Can not load data from unmineable.com")
        
        if 'success' in data.keys() and data['success'] == True:
            self.data['unminerable'] = data['data']


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sochain sensors."""

    address = config.get(CONF_ADDRESS)
    network = config.get(CONF_NETWORK)
    name = config.get(CONF_NAME)

    session = async_get_clientsession(hass)
    chainso = ChainSo(network, address, hass.loop, session)

    async_add_entities([SochainSensor(name, network.upper(), chainso)], True)


class SochainSensor(Entity):
    """Representation of a Sochain sensor."""

    def __init__(self, name, unit_of_measurement, chainso):
        """Initialize the sensor."""
        self._name = name
        self._unit_of_measurement = unit_of_measurement
        self.chainso = chainso

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return (
            self.chainso.data.get("price").get("prices")[0].get("price")
            if self.chainso is not None
            else None
        )

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        address_received = self.chainso.data.get("received").get("confirmed_received_value") if self.chainso is not None else -1
        address_spent = self.chainso.data.get("spent").get("confirmed_sent_value") if self.chainso is not None else -1
        unminerable_data = self.chainso.data.get("unminerable") if self.chainso is not None else None

        attr_dict = {ATTR_ATTRIBUTION: ATTRIBUTION, "confirmed_received_value": address_received, "confirmed_sent_value": address_spent}

        if unminerable_data is not None:
            attr_dict["doge_address"] = unminerable_data.get("address_")
            attr_dict["pending_balance"] = unminerable_data.get("pending_balance")
            attr_dict["pending_mining_balance"] = unminerable_data.get("pending_mining_balance")
            attr_dict["pending_referral_balance"] = unminerable_data.get("pending_referral_balance")
            attr_dict["randomx_hashrate"] = unminerable_data.get("hashrate").get("randomx").get("totalh")
            attr_dict["total_paid"] = unminerable_data.get("total_paid")
            attr_dict["total_24h"] = unminerable_data.get("total_24h")
            attr_dict["auto_pay"] = unminerable_data.get("auto_pay")

        return attr_dict



    async def async_update(self):
        """Get the latest state of the sensor."""
        await self.chainso.async_get_data()

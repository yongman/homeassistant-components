'''
# Module name:
    eastmoney.py
# Prerequisite:
    Based on Python 3.4
    Need python module requests and bs4
# Purpose:
    Fund sensor powered by East Money
# Author:
    Retroposter retroposter@outlook.com
    
# Created:
    Aug.31th 2017
'''

import logging
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
import requests
import re
import json
import voluptuous as vol

from homeassistant.const import (CONF_LATITUDE, CONF_LONGITUDE, CONF_API_KEY, CONF_MONITORED_CONDITIONS, CONF_NAME, TEMP_CELSIUS, ATTR_ATTRIBUTION)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Fund'
ATTRIBUTION = 'Powered by East Money'

PAT_DATE = re.compile(r'\d{4}-\d{1,2}-\d{1,2}')

CONF_UPDATE_INTERVAL = 'update_interval'
CONF_NAME = 'name'
CONF_FUND_ID = 'fund_id'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FUND_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(minutes=15)): (vol.All(cv.time_period, cv.positive_timedelta)),
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Fund sensor.""" 
    fund_id = config[CONF_FUND_ID]
    name = config[CONF_NAME]
    interval = config.get(CONF_UPDATE_INTERVAL)
    fund_data = EastmoneyData(fund_id, interval)
    fund_data.update()
    # If connection failed don't setup platform.
    if fund_data.data is None:
        return False

    sensors = [EastmoneySensor(fund_data, name)]
    add_devices(sensors, True)

class EastmoneySensor(Entity):
    def __init__(self, fund_data, name):
        """Initialize the sensor."""
        self.fund_data = fund_data
        self.client_name = name
        self._state = None
        self._trend = -1

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.client_name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._trend == 1:
            return 'mdi:trending-up'
        if self._trend == -1:
            return 'mdi:trending-down'
        return 'mdi:trending-neutral'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return '%'

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        data = self.fund_data.data
        if data is None:
            attrs[ATTR_ATTRIBUTION] = ATTRIBUTION
            return attrs

        attrs[ATTR_ATTRIBUTION] = '{0} {1}'.format(data['last_update'], ATTRIBUTION)
        attrs['est nav'] = data['enav']
        attrs['est growth'] = data['enav_growth']
        attrs['est growth rate'] = data['enav_rate']
        attrs['last trading day'] = data['last_trading_day']
        attrs['last nav'] = data['last_nav']
        attrs['last growth'] = data['last_nav_growth']
        attrs['last growth rate'] = data['last_nav_rate']
        attrs['recent 1 month'] = data['rct_1month']
        attrs['recent 3 months'] = data['rct_3month']
        return attrs

    def update(self):
        """Get the latest data from He Weather and updates the states."""
        self.fund_data.update()
        data = self.fund_data.data
        if data is None:
            return
        enav = data['enav']
        last_nav = data['last_nav']
        self._state = data['enav_rate']
        if enav > last_nav:
            self._trend = 1
        elif enav < last_nav:
            self._trend = -1
        else:
            self._trend = 0


class EastmoneyData(object):
    """Get the latest data from Eastmoney."""

    def __init__(self, fund_id, internal):
        self.fund_id = fund_id
        self.data = None
        # Apply throttling to methods using configured interval
        self.update = Throttle(internal)(self._update)

    def _update(self):
        """Get the latest data from Eastmoney."""

        url = 'http://fund.eastmoney.com/{0}.html?spm=aladin'.format(self.fund_id)
        resp = None
        try:
            resp = requests.get(url)
        except (ConnectError, HTTPError, Timeout, ValueError) as error:
            _LOGGER.error("Unable to connect to Eastmoney. %s", error)
            return

        soup = BeautifulSoup(resp.text, 'html.parser')

        tit = self._get_fund_tit(soup)
        if tit is not None and (len(tit) == 2 or len(tit) == 3) and tit[-1] == self.fund_id:
            self.data = self._analyze(soup)
        else:
            _LOGGER.error('Invalid fund id: %s.', self.fund_id)
    
    def _get_enav(self):
        url = 'http://fundgz.1234567.com.cn/js/{0}.js'.format(self.fund_id)
        try:
            resp = requests.get(url)
            return json.loads(str(resp.content)[10:-3].encode('utf-8').decode('unicode_escape'))["gsz"]
        except:
            return None

    def _get_fund_tit(self, soup):
        fund_tit = soup.find('div', class_='fundDetail-tit')
        if fund_tit is None:
            return
        tit = fund_tit.find('div')
        if tit is None:
            return
        return tit.text.split('(')

    def _analyze(self, soup):
        fund_info_item = soup.find('div', class_='fundInfoItem')
        if fund_info_item is None:
            _LOGGER.error('Element \'div,class_=fundInfoItem\' not found.')
            return
        fund_data = fund_info_item.find('div', class_='dataOfFund')
        if fund_data is None:
            _LOGGER.error('Element \'div,class_=dataOfFund\' not found.')
            return
        data_item_01 = fund_data.find('dl', class_='dataItem01')
        data_item_02 = fund_data.find('dl', class_='dataItem02')
        # Until now, I do not care accnav.
        # data_item_03 = fund_data.find('dl', class_='dataItem03')
        if data_item_01 is None or data_item_02 is None:
            _LOGGER.error('Element \'div,class_=dataItem01|dataItem02\' not found.')
            return

        enav = self._get_estnav(data_item_01)
        nav = self._get_nav(data_item_02)
        if enav is None or nav is None:
            return None
        now = datetime.now()
        enav_time_str = '20' + enav[0]
        last_trading_day_str = nav[0]
        try:
            real_enav_time = enav_time = datetime.strptime(enav_time_str, "%Y-%m-%d %H:%M")
            last_trading_day = datetime.strptime(last_trading_day_str, "%Y-%m-%d")
            enav_limit_time = enav_time.replace(hour=15, minute=0)
            real_enav_value = float(self._get_enav())
            nav_value = float(nav[1])
            # For timespan greater than 15:00.
            if now > enav_limit_time:
                real_enav_time = now
                # The est time/last trading day of funds are chaotic between 15:00 and 09:00.
                if last_trading_day.day == enav_time.day or real_enav_time.day != enav_time.day:
                    real_enav_value = nav_value
            enav_growth = round(real_enav_value - nav_value, 4)
            enav_rate = round(enav_growth * 100 / nav_value, 2)

            last_nav_rate = nav[2]
            last_nav_rate_value = float(last_nav_rate[0:-1])
            last_nav_growth = round(nav_value - nav_value * 100 / (last_nav_rate_value + 100), 4)

            return {'last_update': real_enav_time.strftime('%Y-%m-%d %H:%M'), 'enav': real_enav_value, 'enav_growth': enav_growth, 'enav_rate': enav_rate, 'last_trading_day': last_trading_day_str, 'last_nav': nav_value, 'last_nav_growth': last_nav_growth, 'last_nav_rate': last_nav_rate, 'rct_1month': enav[2], 'rct_3month': nav[3], 'rct_1year': enav[3]}
        except:
            _LOGGER.error('Invalid enav_value: %s, or nav_value: %s', enav[1], nav[1])
            return None

    def _get_estnav(self, estnav_data):
        nav_time = estnav_data.find('span', id='gz_gztime')
        dds = estnav_data.find_all('dd')
        if dds is None or len(dds) != 3:
            _LOGGER.error('Element \'dd\' error.')
            return None
        nav = dds[0].find('span', id='gz_gsz')
        rct_1month = dds[1].find('span', class_='ui-font-middle ui-color-green ui-num')
        if rct_1month is None:
            rct_1month = dds[1].find('span', class_='ui-font-middle ui-color-red ui-num')
        rct_1year = dds[2].find('span', class_='ui-font-middle ui-color-green ui-num')
        if rct_1year is None:
            rct_1year = dds[2].find('span', class_='ui-font-middle ui-color-red ui-num')
        if nav_time is not None:
            nav_time = nav_time.text.lstrip('(').rstrip(')')
        if nav is not None:
            nav = nav.text
        if rct_1month is not None:
            rct_1month = rct_1month.text
        if rct_1year is not None:
            rct_1year = rct_1year.text
        if nav is None or nav_time is None:
            return None          
        return (nav_time, nav, rct_1month, rct_1year)

    def _get_nav(self, nav_data):
        date = nav_data.find('dt')
        dds = nav_data.find_all('dd')
        if dds is None or len(dds) != 3:
            _LOGGER.error('Element \'dd\' error.')
            return None
        nav = dds[0].find('span', class_='ui-font-large ui-color-green ui-num')
        if nav is None:
            nav = dds[0].find('span', class_='ui-font-large ui-color-red ui-num')
        nav_rate = dds[0].find('span', class_='ui-font-middle ui-color-green ui-num')
        if nav_rate is None:
            nav_rate = dds[0].find('span', class_='ui-font-middle ui-color-red ui-num')
        rct_3month = dds[1].find('span', class_='ui-font-middle ui-color-green ui-num')
        if rct_3month is None:
            rct_3month = dds[1].find('span', class_='ui-font-middle ui-color-red ui-num')
        rct_3year = dds[2].find('span', class_='ui-font-middle ui-color-red ui-num')
        if rct_3year is None:
            rct_3year = dds[2].find('span', class_='ui-font-middle ui-color-red ui-num')
        if date is not None:
            date = re.findall(PAT_DATE, date.text)[0]
        if nav is not None:
            nav = nav.text
        if nav_rate is not None:
            nav_rate = nav_rate.text
        if rct_3month is not None:
            rct_3month = rct_3month.text
        if rct_3year is not None:
            rct_3year = rct_3year.text
        if nav is None or date is None:
            return None     
        return (date, nav, nav_rate, rct_3month, rct_3year)

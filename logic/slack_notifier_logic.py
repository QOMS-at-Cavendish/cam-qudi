# -*- coding: utf-8 -*-
"""
Logic module for sending text notifications to Slack, e.g. to notify about
errors or finished long-running operations.

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

from core.connector import Connector
from logic.generic_logic import GenericLogic
from core.configoption import ConfigOption
import requests

class SlackNotifierLogic(GenericLogic):
    """Notifier logic for Slack.

    Provides the `send_message` method that can be called
    in scripts or other modules.

    Config for copy-paste:

    slacknotifier:
        module.Class: 'slack_notifier_logic.SlackNotifierLogic'
        api_key: '<Slack bot API OAuth key>'
        channel: '#channel-to-message'
    """

    # Config options
    _api_key = ConfigOption('api_key', missing='error')
    _channel = ConfigOption('channel', missing='error')

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    def send_message(self, message):
        """Send message to Slack

        @param str message: Message to post.
        """
        try:
            requests.post('https://slack.com/api/chat.postMessage', {
                        'token':self._api_key,
                        'channel':self._channel,
                        'text':message
                        }).json()

            self.log.info('{} posted to Slack channel {}'.format(message, self._channel))

        except Exception as err:
            self.log.error('Error posting Slack message: {}'.format(err))
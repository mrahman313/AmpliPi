#!/usr/bin/python3

# AmpliPi Home Audio
# Copyright (C) 2021 MicroNova LLC
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""AmpliPi Webapp Init

This initializes the webapplication found in app.py.
"""

import os
from multiprocessing import Process, Queue
import amplipi.app

MOCK_CTRL = os.environ.get('MOCK_CTRL', 'False').lower() == 'true'
MOCK_STREAMS = os.environ.get('MOCK_STREAMS', 'False').lower() == 'true'
# we need the port for zeroconf advertisement, assume the default port 80.
# When debugginq this will need to be set to 5000!
PORT = int(os.environ.get('WEB_PORT', '80'))

application = amplipi.app.create_app(delay_saves=True, mock_ctrl=MOCK_CTRL, mock_streams=MOCK_STREAMS)

# advertise the service here, to avoid adding bloat to underlying app, especially for test startup
# this needs to be done as a separate process to avoid interfering with webserver (ZeroConf makes its own event loop)
zc_reg = Process(target=amplipi.app.advertise_service, args=(PORT, Queue())) # TODO: unregister zeroconf on shutdown?
zc_reg.start()

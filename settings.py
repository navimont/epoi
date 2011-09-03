"""Settings for epoi application"""

import os

DEBUG = os.environ['SERVER_SOFTWARE'].startswith('Dev')

# URL to fetch OSM data
OSM_API_URL = 'http://api.openstreetmap.org/api/0.6/'
#if DEBUG:
# does not work, as usual
#    OSM_API_URL = 'http://api06.dev.openstreetmap.org/api/0.6/'

# size of grid on which the download boxes are aligned (in deg))
BOX_GRID = 0.03
if DEBUG:
    BOX_GRID = 0.01

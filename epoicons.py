"""Serves the icon images from the storage Epoicon class"""

import logging
import os
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from epoidbm import Epoicon

def getIcon(filename):
    """Reads icon from storage"""
    result = db.GqlQuery("SELECT * FROM Epoicon WHERE file = :1 LIMIT 1",
                    filename).fetch(1)
    if (len(result) > 0):
        return result[0]
    else:
        return None


class ServeIcon(webapp.RequestHandler):
    """Makes it look as if icons were served from a static directory
    but in fact they are retrieved from the storage"""
    def get(self):
        iconname = os.path.basename(self.request.path)
        icon = getIcon(iconname)
        if (icon):
            self.response.headers['Content-Type'] = 'image/png'
            self.response.out.write(icon.icon)
        else:
            self.error(404)

application = webapp.WSGIApplication([('/icon/.*', ServeIcon)],debug=True)

def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()


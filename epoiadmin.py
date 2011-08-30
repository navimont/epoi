import logging
import os
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from epoidbm import Epoicon, Osmtag

icondir = 'icons'

class LoginPage(webapp.RequestHandler):
    def get(self):
        self.redirect(users.create_login_url('index.html'))

class LogoutPage(webapp.RequestHandler):
    def get(self):
        self.redirect(users.create_logout_url('index.html'))

class EpoiAdminPage(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()

        # not logged in
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return

        template_values = {'nickname': user.nickname()}

        # not an administrator
        if not users.is_current_user_admin():
            path = os.path.join(os.path.dirname(__file__), 'sorrynoadmin.html')
            self.response.out.write(template.render(path, template_values))
            return

        # find all icons in icondir directory
        # note that icondir is only used to import new icon files
        # into the storage. The files will later be served from
        # the storage, not from icondir!
        iconfiles = os.listdir(icondir)
        # keep only those with ending *.png
        iconfiles = [ic for ic in iconfiles if ic.endswith('.png') ]
        logging.debug ("%3d     iconfiles found: %s" % (len(iconfiles),[", ".join(iconfiles)]))

        # find all existing epoi icons in the storage
        dbicons = Epoicon.all().fetch(1000)
        dbiconfiles = [dbi.file for dbi in dbicons]
        logging.debug ("%3d icons in storage" % (len(dbiconfiles)))

        #
        # Those icons which are in the file list but not in the storage
        # have to be added to the storage
        #
        new_icons = set(iconfiles).difference(set(dbiconfiles))
        logging.debug ("%3d new iconfiles found: %s" % (len(new_icons),[", ".join(new_icons)]))
        imported_icons = []
        for ni in new_icons:
            try:
                fp = open(os.path.join(icondir,ni), 'rb')
                try:
                    icondata = fp.read()
                finally:
                    fp.close()
                imported_icons.append(ni)
            except IOError:
                logging.critical("Could not read file %s/%s" % (icondir,ni))
            # The name has to be adjusted by the user. For now use
            # the upper case filename without ending
            dbi = Epoicon(name=ni[:-4].upper(), file=ni, icon=icondata)
            dbi.put()
        logging.debug ("%3d iconfiles imported:  %s" % (len(imported_icons),[",".join(imported_icons)]))

        # read again after import
        dbicons = Epoicon.all()
        logging.debug ("%3d icons in database" % (dbicons.count()))

        template_values['icons'] = [dbi.file for dbi in dbicons]

        # render administration page
        path = os.path.join(os.path.dirname(__file__), 'epoiadmin.html')
        self.response.out.write(template.render(path, template_values))


application = webapp.WSGIApplication([('/epoiadmin', EpoiAdminPage),
                                      ('/login', LoginPage),
                                      ('/logout', LogoutPage)],debug=True)

def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()


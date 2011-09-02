import logging
import os
import json
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.db import Key
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
        dbicons = Epoicon.all()
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

        icons = []
        for epi in Epoicon.all():
            icons.append({'file': os.path.join('icon',epi.file),
                          'id':str(epi.key()),
                          'name':epi.name})

        template_values['icons'] = icons

        # render administration page
        path = os.path.join(os.path.dirname(__file__), 'epoiadmin.html')
        self.response.out.write(template.render(path, template_values))

class EpoiAdminExportIcons(webapp.RequestHandler):
    """Export the relation between icons and osm tags (backup)"""
    def get(self):

        logging.info("preparing icons for json export")
        icons = []
        for epi in Epoicon.all():
            icon = {'key': str(epi.key()), 'file': epi.file, 'name': epi.name}
            icons.append(icon)

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(icons, indent=2))



class EpoiAdminImportIcons(webapp.RequestHandler):
    """Import the relation between icons and osm tags (restore)"""
    def get(self):
        file = self.request.get('file')
        if not file:
            logging.Error ("No 'file' in URL parameters")
            self.error(500)
            return

        try:
            fp = open(file,'r')
        except IOError:
            logging.Error ("Can't open backup file: %s" % (file))
            self.error(500)
            return

        icons = json.load(fp)
        for icon in icons:
            # open icon file
            try:
                iconfp = open(os.path.join(icondir,icon['file']),'r')
            except IOError:
                logging.Error ("Can't open icon file: %s/%s" % (icondir,file))
                continue

            # instantiate icon object
            epoicon = Epoicon(key=icon['key'], name=icon['name'], file=icon['file'], icon=iconfp.read())
            iconfp.close()
            epoicon.put()

        fp.close()
        self.redirect('/epoiadmin')


class EpoiAdminEditIconPage(webapp.RequestHandler):
    """Manage relations between epoi icons and osm tags"""
    def get(self):
        user = users.get_current_user()

        # TODO: Provide a decorator function for these checks
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

        # retrieve icon key and check it
        id = self.request.get('id')
        if not id:
            logging.error ('id parameter missing in URL')
            self.error(500)
            return
        action = self.request.get('action')
        name = self.request.get('name', None)

        logging.debug ('id: %s action: %s' % (id,action))
        epoicon = Epoicon.get(id)
        if not epoicon:
            self.error(500)
            return

        # update icon name
        if name and epoicon.name != name:
            epoicon.name = name
            epoicon.put()

        if action == 'delete':
            epoicon.delete()
            # go back to icon list page
            self.redirect('/epoiadmin')
        elif action == 'clone':
            # clone icon definition
            epoicon1 = Epoicon(name=epoicon.name,
                              file=epoicon.file,
                              icon=epoicon.icon)
            epoicon1.put()
        elif action == 'done':
            # go back to icon list page
            self.redirect('/epoiadmin')
        else:
            pass

        icon = {'file': os.path.join('icon',epoicon.file),
                'id': str(epoicon.key()),
                'name':epoicon.name}

        template_values['icon'] = icon

        # render administration page
        path = os.path.join(os.path.dirname(__file__), 'epoiadminicon.html')
        self.response.out.write(template.render(path, template_values))



application = webapp.WSGIApplication([('/epoiadmin/icon.*', EpoiAdminEditIconPage),
                                      ('/epoiadmin', EpoiAdminPage),
                                      ('/epoiadmin/importicons.*', EpoiAdminImportIcons),
                                      ('/epoiadmin/exporticons', EpoiAdminExportIcons),
                                      ('/login', LoginPage),
                                      ('/logout', LogoutPage)],debug=True)

def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()


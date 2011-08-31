import logging
import os
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

        #
        # Define data structure for the template
        # categories = List of category/[epicon] tuples for the icons
        # categories(1) ---- category string
        # categories(2) ---- list of epoicons
        #                      +-- name = clear text name (e.g. Hotel)
        #                      +-- icon = png icon image
        #                      +-+ osm_tags = a list of osm_tag key-value pairs
        #                        +-- k
        #                        +-- v
        #
        categories = []
        # categorize icons based on their osm_tags
        # (an icon can be in more than one category)
        osmtags = Osmtag.all()
        for tag in osmtags:
            icon_with_tag = Epoicon.all()
            icon_with_tag.filter("osm_tags =", tag.key())
            icons = []
            for epi in icon_with_tag:
                icons.append({'file': os.path.join('icon',epi.file),
                             'id':str(epi.key()),
                             'name':epi.name})
            categories.append((tag.k, icons))

        # find unused icons in the data storage
        unused = []
        for epi in Epoicon.all():
            if len(epi.osm_tags) < 1:
                unused.append({'file': os.path.join('icon',epi.file),
                               'id':str(epi.key()),
                               'name':epi.name})
        categories.append(('not used', unused))

        template_values['categories'] = categories

        # render administration page
        path = os.path.join(os.path.dirname(__file__), 'epoiadmin.html')
        self.response.out.write(template.render(path, template_values))

class EpoiAdminEditIconPage(webapp.RequestHandler):
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
        key = self.request.get('key')
        value = self.request.get('value')
        action = self.request.get('action')

        logging.debug ('id: %s (key: %s value: %s) action: %s' % (id,key,value,action))
        epoicon = Epoicon.get(id)
        if not epoicon:
            self.error(500)

        # store key/value pair if add was pressed
        if action == 'add' and key and value:
            # don't save duplicates in Osmtag entity
            qosmtag = Osmtag.all()
            qosmtag.filter('k =', key)
            qosmtag.filter('v =', value)
            osmtag = qosmtag.fetch(1)
            if len(osmtag) < 1:
                osmtag = Osmtag(k=key, v=value)
                osmtag.put()
            else:
                osmtag = osmtag[0]
            # store relation but don't save duplicates in list either
            if not osmtag.key() in epoicon.osm_tags:
                epoicon.osm_tags.append(osmtag.key())
                epoicon.put()
        elif action == 'delete':
            # delete icon definition
            epoicon.delete()
            # go back to icon list page
            self.redirect('/epoiadmin')
        elif action.startswith('tagdelete'):
            # get osmtag key from action string
            key = action.split("_")[-1]
            logging.debug("action tagdelete key: %s" % (key))
            epoicon.osm_tags.remove(Key(key))
        elif action == 'clone':
            # clone icon definition
            epoicon1 = Epoicon(name=epoicon.name,
                              file=epoicon.file,
                              icon=epoicon.icon,
                              osm_tags=epoicon.osm_tags)
            epoicon1.put()
        elif action == 'done':
            # go back to icon list page
            self.redirect('/epoiadmin')
        else:
            pass


        # retrieve osm tags
        osmtags = []
        for osmtag_key in epoicon.osm_tags:
            osmtag = Osmtag.get(osmtag_key)
            osmtags.append({'id': str(osmtag_key),
                            'k': osmtag.k,
                            'v': osmtag.v})

        icon = {'file': os.path.join('icon',epoicon.file),
                'id': str(epoicon.key()),
                'name':epoicon.name}

        template_values['icon'] = icon
        template_values['osmtags'] = osmtags

        # render administration page
        path = os.path.join(os.path.dirname(__file__), 'epoiadminicon.html')
        self.response.out.write(template.render(path, template_values))



application = webapp.WSGIApplication([('/epoiadmin/icon.*', EpoiAdminEditIconPage),
                                      ('/epoiadmin', EpoiAdminPage),
                                      ('/login', LoginPage),
                                      ('/logout', LogoutPage)],debug=True)

def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()


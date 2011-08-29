import logging
import os
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app


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

        # go to administration page
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


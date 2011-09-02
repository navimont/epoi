import logging
import os
import xml.sax
import urllib2
import geo.geotypes
import yaml
from epoidbm import Epoicon, Osmtag, Epoi
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

# Internal representation of epoicon.yaml file
Tags2Epoi = []
# all osm tags (key/value pairs) which are stored
TagsOfInterest = []
# same, but only the keys
KeysOfInterest = []

class OSMXMLFileParser(xml.sax.ContentHandler):
    def __init__(self):
        logging.debug ("Keys of interest: %s" % (", ".join(KeysOfInterest)))
        self.epoi = None
        self.isPoi = False

    def startElement(self, name, attrs):
        self.isPoi = False
        if name == 'node':
            # look for existing entity
            qepoi = Epoi.all()
            qepoi.filter("osm_id =", long(attrs['id']))
            self.epoi = qepoi.fetch(1)
            if len(self.epoi) > 0:
                self.epoi = self.epoi[0]
                # node is already in storage. check version.
                if self.epoi.version == int(attrs['version']):
                    # unchanged, skip it
                    self.epoi = None
                    return
            else:
                # Create new entity.
                self.epoi = Epoi(osm_id=long(attrs['id']), version=0, name="<no name>", location=db.GeoPt(0,0))
            # Update existing or fill new entity.
            # It will only be stored if we find the right tags (later)
            self.epoi.location = db.GeoPt(float(attrs['lat']), float(attrs['lon']))
            self.epoi.version = int(attrs['version'])

        elif name == 'way':
            pass

        elif name == 'tag':
            if self.epoi:
                if attrs['k'] == 'name':
                    self.epoi.name = attrs['v']
                if attrs['k'] == 'web':
                    self.epoi.web = attrs['v']
                if attrs['k'] in KeysOfInterest:
                    self.isPoi = True
                    # find it in Osmtag table and add there if new
                    qosmtag = Osmtag.all()
                    qosmtag.filter("k =", attrs['k'])
                    qosmtag.filter("v =", attrs['v'])
                    osmtag = qosmtag.fetch(1)
                    if len(osmtag) < 1:
                        # store new osmtag
                        osmtag = Osmtag(k=attrs['k'], v=attrs['v'])
                        osmtag.put()
                        logging.debug ("Stored osmtag %s=%s" % (attrs['k'], attrs['v']))
                    else:
                        osmtag = osmtag[0]
                    # update reference in epoi entity
                    if not (osmtag.key() in self.epoi.osm_tags):
                        self.epoi.osm_tags.append(osmtag.key())

        elif name == "nd":
            pass

        # not important for us
        elif name == "osm":
            pass
        elif name == "relation":
            pass
        elif name == "member":
            pass
        elif name == "bounds":
            pass
        else:
            logging.error ("Don't know element %s" % (name))


    def endElement(self, name):
        if name == "node":
            if self.epoi and self.isPoi:
                # This is needed for GeoModel location cells update
                self.epoi.update_location()
                self.epoi.put()
                logging.debug ("Stored epoi osm_id: %d name: %s" % (self.epoi.osm_id, self.epoi.name))

        elif name == "way":
            pass

        elif name == "relation":
            pass
        elif name == "osm":
            pass
        else:
            pass

def parseOSMXMLFile(filename=None, content=None):
    """
    Use this class to load and parse OSM files.
    """
    handler = OSMXMLFileParser()
    if content:
        xml.sax.parseString(content, handler)
    else:
        xml.sax.parse(filename, handler)


def apiDownload(predicate=None,box=None):
    """
    Download data using the OSM XAPI.
    Specify a bounding box type geotypes.Box
    Returns the XML data.
    """

    url = "http://open.mapquestapi.com/xapi/api/0.6/node[%s][bbox=%f,%f,%f,%f]" % (predicate,Box.south,Box.west,Box.north,Box.east)

    logging.info("Asking OSM xapi for: %s" % url)

    # use the opener to fetch a URL
    response = urllib2.urlopen(url)

    # parse response and return nodes


def nineBoxes(lat,lon):
    """Calculate the bounding box wich incorporates the
    lat lon coordinate and is aligned to a grid.
    Return this box and the eight surrounding boxes
    as geotype.Box class objects."""
    grid = 0.03

    nlat = int(lat/grid)*grid
    nlon = int(lon/grid)*grid

    boxes = []
    for ilat in (nlat-grid,nlat,nlat+grid):
        for ilon in (nlon-grid,nlon,nlon+grid):
            boxes.append(geo.geotypes.Box(ilat+grid, ilon+grid, ilat, ilon))

    return boxes

def osmtagToEpoi(tags):
    """Finds the right epoi icon for a list of key/value pairs"""

    pass


class EpoiServerTest(webapp.RequestHandler):
    """Runs a testfile through the parser. Call with filename as URL parameter"""

    def get(self):
        file = self.request.get('file')
        if not file:
            self.error(500)
            return

        logging.debug("file: %s", (file))

        # check if file exists
        if not os.path.isfile(file):
            self.error(404)
            return

        parseOSMXMLFile(filename=file)

        self.response.out.write("<html><body>")
        for epoi in Epoi.all():
            self.response.out.write("<br>osm id: %d name: %s osm_tags: %s" % (epoi.osm_id, epoi.name, ", ".join(["/".join((Osmtag.get(key).k,Osmtag.get(key).v)) for key in epoi.osm_tags])))
        self.response.out.write("<body><html>")


class EpoiServerPopulate(webapp.RequestHandler):
    """Receive bounding box coordinates. If data is not yet in
    database, download from xapi
    The purpose of this function is to populate the database
    once. Later on, updates via OSM api will only be done when the user
    actually works on a small area."""

    def get(self):
        minlat = self.request.get('minlat',0)
        minlon = self.request.get('minlon',0)
        maxlat = self.request.get('maxlat',0)
        maxlon = self.request.get('maxlon',0)

        # some checks
        if minlon > maxlon or minlat > maxlat:
            logging.error ("coordinate parameters in wrong order")
            self.error(500)
            return
        # calculate center point of box and from there a 0.09 * 0.09 download area
        center_lat = minlat + (maxlat-minlat) / 2
        center_lon = minlon + (maxlon-minlon) / 2
        bboxes = nineBoxes(center_lat,center_lon)

        #
        # Check if area is already in storage and if not, download
        #

        for box in bboxes:
            # geotype box __init__ parameters are: north, east, south, west
            # checks if there is at least one point in this box in the storage
            results = Epoi.bounding_box_fetch(Epoi.all(), box, max_results=1)
            if len(result) == 0:
                # load box from xapi
                for tag in TagsOfInterest:
                    apiDownload(tag,box)
                    # TODO store in database
                    pass


application = webapp.WSGIApplication([('/epoiserver', EpoiServerPopulate),
                                      ('/epoiserver/test.*', EpoiServerTest)])

def main():
    global TagsOfInterest, KeysOfInterest
    logging.getLogger().setLevel(logging.DEBUG)
    # read and parse definition for osmtag to icon relation
    filename = 'epoicons.yaml'
    try:
        fp = open(filename)
    except IOError:
        logging.Critical("Can't open file %s" %(filename))
        fp = None
    if fp:
        try:
            Tags2Epoi = yaml.load(fp)
        except yaml.YAMLError, exc:
            logging.Critical ("Error in configuration file: %s" (exc))
            Tags2Epoi = []
        fp.close()
    # Extract all tags of interest from the configuration
    tags = []
    for icon in Tags2Epoi:
        for key,value in icon['tags'].items():
            tags.append("%s=%s" % (key, value))
    # convert to set to remove duplicates
    TagsOfInterest = set(tags)
    KeysOfInterest = set([k.split('=')[0] for k in TagsOfInterest])
    logging.debug ("Tags of interest: %s" % (", ".join(TagsOfInterest)))
    logging.debug ("Keys of interest: %s" % (", ".join(KeysOfInterest)))

    run_wsgi_app(application)

if __name__ == "__main__":
    main()


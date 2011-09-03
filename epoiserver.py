import logging
import os
import xml.sax
import geo.geotypes
import json
import yaml
import settings
from epoidbm import Epoicon, Osmtag, Epoi
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.api import urlfetch
from google.appengine.ext.webapp.util import run_wsgi_app

# Internal representation of epoicon.yaml file
Tags2Epoi = []
# same, but only the keys
KeysOfInterest = []
# counter for stored poi
PoiCounter = 0

class OSMXMLFileParser(xml.sax.ContentHandler):
    def __init__(self):
        self.counter = 0
        self.epoi = None

    def startElement(self, name, attrs):
        self.isPoi = False
        self.counter = self.counter+1
        if not (self.counter % 300):
            logging.debug ("Parsed %06d elements and going..." % self.counter)

        if name == 'node':
            self.osm_tags = []
            self.isPoi = False
            # Always store data in new entity while parsing.
            # In the end, decide whether it is written to storage
            self.epoi = Epoi(osm_id=long(attrs['id']),
                            version=int(attrs['version']),
                            name="<no name>",
                            location=db.GeoPt(float(attrs['lat']),float(attrs['lon'])))

        elif name == 'way':
            self.osm_tags = []
            pass

        elif name == 'tag':
            if self.epoi:
                if attrs['k'] == 'name':
                    self.epoi.name = attrs['v']
                if attrs['k'] == 'web':
                    self.epoi.web = attrs['v']
                if attrs['k'] in KeysOfInterest:
                    self.isPoi = True
                    self.osm_tags.append((attrs['k'], attrs['v']))

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
        global PoiCounter
        if name == "node":
            if self.epoi and self.isPoi:
                # look for existing entity
                qepoi = Epoi.all()
                qepoi.filter("osm_id =", self.epoi.osm_id)
                epoi = qepoi.fetch(1)
                if len(epoi) > 0:
                    epoi = epoi[0]
                    # node is already in storage. check version.
                    if epoi.version < self.epoi.version:
                        # overwrite existing point, keep attributes
                        # which don't come from OSM
                        self.epoi.pic = epoi.pic
                    else:
                        # unchanged, skip it
                        return
                # find  in Osmtag table and add there if new
                for key,value in self.osm_tags:
                    qosmtag = Osmtag.all()
                    qosmtag.filter("k =", key)
                    qosmtag.filter("v =", value)
                    osmtag = qosmtag.fetch(1)
                    if len(osmtag) < 1:
                        # store new osmtag
                        osmtag = Osmtag(k=key, v=value)
                        osmtag.put()
                        logging.debug ("Stored osmtag %s=%s" % (key, value))
                    else:
                        osmtag = osmtag[0]
                    # update reference in epoi entity
                    if not (osmtag.key() in self.epoi.osm_tags):
                        self.epoi.osm_tags.append(osmtag.key())
                # This is needed for GeoModel location cells update
                self.epoi.update_location()
                self.epoi.put()
                PoiCounter = PoiCounter+1
                logging.debug ("Stored epoi osm_id: %d name: %s tags %s" %
                  (self.epoi.osm_id,
                    self.epoi.name,
                    ", ".join([("%s=%s") % (Osmtag.get(key).k,Osmtag.get(key).v) for key in self.epoi.osm_tags])))

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


def apiDownload(box=None):
    """
    Download data using the OSM XAPI.
    Specify a bounding box type geotypes.Box
    Stores the result in db
    """
    global PoiCounter
    url = "%smap?bbox=%f,%f,%f,%f" % (settings.OSM_API_URL,box.west,box.south,box.east,box.north)

    logging.info("Asking OSM xapi for: %s" % url)

    try:
        res = urlfetch.fetch(url, method=urlfetch.GET, deadline=33)
    except urlfetch.DownloadError:
        logging.error("Timeout for: %s" % url)
        return

    logging.info ("Received: %3.1fkB content-type: %s url: %s" % (float(len(res.content))/1000.0,res.headers['content-type'],res.final_url))
    if not res.headers['content-type'].startswith('text/xml'):
        logging.error("Wrong content type in reply: %s" % res.headers['content-type'])
        return

    PoiCounter = 0
    parseOSMXMLFile(content=res.content)
    logging.debug ("Stored %d POI" % PoiCounter)

def nineBoxes(lat,lon):
    """Calculate the bounding box wich incorporates the
    lat lon coordinate and is aligned to a grid.
    Return this box and the eight surrounding boxes
    as geotype.Box class objects."""
    grid = settings.BOX_GRID

    nlat = int(lat/grid)*grid
    nlon = int(lon/grid)*grid

    boxes = []
    for ilat in (nlat-grid,nlat,nlat+grid):
        for ilon in (nlon-grid,nlon,nlon+grid):
            boxes.append(geo.geotypes.Box(ilon+grid, ilat+grid, ilon, ilat))

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


class EpoiServerPopulate(webapp.RequestHandler):
    """Receive bounding box coordinates and return points of interest in this box.
    POI (epoi entities) are returned from storage after a few seconds.
    If the storage does not hold any POI at the given box, data is downloaded
    asynchronously from the OSM Api.
    As download may continue while the server already responded (with no or
    too few or outdated POI) a second call may be necessary.
    Bounding box is specified by the URL parameters minlon, maxlon, minlat, maxlat
    If cache=False is set as a parameter, new downloads are initiated.
    max_results=n may be set, too (Default is 60)
    """
    def get(self):
        bbox = self.request.get('bbox',"0,0,0,0").split(',')
        minlat = float(bbox[0])
        minlon = float(bbox[1])
        maxlat = float(bbox[2])
        maxlon = float(bbox[3])
        if self.request.get('cache',"") == 'False':
            cache = False
        else:
            cache = True
        max_results = int(self.request.get('max_results',60))

        logging.info ("populate bbox minlon: %3.6f maxlon: %3.6f minlat: %3.6f maxlat: %3.6f cache: %d"
                      % (minlon,maxlon,minlat,maxlat,cache))

        return

        # some checks
        if minlon > maxlon or minlat > maxlat:
            logging.error ("coordinate parameters in wrong order")
            self.error(500)
            return
        # calculate center point of box and from there the surrounding
        # grid boxes for download
        center_lat = minlat + (maxlat-minlat) / 2
        center_lon = minlon + (maxlon-minlon) / 2
        bboxes = nineBoxes(center_lat,center_lon)

        #
        # Check if area is already in storage and if not, download
        #

        for box in bboxes:
            # geotype box __init__ parameters are: north, east, south, west
            # checks if there is at least one point in this box in the storage
            results = Epoi.bounding_box_fetch(Epoi.all(), box, max_results=11)
            if len(results) == 0 or not cache:
                # load box from osm api
                apiDownload(box)
            else:
                logging.debug("skip bbox for download; west: %3.3f south: %3.3f east: %3.3f north: %3.3f"
                          % (box.west,box.south,box.east,box.north))

        #
        # Build result object GeoJSON
        #

        result = {"type": "FeatureCollection",
                  "bbox": [minlon,minlat,maxlon,maxlat]}
        res = Epoi.bounding_box_fetch(Epoi.all(),
                geo.geotypes.Box(maxlon, maxlat, minlon, minlat),
                max_results=max_results)
        features = []
        feature = {}
        for epoi in res:
            feature['type'] = "Feature"
            feature['geometry'] = {"type": "Point", "coordinates": [epoi.location.lon,epoi.location.lat]}
            properties = {}
            for key in epoi.osm_tags:
                prop = Osmtag.get(key)
                properties[prop.k] = prop.v
            feature['properties'] = properties
            features.append(feature)
        result['features'] = features

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(result))


application = webapp.WSGIApplication([('/epoiserver/test.*', EpoiServerTest),
                                      ('/epoiserver.*', EpoiServerPopulate)])

def main():
    global KeysOfInterest
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
    # Extract all keys of interest from the configuration
    keys = []
    for icon in Tags2Epoi:
        for key,value in icon['tags'].items():
            keys.append(key)
    # convert to set to remove duplicates
    KeysOfInterest = set(keys)
    logging.debug ("Keys of interest: %s" % (", ".join(KeysOfInterest)))

    run_wsgi_app(application)

if __name__ == "__main__":
    main()


import logging
import os
import xml.sax
import urllib2
import geo.geotypes
from epoidbm import Epoicon, Osmtag, Epoi
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

TagsOfInterest = (
    'amenity=*',
    'leisure=*',
    'office=*',
    'shop=*',
    'craft=*',
    'emergency=*',
    'tourism=*',
    'historic=*',
    'sport=*',
    # to capture station nodes
    'public_transport=*',
    'railway=*',
    'aerialway=*',
    'railway=*',
    'waterway=*'
)

class Node(object):
    def __init__(self, attr, tags=None):
        if not attr.get('id', None):
            attr['id'] = str(IDFactory.id())
        self.id = int(attr['id'])
        self.lon = attr['lon']
        self.lat = attr['lat']
        self.version = int(attr.get('version','1'))
        self.visible = attr.get('visible',None)
        if tags:
            self.tags = tags
        else:
            self.tags = {}

class Way(object):
    def __init__(self, attr, nodes=None, tags=None):
        self.id = int(attr['id'])
        self.version = int(attr.get('version','1'))
        self.visible = attr.get('visible',None)

        if nodes:
            self.nodes = nodes
        else:
            self.nodes = []
        if tags:
            self.tags = tags
        else:
            self.tags = {}

class OSMXMLFileParser(xml.sax.ContentHandler):
    def __init__(self, containing_obj):
        # the OSMXMLFile object is in containing_obj parameter
        self.containing_obj = containing_obj

        self.curr_node = None
        self.curr_way = None
        self.curr_relation = None
        self.curr_osmattrs = None

    def startElement(self, name, attrs):
        if name == 'node':
            self.curr_node = Node(attr=attrs)

        elif name == 'way':
            self.curr_way = Way(attr=attrs)

        elif name == 'tag':
            if self.curr_node:
                self.curr_node.tags[attrs['k']] = attrs['v']
            elif self.curr_way:
                self.curr_way.tags[attrs['k']] = attrs['v']
            elif self.curr_relation:
                self.curr_relation.tags[attrs['k']] = attrs['v']

        elif name == "nd":
            assert self.curr_node is None, "curr_node (%r) is non-none" % (self.curr_node)
            assert self.curr_way is not None, "curr_way is None"
            self.curr_way.nodes.append(attrs['ref'])

        elif name == "osm":
            self.curr_osmattrs = attrs

        # not important for us
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
            # write directly to the node dictionary of OSMXMLFile class
            self.containing_obj.nodes[self.curr_node.id] = self.curr_node
            self.curr_node = None

        elif name == "way":
            self.containing_obj.ways[self.curr_way.id] = self.curr_way
            self.curr_way = None

        elif name == "relation":
            pass

        elif name == "osm":
            self.containing_obj.osmattrs = self.curr_osmattrs
            self.curr_osmtags = None

class OSMXMLFile(object):
    """
    Use this class to load and parse OSM files.
    """
    def __init__(self, filename=None, content=None):
        self.filename = filename

        # will be filled by OSMXMLFileParser node by node
        # dic format: {nodeid: NODE, ...}
        self.nodes = {}
        self.ways = {}
        self.osmattrs = {'version':'0.6'}
        if filename:
            self.__parse()
        elif content:
            self.__parse(content)

    def __parse(self, content=None):
        """Parse the given XML file"""
        handler = OSMXMLFileParser(self)
        if content:
            xml.sax.parseString(content, handler)
        else:
            xml.sax.parse(self.filename, handler)

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
    lat lon coordinate and is aligned at a 0.04 deg grid.
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

        osm = OSMXMLFile(filename=file)

        self.response.out.write("<html><body>")
        self.response.out.write("nodes: %d" % len(osm.nodes))
        self.response.out.write("<br>ways: %d" % len(osm.ways))
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
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()


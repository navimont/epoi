import geo.geomodel
from google.appengine.ext import db

class Osmtag(db.Model):
    """OSM tag key/value pair"""
    k = db.StringProperty(required=True)
    v = db.StringProperty(required=True)

class Epoicon(db.Model):
    """Icon and category name used for POI in epoi.
    An epoi tag represents a single osm_tag (such as tourism: hotel)
    or a combination of tags (tourism: hotel; stars: 3)"""
    name = db.StringProperty(required=True)
    # file name of icon (includes path)
    file = db.StringProperty(required=True)
    # the icon itself
    icon = db.BlobProperty(required=True)
    # references to one or more osm_tags
    osm_tags = db.ListProperty(db.Key)

class Epoi(geo.geomodel.GeoModel):
    """Point of interest as was loaded from the OSM database"""
    # 64 bit osm key
    osm_id = db.IntegerProperty(required=True)
    # lat/lon location is inherited from GeoModel
    # node's version in the osm database
    version = db.IntegerProperty(required=True)
    # English name which is used for display.
    # name properties in other languages may be added
    # in Epoi_ext entity ()such as name_de, name_es)
    name = db.StringProperty(required=True)
    # web address of the place
    web = db.LinkProperty()
    # a list of icons (categories) which apply to the object.
    # Why more than one? The node may represent a hotel AND a restaurant
    epoicons = db.ListProperty(db.Key)

class Epoi_ext(db.Expando):
    """Extended properties for an epoi entity. It is defined
    as a separate entity because I need to use GeoModel as a
    base class for Epoi. GeoModel is based on db.Model .
    When using extended properties (like name_es) the epoi
    instance must be defined as the epoi_ext parent."""
    # a list of pics of the place
    pics = db.ListProperty(db.Blob)

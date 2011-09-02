import geo.geomodel
from google.appengine.ext import db

class Osmtag(db.Model):
    """OSM tag key/value pair"""
    k = db.StringProperty(required=True)
    v = db.StringProperty(required=True)

class Epoicon(db.Model):
    """Icon and category name used for POI in epoi."""
    # Caption for the icon (this is also the 'name')
    # in configuration file epoicon.yaml
    name = db.StringProperty(required=True)
    # file name of icon (includes path)
    file = db.StringProperty(required=True)
    # the icon itself
    icon = db.BlobProperty(required=True)

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
    # pics of the place
    pic = db.BlobProperty
    # web address of the place
    web = db.LinkProperty(required=False)
    # reference to the OSM tags (key/value pairs) for this
    # object. Only those keys are taken into account
    # which are used in the epoicon.yaml definition file.
    osm_tags = db.ListProperty(db.Key)

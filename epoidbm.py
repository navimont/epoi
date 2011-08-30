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
    # file name of icon
    file = db.StringProperty(required=True)
    # the icon itself
    icon = db.BlobProperty(required=True)
    # references to one or more osm_tags
    osm_tags = db.ListProperty(db.Key)


class Epoi(db.Expando):
    """Point of interest as was loaded from the OSM database at timestamp"""
    # 64 bit osm key
    osm_id = db.IntegerProperty(required=True)
    # lat/lon location
    location = db.GeoPtProperty(required=True)
    # date/time when loaded from the OSM database
    timestamp = db.DateTimeProperty(required=True)
    # English name which appears (more name properties may be added
    # such as name_de, name_es)
    name = db.StringProperty(required=True)
    # web address of the place
    web = db.LinkProperty()
    # a list of pics of the place
    pics = db.ListProperty(db.Blob)
    # a list of tags (categories) which apply to the object.
    # Why more than one? The node may represent a hotel AND a restaurant
    categs = db.ListProperty(db.Key)

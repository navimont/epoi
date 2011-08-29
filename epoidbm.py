from google.appengine.ext import db

class osm_tag(db.Model):
"""OSM tag key/value pair"""
    k = db.StringProperty(required=True)
    v = db.StringProperty(required=True)

class epoi_tag(db.Model):
"""Icon and category name used for POI in epoi.
An epoi tag represents a single osm_tag (such as tourism: hotel)
or a combination of tags (tourism: hotel; stars: 3)"""
    name = db.StringProperty(required=True)
    icon = db.BlobProperty(required)
    # references to one or more osm_tags
    osm_tags = db.ListProperty(db.Key)


class epoi(db.Expando):
"""Point of interest as was loaded from the OSM database at timestamp"""
    # 64 bit osm key
    osm_id = db.IntegerProperty(required=True)
    # lat/lon location
    location = db.GeoPtProperty()
    # date/time when loaded from the OSM database
    timestamp =
    name = db.StringProperty(required=True)
    web = db.LinkProperty()
    # a list of pics of the object
    pics = db.ListProperty(db.Blob)
    # a list of tags (categories) which apply to the object.
    # Why more than one? The node may represent a hotel AND a restaurant
    categs = db.ListProperty(db.Key)

from pylons import request

from adhocracy.lib import helpers as h
from adhocracy.lib.base import BaseController
from adhocracy.lib.templating import render_json, render_geojson
from adhocracy.lib.util import get_entity_or_abort
from adhocracy.model import meta
from adhocracy.model import Region
from adhocracy.model import Instance

from sqlalchemy import func
from sqlalchemy import or_

import geojson
from shapely.wkb import loads
from shapely.geometry import Polygon, MultiPolygon, box

import logging
log = logging.getLogger(__name__)


USE_POSTGIS = 'USE_POSTGIS'
USE_SHAPELY = 'USE_SHAPELY'

BBOX_FILTER_TYPE = USE_POSTGIS
SIMPLIFY_TYPE = USE_SHAPELY

COMPLEXITY_TOLERANCE = {
    '0': 0.5,
    '1': 0.1,
    '2': 0.02,
    '3': 0.005,
    '4': 0.001
    }

class GeoController(BaseController):

    def get_boundaries_json(self):
        admin_level = request.params.get('admin_level')
        
        complexity = request.params.get('complexity')
        tolerance = COMPLEXITY_TOLERANCE[complexity]

        bbox = map(float, request.params.get('bbox').split(','))
        assert(len(bbox)==4)

        q = meta.Session.query(Region)
        q = q.filter(Region.admin_level == admin_level)

        if BBOX_FILTER_TYPE == USE_POSTGIS:
            q = q.filter(Region.boundary.intersects(func.setsrid(func.box2d('BOX(%f %f, %f %f)'%(tuple(bbox))), 4326)))

        if SIMPLIFY_TYPE == USE_POSTGIS:
            # NYI
            pass

        def make_feature(region):
            return dict(geometry = loads(str(region.boundary.geom_wkb)), properties = {'label': region.name, 'admin_level': region.admin_level})

        if BBOX_FILTER_TYPE == USE_SHAPELY:
            sbox = box(*bbox)
            regions = filter(lambda region: sbox.intersection(region['geometry']), map(make_feature, q.all()))

        elif BBOX_FILTER_TYPE == USE_POSTGIS:

            regions = map(make_feature, q.all())

        if SIMPLIFY_TYPE == USE_SHAPELY:

            def simplify_region(region):
                if region['geometry'].is_valid:
                    geom_simple = region['geometry'].simplify(tolerance, True)
                    if geom_simple.is_valid and geom_simple.area != 0:
                        region['geometry'] = geom_simple
                    else:
                        log.warn('invalid simplified geometry for %s'%region['properties']['label'])
                else:
                    log.warn('invalid geometry for %s'%region['properties']['label'])
                return region

            regions = map(simplify_region, regions)

        return render_geojson(geojson.FeatureCollection([geojson.Feature(**r) for r in regions]))

    def find_instances_json(self):
        max_rows = request.params.get('max_rows')
        name_contains = request.params.get('name_contains')
        callback = request.params.get('callback')

#        q = meta.Session.query(Region.name,Region.admin_level).add_column(Region.get_instances).order_by(Region.name)
        q = meta.Session.query(Region).order_by(Region.name)
        q = q.filter(or_(or_(Region.admin_level == 6, Region.admin_level == 7),Region.admin_level == 8))
#        q = q.filter(Region.name.in_(name_contains))
        q = q.filter(Region.name.like('%' + name_contains + '%'))
#        q = q.offset(search_offset).limit(search_count-search_offset)
        regions = q.all()

        response = dict()
        num_hits = len(regions)

        def create_entry(region):
            instances = getattr(region,"get_instances")
            entry = dict()
            if instances != []: 
                instance = get_entity_or_abort(Instance, instances[0].id)
                entry['id'] = instance.id
                entry['url'] = h.entity_url(instances[0])
                entry['admin_level'] = region.admin_level
                entry['num_proposals'] = instance.num_proposals
                entry['num_papers'] = 'nyi'
                entry['num_members'] = instance.num_members
                entry['create_date'] = str(instance.create_time.date())
            else: entry['id'] = ""
            entry['name'] = region.name
            return entry

        search_result = map(create_entry, regions)
        response['count'] = num_hits
        response['search_result'] = search_result
        return callback + '(' + render_json(response) + ');'

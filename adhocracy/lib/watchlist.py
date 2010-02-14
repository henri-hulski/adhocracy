import logging
from datetime import datetime
import urllib

from sqlalchemy import or_
from sqlalchemy.orm import eagerload

from pylons import tmpl_context as c, request
import formencode

import adhocracy.model as model
import adhocracy.model.refs as refs


log = logging.getLogger(__name__)


def find_watch(entity):
    return model.Watch.find_by_entity(c.user, entity)


def make_watch(entity):
    return urllib.urlencode({'ref': refs.to_url(entity)})


def check_watch(entity):
    if not c.user:
        return None
    watch = model.Watch.find_by_entity(c.user, entity)
    if request.params.get('watch') and not watch: 
        model.Watch.create(c.user, entity)
    elif watch:
        watch.delete()
    model.meta.Session.commit()

    
def clean_stale_watches():
    log.debug("Beginning to clean up watchlist entries...")
    count = 0
    for watch in model.Watch.all():
        if hasattr(watch.entity, 'is_deleted') and \
            watch.entity.is_deleted():
            count += 1
            watch.delete()
    model.meta.Session.commit()
    if count > 0:
        log.debug("Removed %d stale watchlist entries." % count)    
            

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid.interfaces import IRequest

from pyramid.traversal import find_interface

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from nti.app.contentlibrary.interfaces import IContentUnitInfo

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.app.site.workspaces.workspaces import ISiteAdminWorkspace

# make sure we use nti.dataserver.traversal to find the root site
from nti.dataserver.traversal import find_nearest_site as ds_find_nearest_site

from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import IExternalMappingDecorator
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.singleton import SingletonDecorator

from nti.links.links import Link

from nti.links import render_link

LINKS = StandardExternalFields.LINKS

SYNC_LIBRARIES = 'SyncAllLibraries'
REMOVE_LOCK = 'RemoveSyncLocks'

@component.adapter(IContentUnitInfo)
@interface.implementer(IExternalMappingDecorator)
class ContentUnitInfoHrefDecorator(object):

    __metaclass__ = SingletonDecorator

    def decorateExternalMapping(self, context, mapping):
        if 'href' in mapping:
            return

        try:
            # Some objects are not in the traversal tree. Specifically,
            # chatserver.IMeeting (which is IModeledContent and IPersistent)
            # Our options are to either catch that here, or introduce an
            # opt-in interface that everything that wants 'edit' implements
            nearest_site = ds_find_nearest_site(context)
        except TypeError:
            nearest_site = None

        if nearest_site is None:
            logger.debug("Not providing href links for %s, could not find site",
                         type(context))
            return

        link = links.Link(nearest_site, elements=('Objects', context.ntiid))
        # Nearest site may be IRoot, which has no __parent__
        link.__parent__ = getattr(nearest_site, '__parent__', None)
        link.__name__ = ''
        interface.alsoProvides(link, ILocation)

        mapping['href'] = render_link(link, nearest_site=nearest_site)['href']

@component.adapter(ISiteAdminWorkspace, IRequest)
@interface.implementer(IExternalObjectDecorator)
class AdminSyncLibrariesDecorator(AbstractAuthenticatedRequestAwareDecorator):

    __metaclass_ = SingletonDecorator

    def _do_decorate_external(self, context, result_map):
        links = result_map.setdefault("Links", [])
        rels = [SYNC_LIBRARIES, REMOVE_LOCK]
        ds2 = find_interface(context, IDataserverFolder)
        for rel in rels:
            link = Link(ds2,
                        rel=rel,
                        elements=("@@%s" % rel,))
            links.append(link)

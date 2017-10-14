#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from nti.app.contentlibrary import LIBRARY_PATH_GET_VIEW

from nti.app.contentlibrary.decorators import get_ds2

from nti.dataserver.interfaces import IHighlight

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import SingletonDecorator

from nti.links.links import Link

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@component.adapter(IHighlight)
@interface.implementer(IExternalMappingDecorator)
class _UGDLibraryPathLinkDecorator(object):
    """
    Create a `LibraryPath` link to our container id.
    """

    __metaclass__ = SingletonDecorator

    def decorateExternalMapping(self, context, result):
        container_id = context.containerId
        container = find_object_with_ntiid(container_id)
        if container is not None:
            external_ntiid = to_external_ntiid_oid(container)
        else:
            external_ntiid = None
        if external_ntiid is None:
            # Non-persistent content unit perhaps.
            # Just add library path to our note.
            external_ntiid = to_external_ntiid_oid(context)

        if external_ntiid is not None:
            path = '/%s/%s' % (get_ds2(), LIBRARY_PATH_GET_VIEW)
            link = Link(path,
                        rel=LIBRARY_PATH_GET_VIEW,
                        method='GET',
                        params={'objectId': external_ntiid})
            _links = result.setdefault(LINKS, [])
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)

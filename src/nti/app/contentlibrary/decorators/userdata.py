#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from zope.location.interfaces import ILocation

from nti.app.contentlibrary import LIBRARY_PATH_GET_VIEW

from nti.app.contentlibrary.decorators import get_ds2

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import Singleton

from nti.links.links import Link

from nti.ntiids.oids import to_external_ntiid_oid

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IExternalMappingDecorator)
class _UGDLibraryPathLinkDecorator(Singleton):
    """
    Create a `LibraryPath` link to our object ntiid.
    """

    def decorateExternalMapping(self, context, result):
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

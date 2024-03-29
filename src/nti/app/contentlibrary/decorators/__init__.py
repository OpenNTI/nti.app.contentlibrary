#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.threadlocal import get_current_request

from zope import interface

from zope.location.interfaces import ILocation

from nti.app.contentlibrary import LIBRARY_PATH_GET_VIEW

from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.singleton import Singleton

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


class AbstractLibraryPathLinkDecorator(Singleton):
    """
    Create a `LibraryPath` link to our object.
    """

    def decorateExternalMapping(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context,
                    rel=LIBRARY_PATH_GET_VIEW,
                    elements=(LIBRARY_PATH_GET_VIEW,))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)


def get_ds2(request=None):
    request = request if request else get_current_request()
    try:
        result = request.path_info_peek() if request else None
    except AttributeError:  # in unit test we may see this
        result = None
    return result or "dataserver2"
get_path_info = get_ds2

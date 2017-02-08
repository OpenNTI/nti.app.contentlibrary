#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from urllib import unquote

from zope import interface

from zope.container.contained import Contained

from zope.traversing.interfaces import IPathAdapter

from pyramid import httpexceptions as hexc

from nti.app.contentlibrary import VIEW_CONTENTS
from nti.app.contentlibrary import LIBRARY_ADAPTER

from nti.app.contentlibrary import MessageFactory

from nti.contentlibrary.interfaces import IContentUnit

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import ALL_PERMISSIONS
from nti.dataserver.interfaces import EVERYONE_GROUP_NAME

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.property.property import Lazy


@interface.implementer(IPathAdapter)
class LibraryPathAdapter(Contained):

    __name__ = LIBRARY_ADAPTER

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.__parent__ = context

    def __getitem__(self, ntiid):
        if not ntiid:
            raise hexc.HTTPNotFound()
        ntiid = unquote(ntiid)
        result = find_object_with_ntiid(ntiid)
        if IContentUnit.providedBy(result):
            return result
        raise KeyError(ntiid)

    @Lazy
    def __acl__(self):
        aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)),
                ace_allowing(ROLE_CONTENT_ADMIN, ALL_PERMISSIONS, type(self)),
                ace_allowing(EVERYONE_GROUP_NAME, ACT_READ, type(self))]
        return acl_from_aces(aces)

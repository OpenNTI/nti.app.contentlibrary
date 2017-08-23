#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from urllib import unquote

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite

from zope.location.interfaces import IContained

from zope.traversing.interfaces import IPathAdapter

from pyramid import httpexceptions as hexc

from nti.app.contentlibrary import LIBRARY_ADAPTER
from nti.app.contentlibrary import CONTENT_BUNDLES_ADAPTER

from nti.app.contentlibrary import VIEW_CONTENTS
from nti.app.contentlibrary import VIEW_PUBLISH_CONTENTS
from nti.app.contentlibrary import VIEW_PACKAGE_WITH_CONTENTS

from nti.app.contentlibrary import MessageFactory

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.contentlibrary import NTI

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackageBundle

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import ALL_PERMISSIONS
from nti.dataserver.interfaces import EVERYONE_GROUP_NAME

from nti.ntiids.ntiids import find_object_with_ntiid


@interface.implementer(IPathAdapter, IContained)
class PathAdapterMixin(object):

    __name__ = None

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.__parent__ = context

    @Lazy
    def __acl__(self):
        aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)),
                ace_allowing(ROLE_CONTENT_ADMIN, ALL_PERMISSIONS, type(self)),
                ace_allowing(EVERYONE_GROUP_NAME, ACT_READ, type(self))]
        return acl_from_aces(aces)


class LibraryPathAdapter(PathAdapterMixin):

    __name__ = LIBRARY_ADAPTER

    def __getitem__(self, ntiid):
        if not ntiid:
            raise hexc.HTTPNotFound()
        ntiid = unquote(ntiid)
        result = find_object_with_ntiid(ntiid)
        if IContentUnit.providedBy(result):
            return result
        raise KeyError(ntiid)


class ContentBundlesPathAdapter(PathAdapterMixin):

    __name__ = CONTENT_BUNDLES_ADAPTER

    def __getitem__(self, ntiid):
        if not ntiid:
            raise hexc.HTTPNotFound()
        ntiid = unquote(ntiid)
        result = find_object_with_ntiid(ntiid)
        if IContentPackageBundle.providedBy(result):
            return result
        raise KeyError(ntiid)


def get_site_provider():
    policy = component.queryUtility(ISitePolicyUserEventListener)
    result = getattr(policy, 'PROVIDER', None)
    if not result:
        annontations = IAnnotations(getSite(), {})
        result = annontations.get('PROVIDER')
    return result or NTI

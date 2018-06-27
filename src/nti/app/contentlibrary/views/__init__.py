#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from six.moves.urllib_parse import unquote

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.location.interfaces import IContained

from zope.traversing.interfaces import IPathAdapter

from pyramid import httpexceptions as hexc

from nti.app.contentlibrary import LIBRARY_ADAPTER
from nti.app.contentlibrary import CONTENT_BUNDLES_ADAPTER
from nti.app.contentlibrary import BUNDLE_USERS_PATH_ADAPTER

from nti.app.contentlibrary import VIEW_CONTENTS
from nti.app.contentlibrary import VIEW_PUBLISH_CONTENTS
from nti.app.contentlibrary import VIEW_PACKAGE_WITH_CONTENTS

from nti.app.contentlibrary import MessageFactory

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackageBundle

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import ALL_PERMISSIONS
from nti.dataserver.interfaces import EVERYONE_GROUP_NAME

from nti.dataserver.users import User

from nti.externalization.proxy import removeAllProxies

from nti.ntiids.ntiids import find_object_with_ntiid
from nti.app.contentlibrary.model import UserBundleRecord

logger = __import__('logging').getLogger(__name__)


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
            return removeAllProxies(result)
        raise KeyError(ntiid)


class ContentBundlesPathAdapter(PathAdapterMixin):

    __name__ = CONTENT_BUNDLES_ADAPTER

    def __getitem__(self, ntiid):
        if not ntiid:
            raise hexc.HTTPNotFound()
        ntiid = unquote(ntiid)
        result = find_object_with_ntiid(ntiid)
        if IContentPackageBundle.providedBy(result):
            return removeAllProxies(result)
        raise KeyError(ntiid)


@interface.implementer(IPathAdapter, IContained)
class ContentPackageBundleUsersPathAdapter(object):

    __name__ = BUNDLE_USERS_PATH_ADAPTER

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.__parent__ = context

    def __getitem__(self, username):
        if not username:
            raise hexc.HTTPNotFound()
        username = unquote(username)
        user = User.get_user(username)
        if not username:
            raise hexc.HTTPNotFound()
        result = UserBundleRecord(User=user, Bundle=self.context)
        # Gives us the bundle ACL
        result.__parent__ = self.context
        return result

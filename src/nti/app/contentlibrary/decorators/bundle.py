#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.interfaces import IRequest

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from nti.app.contentlibrary import VIEW_CONTENTS
from nti.app.contentlibrary import VIEW_BUNDLE_GRANT_ACCESS
from nti.app.contentlibrary import VIEW_USER_BUNDLE_RECORDS
from nti.app.contentlibrary import VIEW_BUNDLE_REMOVE_ACCESS
from nti.app.contentlibrary import BUNDLE_USERS_PATH_ADAPTER

from nti.app.contentlibrary.interfaces import IContentBoard
from nti.app.contentlibrary.interfaces import IUserBundleRecord

from nti.app.contentlibrary.utils import get_visible_bundles_for_user

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.contentlibrary.interfaces import IContentPackageBundle

from nti.coremetadata.interfaces import IUser
from nti.coremetadata.interfaces import ILastSeenProvider

from nti.dataserver.authorization import is_admin
from nti.dataserver.authorization import is_site_admin
from nti.dataserver.authorization import is_admin_or_site_admin
from nti.dataserver.authorization import is_admin_or_content_admin_or_site_admin

from nti.dataserver.interfaces import ISiteAdminUtility

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import Singleton

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IExternalMappingDecorator)
@component.adapter(IContentPackageBundle)
class _ContentBundlePagesLinkDecorator(Singleton):
    """
    Places a link to the pages and contents of a content bundle.
    """

    def decorateExternalMapping(self, context, result):
        _links = result.setdefault(LINKS, [])
        for rel in ('Pages', VIEW_CONTENTS):
            link = Link(context, rel=rel, elements=(rel,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)
        result['Discussions'] = IContentBoard(context, None)


@interface.implementer(IExternalMappingDecorator)
@component.adapter(IContentPackageBundle, IRequest)
class _ContentBundleAdminDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, unused_context, unused_result):
        return is_admin_or_content_admin_or_site_admin(self.remoteUser)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        for rel in ('AddPackage', 'RemovePackage'):
            link = Link(context,
                        rel=rel,
                        elements=('@@%s' % rel,))
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@interface.implementer(IExternalMappingDecorator)
@component.adapter(IContentPackageBundle, IRequest)
class _ContentBundleDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, unused_context, unused_result):
        return is_admin_or_site_admin(self.remoteUser)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        for rel in (VIEW_BUNDLE_GRANT_ACCESS,
                    VIEW_BUNDLE_REMOVE_ACCESS,
                    BUNDLE_USERS_PATH_ADAPTER):
            if BUNDLE_USERS_PATH_ADAPTER:
                elements = (rel,)
            else:
                elements = ('@@%s' % rel,)
            link = Link(context,
                        rel=rel,
                        elements=elements)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@component.adapter(IUser)
@interface.implementer(IExternalMappingDecorator)
class _UserBundleRecordsDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the :class:``IUser`` with a rel to fetch bundle records.
    """

    def _can_admin_user(self, context):
        # Verify a site admin is administering a user in their site.
        result = True
        if is_site_admin(self.remoteUser):
            admin_utility = component.getUtility(ISiteAdminUtility)
            result = admin_utility.can_administer_user(self.remoteUser, context)
        return result

    def _predicate(self, context, unused_result):
        bundles = get_visible_bundles_for_user(context)
        return  bundles \
            and (   self.remoteUser == context \
                 or is_admin(self.remoteUser) \
                 or self._can_admin_user(context))

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context,
                    rel=VIEW_USER_BUNDLE_RECORDS,
                    elements=('@@%s' % VIEW_USER_BUNDLE_RECORDS,))
        _links.append(link)


@component.adapter(IUserBundleRecord)
@interface.implementer(IExternalMappingDecorator)
class _LastSeenTimeForUserBundleRecordDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _do_decorate_external(self, context, result):
        if 'LastSeenTime' not in result:
            provider = component.queryMultiAdapter((context.User, context.Bundle or context.__parent__),
                                                   ILastSeenProvider)
            result['LastSeenTime'] = provider.lastSeenTime if provider else None

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from pyramid.threadlocal import get_current_request

from nti.appserver.pyramid_authorization import has_permission

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.contentsearch.interfaces import ISearchHitPredicate
from nti.contentsearch.interfaces import IContentUnitSearchHit
from nti.contentsearch.interfaces import ISearchPackageResolver

from nti.contentsearch.predicates import DefaultSearchHitPredicate

from nti.dataserver.authorization import ACT_READ

from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.singleton import SingletonDecorator

from nti.publishing.interfaces import IPublishable

CONTAINER_ID = StandardExternalFields.CONTAINER_ID


def is_published(context):
    return not IPublishable.providedBy(context) or context.is_published()


@interface.implementer(ISearchPackageResolver)
class _DefaultSearchPacakgeResolver(object):

    def __init__(self, *args):
        pass

    def resolve(self, unused_user, unused_ntiid=None):
        result = ()
        request = get_current_request()
        library = component.queryUtility(IContentPackageBundleLibrary)
        library = component.queryMultiAdapter((library, request),
                                              IContentPackageBundleLibrary)
        if library is not None:
            result = []
            for bundle in library.getBundles():
                result.extend(x.ntiid for x in bundle.ContentPackages)
        return result


@component.adapter(IContentUnit)
@interface.implementer(ISearchHitPredicate)
class _ContentUnitSearchHitPredicate(DefaultSearchHitPredicate):

    __name__ = u'ContentUnit'

    @Lazy
    def request(self):
        return get_current_request()

    def allow(self, item, unused_score, unused_query):
        if self.principal is None:
            return True
        return is_published(item) \
           and has_permission(ACT_READ, item, self.request)


@component.adapter(IContentUnitSearchHit)
class _SearchHitDecorator(object):

    __metaclass__ = SingletonDecorator

    def decorateExternalObject(self, original, external):
        if CONTAINER_ID not in external:
            context = original.Target
            parent_key = getattr(context.__parent__, 'key', None)
            if parent_key is not None and parent_key == context.key:
                external[CONTAINER_ID] = context.__parent__.ntiid
            else:
                external[CONTAINER_ID] = context.ntiid

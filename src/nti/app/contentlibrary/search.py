#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.threadlocal import get_current_request

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from nti.appserver.pyramid_authorization import has_permission

from nti.contentlibrary.interfaces import IContentUnit, IContentPackageBundle
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.contentsearch.interfaces import ISearchHitPredicate
from nti.contentsearch.interfaces import IContentUnitSearchHit
from nti.contentsearch.interfaces import ISearchPackageResolver

from nti.contentsearch.predicates import DefaultSearchHitPredicate

from nti.dataserver.authorization import ACT_READ

from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.singleton import Singleton

from nti.publishing.interfaces import IPublishable
from nti.ntiids.ntiids import find_object_with_ntiid

CONTAINER_ID = StandardExternalFields.CONTAINER_ID

logger = __import__('logging').getLogger(__name__)


def is_published(context):
    return not IPublishable.providedBy(context) or context.is_published()


@interface.implementer(ISearchPackageResolver)
class _DefaultSearchPacakgeResolver(object):

    def __init__(self, *args):
        pass

    def resolve(self, unused_user, ntiid=None):
        result = set()
        if ntiid:
            # If ntiid, return it and any packages under it
            result.add(ntiid)
            obj = find_object_with_ntiid(ntiid)
            if IContentPackageBundle.providedBy(obj):
                result.update(x for x in obj.ContentPackages)
        else:
            # Otherwise, return all bundle packages
            request = get_current_request()
            library = component.queryUtility(IContentPackageBundleLibrary)
            library = component.queryMultiAdapter((library, request),
                                                  IContentPackageBundleLibrary)
            if library is not None:
                for bundle in library.getBundles():
                    result.update(x.ntiid for x in bundle.ContentPackages)
        return result


@component.adapter(IContentUnit)
@interface.implementer(ISearchHitPredicate)
class _ContentUnitSearchHitPredicate(DefaultSearchHitPredicate):

    __name__ = u'ContentUnit'

    @Lazy
    def request(self):
        return get_current_request()

    def allow(self, item, unused_score, unused_query):  # pylint: disable=arguments-differ
        if self.principal is None:
            return True
        return is_published(item) \
           and has_permission(ACT_READ, item, self.request)


@component.adapter(IContentUnitSearchHit)
class _SearchHitDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        if CONTAINER_ID not in external:
            context = original.Target
            parent_key = getattr(context.__parent__, 'key', None)
            if parent_key is not None and parent_key == context.key:
                external[CONTAINER_ID] = context.__parent__.ntiid
            else:
                external[CONTAINER_ID] = context.ntiid

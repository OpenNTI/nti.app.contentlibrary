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

from nti.app.contentlibrary.utils import content_unit_to_bundles

from nti.contentlibrary.interfaces import IContentUnit, IContentPackageBundle
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.contentsearch.interfaces import ISearchHitPredicate
from nti.contentsearch.interfaces import IContentUnitSearchHit
from nti.contentsearch.interfaces import ISearchPackageResolver

from nti.contentsearch.predicates import DefaultSearchHitPredicate

from nti.dataserver.authorization import ACT_READ

from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.singleton import Singleton

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.publishing.interfaces import IPublishable

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
                result.update(x.ntiid for x in obj.ContentPackages)
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

    def validate_bundle_permission(self, item):
        """
        Validate the remote user has READ permission on *any* bundle
        containing this unit. If not found in a bundle, return True.
        """
        bundles = content_unit_to_bundles(item)
        if not bundles:
            return True
        result = False
        for bundle in bundles:
            if has_permission(ACT_READ, bundle, self.request):
                # Just need one hit
                result = True
                break
        return result

    def allow(self, item, unused_score, unused_query):  # pylint: disable=arguments-differ
        if self.principal is None:
            return True
        return is_published(item) \
           and has_permission(ACT_READ, item, self.request) \
           and self.validate_bundle_permission(item)


@component.adapter(IContentUnitSearchHit)
class _SearchHitDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        if CONTAINER_ID not in external:
            context = original.Target
            parent_key = getattr(context.__parent__, 'key', None)
            if parent_key is not None and parent_key == context.key:
                external[CONTAINER_ID] = container_id = context.__parent__.ntiid
            else:
                external[CONTAINER_ID] = container_id = context.ntiid
            container = find_object_with_ntiid(container_id)
            title = getattr(container, 'title', '') \
                 or getattr(container, 'label', '')
            external["ContainerTitle"] = title

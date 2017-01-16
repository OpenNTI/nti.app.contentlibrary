#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from pyramid.threadlocal import get_current_request

from nti.appserver.pyramid_authorization import has_permission

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackageBundle
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contentsearch.interfaces import ISearchHitPredicate
from nti.contentsearch.interfaces import IRootPackageResolver
from nti.contentsearch.interfaces import IContentUnitSearchHit
from nti.contentsearch.interfaces import ISearchPackageResolver

from nti.contentsearch.predicates import DefaultSearchHitPredicate

from nti.dataserver.authorization import ACT_READ

from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.singleton import SingletonDecorator

from nti.ntiids.ntiids import ROOT
from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import is_ntiid_of_type
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.property.property import Lazy

CONTAINER_ID = StandardExternalFields.CONTAINER_ID


@interface.implementer(ISearchPackageResolver)
class _DefaultSearchPacakgeResolver(object):

    def __init__(self, *args):
        pass

    def resolve(self, user, ntiid=None):
        result = ()
        if ntiid != ROOT:
            if bool(is_ntiid_of_type(ntiid, TYPE_OID)):
                obj = find_object_with_ntiid(ntiid)
                bundle = IContentPackageBundle(obj, None)
                if bundle is not None and bundle.ContentPackages:
                    result = tuple(x.ntiid for x in bundle.ContentPackages)
            else:
                result = (ntiid,)
        else:
            request = get_current_request()
            library = component.queryUtility(IContentPackageLibrary)
            library = component.queryMultiAdapter((library, request),
                                                  IContentPackageLibrary)
            if library is not None:
                result = tuple(x.ntiid for x in library.contentPackages)
        return result


@interface.implementer(IRootPackageResolver)
class _DefaultRootPackageResolver(object):

    def __init__(self, *args):
        pass

    def resolve(self, ntiid):
        library = component.queryUtility(IContentPackageLibrary)
        paths = library.pathToNTIID(ntiid) if library is not None else None
        return paths[0] if paths else None


@component.adapter(IContentUnit)
@interface.implementer(ISearchHitPredicate)
class _ContentUnitSearchHitPredicate(DefaultSearchHitPredicate):

    __name__ = 'ContentUnit'

    @Lazy
    def request(self):
        return get_current_request()

    def allow(self, item, score, query):
        if self.principal is None:
            return True
        return has_permission(ACT_READ, item, self.request)


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

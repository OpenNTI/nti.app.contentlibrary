#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin

from nti.app.contentlibrary.views import LibraryPathAdapter

from nti.contentlibrary import ALL_CONTENT_MIMETYPES

from nti.contentlibrary.index import get_contentbundle_catalog
from nti.contentlibrary.index import get_contentlibrary_catalog

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.contentlibrary.utils import get_content_packages

from nti.dataserver import authorization as nauth

from nti.externalization.externalization import StandardExternalFields

from nti.externalization.interfaces import LocatedExternalDict

from nti.metadata import queue_add
 
from nti.site.hostpolicy import get_all_host_sites

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


@view_config(context=LibraryPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name="RemoveInvalidContentPackages",
               permission=nauth.ACT_NTI_ADMIN)
class RemoveInvalidPackagesView(AbstractAuthenticatedView):

    @Lazy
    def _library(self):
        library = component.queryUtility(IContentPackageLibrary)
        return library

    def _do_delete_object(self, theObject, event=True):
        library = self._library
        library.remove(theObject, event=event)
        return theObject

    def __call__(self):
        library = self._library
        result = LocatedExternalDict()
        result[ITEMS] = items = {}
        packages = get_content_packages(mime_types=ALL_CONTENT_MIMETYPES)
        for package in packages:
            stored = library.get(package.ntiid)
            if stored is None:
                logger.info('Removing package (%s)', package.ntiid)
                self._do_delete_object(package)
                items[package.ntiid] = package
        # remove invalid registrations
        try:
            for ntiid in library.removeInvalidContentUnits().keys():
                items[ntiid] = None
        except AttributeError:
            pass
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        return result


@view_config(context=LibraryPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name="AllContentPackages",
               permission=nauth.ACT_NTI_ADMIN)
class AllContentPackagesView(AbstractAuthenticatedView,
                             BatchingUtilsMixin):

    _DEFAULT_BATCH_SIZE = 30
    _DEFAULT_BATCH_START = 0

    def __call__(self):
        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        library = component.queryUtility(IContentPackageLibrary)
        if library is not None:
            packages = list(library.contentPackages)
            packages.sort(key=lambda p: p.ntiid)
        else:
            packages = ()
        result['TotalItemCount'] = len(packages)
        self._batch_items_iterable(result, packages)
        result[ITEM_COUNT] = len(result[ITEMS])
        return result


@view_config(context=LibraryPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name="AllContentPackageBundles",
               permission=nauth.ACT_NTI_ADMIN)
class AllContentPackageBundlesView(AbstractAuthenticatedView,
                                   BatchingUtilsMixin):

    _DEFAULT_BATCH_SIZE = 30
    _DEFAULT_BATCH_START = 0

    def __call__(self):
        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        library = component.queryUtility(IContentPackageBundleLibrary)
        if library is not None:
            bundles = list(library.getBundles())
            bundles.sort(key=lambda p: p.ntiid)
        else:
            bundles = ()
        result['TotalItemCount'] = len(bundles)
        self._batch_items_iterable(result, bundles)
        result[ITEM_COUNT] = len(result[ITEMS])
        return result


@view_config(context=LibraryPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name="RebuildContentLibraryCatalog",
               permission=nauth.ACT_NTI_ADMIN)
class RebuildContentPackageCatalogView(AbstractAuthenticatedView):

    def __call__(self):
        intids = component.getUtility(IIntIds)
        # remove indexes
        catalog = get_contentlibrary_catalog()
        for index in catalog.values():
            index.clear()
        # reindex
        seen = set()
        for host_site in get_all_host_sites():  # check all sites
            with current_site(host_site):
                library = component.queryUtility(IContentPackageLibrary)
                packages = library.contentPackages if library else ()
                for package in packages:
                    doc_id = intids.queryId(package)
                    if doc_id is None or doc_id in seen:
                        continue
                    seen.add(doc_id)
                    queue_add(package)
                    catalog.index_doc(doc_id, package)
        result = LocatedExternalDict()
        result[ITEM_COUNT] = result[TOTAL] = len(seen)
        return result


@view_config(context=LibraryPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name="RebuildContentBundleCatalog",
               permission=nauth.ACT_NTI_ADMIN)
class RebuildContentBundleCatalogView(AbstractAuthenticatedView):

    def __call__(self):
        intids = component.getUtility(IIntIds)
        # remove indexes
        catalog = get_contentbundle_catalog()
        for index in catalog.values():
            index.clear()
        # reindex
        seen = set()
        for host_site in get_all_host_sites():  # check all sites
            with current_site(host_site):
                library = component.queryUtility(IContentPackageBundleLibrary)
                bundles = library.getBundles() if library else ()
                for bundle in bundles:
                    doc_id = intids.queryId(bundle)
                    if doc_id is None or doc_id in seen:
                        continue
                    seen.add(doc_id)
                    catalog.index_doc(doc_id, bundle)
                    queue_add(bundle)
        result = LocatedExternalDict()
        result[ITEM_COUNT] = result[TOTAL] = len(seen)
        return result

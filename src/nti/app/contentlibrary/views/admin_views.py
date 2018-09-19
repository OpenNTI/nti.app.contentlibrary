#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from requests.structures import CaseInsensitiveDict

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from zope import component
from zope import lifecycleevent

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite
from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.contentlibrary.utils.bundle import save_bundle

from nti.app.contentlibrary.views import LibraryPathAdapter

from nti.app.contentlibrary.views.bundle_views import ContentPackageBundleMixin

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.common.string import is_true

from nti.contentlibrary import ALL_CONTENT_MIMETYPES

from nti.contentlibrary.bundle import PUBLISHABLE_BUNDLE_MIME_TYPE

from nti.contentlibrary.bundle import PublishableContentPackageBundle

from nti.contentlibrary.index import get_contentbundle_catalog
from nti.contentlibrary.index import get_contentlibrary_catalog

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.contentlibrary.utils import get_content_packages

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IPublishable
from nti.dataserver.interfaces import IAccessProvider

from nti.dataserver.users.communities import Community

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import StandardInternalFields

from nti.externalization.internalization import update_from_external_object

from nti.metadata import queue_add

from nti.site.hostpolicy import get_all_host_sites

NTIID = StandardExternalFields.NTIID
ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

INTERNAL_NTIID = StandardInternalFields.NTIID

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
        # pylint: disable=no-member
        library.remove(theObject, event=event)
        return theObject

    def __call__(self):
        library = self._library
        result = LocatedExternalDict()
        result[ITEMS] = items = {}
        packages = get_content_packages(mime_types=ALL_CONTENT_MIMETYPES)
        for package in packages:
            # pylint: disable=no-member
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
        result[TOTAL] = result['TotalItemCount'] = len(packages)
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
        result[TOTAL] = result['TotalItemCount'] = len(bundles)
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


@view_config(context=LibraryPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name="PublishBundleCatalog",
               permission=nauth.ACT_NTI_ADMIN)
class PublishBundleCatalogView(AbstractAuthenticatedView):
    """
    An admin view that will publish all bundles in our current site (and not
    parent catalog bundles).
    """

    def __call__(self):
        library = component.queryUtility(IContentPackageBundleLibrary)
        bundles = library.getBundles(parents=False)
        ntiids = []
        for bundle in bundles:
            if IPublishable.providedBy(bundle) and not bundle.is_published():
                bundle.publish()
                ntiids.append(bundle.ntiid)
        result = LocatedExternalDict()
        result[ITEMS] = ntiids
        result[ITEM_COUNT] = result[TOTAL] = len(ntiids)
        return result


@view_config(context=LibraryPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name="CopyBundleCatalog",
               permission=nauth.ACT_NTI_ADMIN)
class CopyContentPackageBundleCatalogView(AbstractAuthenticatedView,
                                          ModeledContentUploadRequestUtilsMixin,
                                          ContentPackageBundleMixin):
    """
    An admin view that will copy all content package bundles from a source
    site into our current site.
    """

    def readInput(self, value=None):
        if self.request.body:
            values = super(CopyContentPackageBundleCatalogView, self).readInput(value)
        else:
            values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    @Lazy
    def _params(self):
        return self.readInput()

    @Lazy
    def intids(self):
        return component.getUtility(IIntIds)

    @Lazy
    def source_site_name(self):
        return self._params.get('source') \
            or self._params.get('source_site') \
            or self._params.get('source_site_name')

    @Lazy
    def restrict_parent_bundles(self):
        # Default false
        result = self._params.get('restrict') \
              or self._params.get('restrict_parent_bundles')
        return is_true(result)

    @Lazy
    def publish_bundles(self):
        # Default to true
        result = self._params.get('publish') \
              or self._params.get('publish_bundles')
        return result is None or is_true(result)

    def do_restrict_bundles(self, parent_bundles, parent_sm):
        """
        Restrict access to parent bundles; explicitly granting to parent site
        community.
        """
        site_policy = parent_sm.queryUtility(ISitePolicyUserEventListener)
        community_username = getattr(site_policy, 'COM_USERNAME', '')
        parent_community = None
        if community_username:
            parent_community = Community.get_community(community_username)
        for bundle in parent_bundles:
            bundle.RestrictedAccess = True
            if parent_community is not None:
                access_provider = IAccessProvider(bundle)
                access_provider.grant_access(parent_community)

    def save_bundle_to_disk(self, new_bundle, parent_bundle):
        doc_id = self.intids.getId(new_bundle)
        parent_root = parent_bundle.root
        assets_path = parent_root.getChildNamed('presentation-assets')
        assets_path = getattr(assets_path, 'absolute_path', None)
        if assets_path is not None:
            library = self.validate_content_library(new_bundle)
            # check for transaction retrial
            jid = getattr(self.request, 'jid', None)
            if jid is None:
                # This should keep the source assets path unchanged.
                save_bundle(new_bundle,
                            library.enumeration.root,
                            assets_path,
                            name=str(doc_id))
        self.request.jid = doc_id

    def create_bundle(self, parent_bundle, library):
        """
        Create a bundle based on the parent bundle as a starting point.
        """
        bundle = PublishableContentPackageBundle()
        ext_bundle = to_external_object(parent_bundle, decorate=False)
        ext_bundle['ContentPackages'] = [x[NTIID] for x in ext_bundle['ContentPackages']]
        ext_bundle[MIMETYPE] = PUBLISHABLE_BUNDLE_MIME_TYPE
        [ext_bundle.pop(x, None) for x in (NTIID, INTERNAL_NTIID)]
        update_from_external_object(bundle, ext_bundle)

        bundle.creator = self.remoteUser.username
        # register and set ntiid
        intids = component.getUtility(IIntIds)
        intids.register(bundle)
        bundle.ntiid = self.make_bundle_ntiid(bundle)
        # add to library
        lifecycleevent.created(bundle)
        library.add(bundle)
        self.save_bundle_to_disk(bundle, parent_bundle)
        return bundle

    def copy_bundles(self, parent_bundles):
        library = component.queryUtility(IContentPackageBundleLibrary)
        bundles = tuple(library.getBundles(parents=False))
        # We do not need to copy bundles if the title already exists
        child_titles = {x.title for x in bundles}
        new_ntiids = []
        for parent_bundle in parent_bundles:
            if parent_bundle.title in child_titles:
                continue
            new_bundle = self.create_bundle(parent_bundle, library)
            if self.publish_bundles:
                new_bundle.publish()
            logger.info('Creating copied bundle (%s) (%s)',
                        new_bundle.title,
                        new_bundle.ntiid)
            new_ntiids.append(new_bundle.ntiid)
        return new_ntiids

    def __call__(self):
        current_site = getSite()
        source_site = current_site.__parent__.get(self.source_site_name)
        if source_site is None:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Invalid bundle source site."),
                             },
                             None)
        parent_sm = source_site.getSiteManager()
        parent_library = parent_sm.queryUtility(IContentPackageBundleLibrary)
        parent_bundles = tuple(parent_library.getBundles(parents=False))
        if self.restrict_parent_bundles:
            logger.info('Restricting access to parent bundles (%s)',
                        self.source_site_name)
            self.do_restrict_bundles(parent_bundles, parent_sm)
        new_ntiids = self.copy_bundles(parent_bundles)

        result = LocatedExternalDict()
        result[ITEMS] = new_ntiids
        result[ITEM_COUNT] = result[TOTAL] = len(new_ntiids)
        return result

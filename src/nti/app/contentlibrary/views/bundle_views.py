#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import uuid
import shutil

from zope import component

from zope import lifecycleevent

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import site as current_site

from zope.file.file import File

from zope.intid.interfaces import IIntIds

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary import MessageFactory as _

from nti.app.contentlibrary import VIEW_BUNDLE_GRANT_ACCESS
from nti.app.contentlibrary import VIEW_BUNDLE_REMOVE_ACCESS

from nti.app.contentlibrary.acl import role_for_content_bundle

from nti.app.contentlibrary.utils import role_for_content_package

from nti.app.contentlibrary.utils.bundle import save_bundle

from nti.app.contentlibrary.views import ContentBundlesPathAdapter

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.publishing import VIEW_PUBLISH

from nti.app.publishing.views import PublishView

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.appserver.ugd_edit_views import ContainerContextUGDPostView

from nti.contentlibrary.bundle import DEFAULT_BUNDLE_MIME_TYPE
from nti.contentlibrary.bundle import PUBLISHABLE_BUNDLE_MIME_TYPE

from nti.contentlibrary.interfaces import IContentPackageBundle
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary
from nti.contentlibrary.interfaces import IFilesystemContentPackageLibrary
from nti.contentlibrary.interfaces import IPublishableContentPackageBundle

from nti.contentlibrary.utils import NTI
from nti.contentlibrary.utils import make_content_package_bundle_ntiid
from nti.contentlibrary.utils import is_valid_presentation_assets_source

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_NTI_ADMIN
from nti.dataserver.authorization import ACT_CONTENT_EDIT
from nti.dataserver.authorization import CONTENT_ROLE_PREFIX

from nti.dataserver.interfaces import IMutableGroupMember

from nti.dataserver.users.communities import Community

from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.proxy import removeAllProxies

from nti.site.interfaces import IHostPolicyFolder

MIMETYPE = StandardExternalFields.MIMETYPE


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='POST',
             context=IContentPackageBundle,
             permission=ACT_READ,
             name='Pages')
class ContentBundlePagesView(ContainerContextUGDPostView):
    """
    A pages view on the course.  We subclass ``ContainerContextUGDPostView``
    in order to intervene and annotate our ``IContainerContext``
    object with the content bundle context.

    Reading/Editing/Deleting will remain the same.
    """


class ContentPackageBundleMixin(object):

    @Lazy
    def extra(self):
        return str(uuid.uuid4()).split('-')[0].upper()

    def get_source(self, request=None):
        request = self.request if not request else request
        sources = get_all_sources(request)
        if sources:
            source = iter(sources.values()).next()
            source.seek(0)
            return source
        return None

    def get_library(self, context=None, provided=IContentPackageBundleLibrary):
        if context is None:
            library = component.queryUtility(provided)
        else:
            # If context is given, attempt to use the site the given context
            # is stored in. This is necessary to avoid data loss during sync.
            with current_site(IHostPolicyFolder(context)):
                library = component.queryUtility(provided)
        if library is None:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Library not available."),
                                 'code': 'LibraryNotAvailable',
                             },
                             None)
        return library

    def validate_content_library(self, context=None):
        library = self.get_library(context, IContentPackageLibrary)
        if not IFilesystemContentPackageLibrary.providedBy(library):
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Library not supported."),
                                 'code': 'LibraryNotSupported',
                             },
                             None)
        return library

    @classmethod
    def make_bundle_ntiid(cls, bundle, provider=None, base=None, extra=None):
        policy = component.queryUtility(ISitePolicyUserEventListener)
        provider = provider or getattr(policy, 'PROVIDER', None) or NTI
        return make_content_package_bundle_ntiid(bundle, provider, base, extra)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='POST',
             context=ContentBundlesPathAdapter,
             permission=ACT_CONTENT_EDIT)
class ContentBundlePostView(AbstractAuthenticatedView,
                            ModeledContentUploadRequestUtilsMixin,
                            ContentPackageBundleMixin):

    content_predicate = IPublishableContentPackageBundle

    def readInput(self, value=None):
        result = super(ContentBundlePostView, self).readInput(value)
        result.pop('NTIID', None)
        result.pop('ntiid', None)
        if result.get(MIMETYPE) == DEFAULT_BUNDLE_MIME_TYPE:
            result[MIMETYPE] = PUBLISHABLE_BUNDLE_MIME_TYPE
        return result

    def _set_ntiid(self, context):
        context.ntiid = self.make_bundle_ntiid(context)

    def _do_call(self):
        # read incoming object
        bundle = self.readCreateUpdateContentObject(self.remoteUser,
                                                    search_owner=False)
        bundle.creator = self.remoteUser.username
        # register and set ntiid
        intids = component.getUtility(IIntIds)
        intids.register(bundle)
        self._set_ntiid(bundle)
        # add to library
        lifecycleevent.created(bundle)
        library = self.get_library(provided=IContentPackageBundleLibrary)
        library.add(bundle)
        # handle presentation-assets and save
        assets = self.get_source(self.request)
        if assets is not None:
            archive = is_valid_presentation_assets_source(assets)
            if not archive:
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u"Invalid presentation assets source."),
                                 },
                                 None)
            # save tmp file
            shutil.rmtree(archive, ignore_errors=True)
            assets.seek(0)
            # save assets source in a zope file
            archive = File()
            with archive.open("w") as fp:
                fp.write(assets.read())
            bundle._presentation_assets = archive
        self.request.response.status_int = 201
        logger.info('Created new content package bundle (%s)', bundle.ntiid)
        return bundle


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='POST',
             name=VIEW_PUBLISH,
             permission=ACT_CONTENT_EDIT,
             context=IPublishableContentPackageBundle)
class ContentBundlePublishView(PublishView, ContentPackageBundleMixin):

    def _do_provide(self, context):
        super(ContentBundlePublishView, self)._do_provide(context)
        intids = component.getUtility(IIntIds)
        doc_id = intids.getId(removeAllProxies(context))
        # get any presentation assets
        assets = self.get_source(self.request) \
              or getattr(context, '_presentation_assets', None)
        if assets is not None:
            if hasattr(assets, "seek"):
                assets.seek(0)
            library = self.validate_content_library(context)
            # check for transaction retrial
            jid = getattr(self.request, 'jid', None)
            if jid is None:
                save_bundle(context, library.enumeration.root,
                            assets, name=str(doc_id))
                if hasattr(context, '_presentation_assets'):
                    del context._presentation_assets
        # save trx id
        self.request.jid = doc_id
        context.publisher = self.remoteUser.username
        return context


class AbstractBundleUpdateAccessView(AbstractAuthenticatedView):
    """
    Base class for granting/removing a site community's access to an
    :class:`IContentPackageBundle` (e.g. the packages within our context
    bundle). We do so by adding/removing the content role(s) from the site
    community's IGroupMember list, including the content bundle role. If a
    package is added/removed from a bundle, this may have to be called again.

    TODO: Event, username params, decorators
    """

    @Lazy
    def _site_community(self):
        site_policy = component.queryUtility(ISitePolicyUserEventListener)
        community_username = getattr(site_policy, 'COM_USERNAME', '')
        result = None
        if community_username:
            result = Community.get_community(community_username)
        return result

    @Lazy
    def _entities(self):
        result = ()
        if self._site_community is not None:
            result = (self._site_community,)
        return result

    @Lazy
    def _context_roles(self):
        result = set()
        bundle_role = role_for_content_bundle(self.context)
        result.add(bundle_role)
        for package in self.context.ContentPackages or ():
            package_role = role_for_content_package(package)
            result.add(package_role)
        return result

    def _update_access(self):
        for entity in self._entities:
            logger.info("Updating access to bundle (%s) (%s) (type=%s)",
                        self.context.ntiid, entity, self.type)
            membership = component.getAdapter(entity, IMutableGroupMember,
                                              CONTENT_ROLE_PREFIX)
            orig_groups = set(membership.groups)
            new_groups = self._get_new_groups(orig_groups, self._context_roles)
            if new_groups != orig_groups:
                # be idempotent
                membership.setGroups(new_groups)

    def __call__(self):
        self._update_access()
        return hexc.HTTPNoContent()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='POST',
             name=VIEW_BUNDLE_GRANT_ACCESS,
             permission=ACT_NTI_ADMIN,
             context=IContentPackageBundle)
class BundleGrantAccessView(AbstractBundleUpdateAccessView):

    type = "GRANT"

    def _get_new_groups(self, original_groups, context_roles):
        return original_groups | context_roles


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='POST',
             name=VIEW_BUNDLE_REMOVE_ACCESS,
             permission=ACT_NTI_ADMIN,
             context=IContentPackageBundle)
class BundleRemoveAccessView(AbstractBundleUpdateAccessView):
    """
    FIXME: User has access to package from multiple bundles, how do
    handle that correctly? Do we iterate through bundle library
    checking bundle access?
    """

    type = "REMOVE"

    def _get_new_groups(self, original_groups, context_roles):
        return original_groups - context_roles

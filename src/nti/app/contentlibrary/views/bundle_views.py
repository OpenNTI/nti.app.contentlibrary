#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import six
import uuid
import shutil

from requests.structures import CaseInsensitiveDict

from zope import component

from zope import lifecycleevent

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite
from zope.component.hooks import site as current_site

from zope.event import notify

from zope.file.file import File

from zope.intid.interfaces import IIntIds

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.authentication import get_remote_user

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary import MessageFactory as _

from nti.app.contentlibrary import VIEW_BUNDLE_GRANT_ACCESS
from nti.app.contentlibrary import VIEW_BUNDLE_REMOVE_ACCESS

from nti.app.contentlibrary.hostpolicy import get_site_provider

from nti.app.contentlibrary.utils.bundle import save_bundle

from nti.app.contentlibrary.views import ContentBundlesPathAdapter

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.internalization import update_object_from_external_object

from nti.app.externalization.view_mixins import ModeledContentEditRequestUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.publishing import VIEW_PUBLISH
from nti.app.publishing import VIEW_UNPUBLISH

from nti.app.publishing.views import PublishView
from nti.app.publishing.views import UnpublishView

from nti.appserver.ugd_edit_views import ContainerContextUGDPostView

from nti.contentlibrary.bundle import DEFAULT_BUNDLE_MIME_TYPE
from nti.contentlibrary.bundle import PUBLISHABLE_BUNDLE_MIME_TYPE

from nti.contentlibrary.interfaces import IContentPackageBundle
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary
from nti.contentlibrary.interfaces import IFilesystemContentPackageLibrary
from nti.contentlibrary.interfaces import IPublishableContentPackageBundle

from nti.contentlibrary.interfaces import ContentBundleUpdatedEvent

from nti.contentlibrary.utils import make_content_package_bundle_ntiid
from nti.contentlibrary.utils import is_valid_presentation_assets_source

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ACT_NTI_ADMIN
from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import IAccessProvider

from nti.dataserver.users.entity import Entity

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import StandardInternalFields

from nti.externalization.proxy import removeAllProxies

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.interfaces import IHostPolicyFolder

NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE

INTERNAL_NTIID = StandardInternalFields.NTIID

logger = __import__('logging').getLogger(__name__)


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
        return str(uuid.uuid4().get_time_low())

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

    def check_presentation_assets(self, assets):
        if assets is not None:
            if hasattr(assets, "seek"):
                assets.seek(0)
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
        return assets

    @classmethod
    def make_bundle_ntiid(cls, bundle, provider=None, base=None, extra=None):
        provider = provider or get_site_provider()
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
        [result.pop(x, None) for x in (NTIID, INTERNAL_NTIID)]
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
            assets = self.check_presentation_assets(assets)
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
             request_method='PUT',
             permission=ACT_CONTENT_EDIT,
             context=IContentPackageBundle)
class ContentBundleUpdateView(AbstractAuthenticatedView,
                              ModeledContentEditRequestUtilsMixin,
                              ModeledContentUploadRequestUtilsMixin,
                              ContentPackageBundleMixin):

    content_predicate = IContentPackageBundle

    def readInput(self, value=None):
        if self.request.body:
            result = super(ContentBundleUpdateView, self).readInput(value)
            [result.pop(x, None) for x in (NTIID, INTERNAL_NTIID)]
        else:
            result = dict()
        return result

    def __call__(self):
        externalValue = self.readInput()
        contentObject = removeAllProxies(self.context)
        self._check_object_unmodified_since(externalValue)
        if externalValue:  # check there is something to update
            self.updateContentObject(contentObject, externalValue, notify=True)
        intids = component.getUtility(IIntIds)
        doc_id = intids.getId(contentObject)
        # get any presentation assets
        assets = self.get_source(self.request)
        if assets is not None:
            assets = self.check_presentation_assets(assets)
            library = self.validate_content_library(contentObject)
            # check for transaction retrial
            jid = getattr(self.request, 'jid', None)
            if jid is None:
                save_bundle(contentObject, library.enumeration.root,
                            assets, name=str(doc_id))
        # save trx id
        self.request.jid = doc_id
        return contentObject


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
        assets = self.get_source(self.request)
        if assets is not None:
            assets = self.check_presentation_assets(assets)
        else:
            assets = getattr(context, '_presentation_assets', None)
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
        context.publisher = get_remote_user().username
        return context


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='POST',
             name=VIEW_UNPUBLISH,
             permission=ACT_CONTENT_EDIT,
             context=IPublishableContentPackageBundle)
class ContentBundleUnpublishView(UnpublishView):
    pass


class AbstractBundleUpdateAccessView(AbstractAuthenticatedView,
                                     ModeledContentUploadRequestUtilsMixin):
    """
    Base class for granting/removing a site community's access to an
    :class:`IContentPackageBundle` (e.g. the packages within our context
    bundle). We do so by adding/removing the content role(s) from the site
    community's IGroupMember list, including the content bundle role. If a
    package is added/removed from a bundle, this may have to be called again.

    :params user The comma-separated usernames of the entities to grant/deny access.

    TODO: Event
    """

    def readInput(self, value=None):
        if self.request.body:
            values = super(AbstractBundleUpdateAccessView, self).readInput(value)
        else:
            values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    @Lazy
    def _site_community(self):
        result = ICommunity(getSite(), None)
        return result

    def _get_entities(self, entity_iterable):
        result = []
        for entity_name in entity_iterable:
            entity = Entity.get_entity(entity_name)
            if entity is not None:
                result.append(entity)
            else:
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u"Given entity not found."),
                                     'code': 'EntityNotFoundError',
                                 },
                                 None)
        return result

    @Lazy
    def _entities(self):
        """
        Take user input or fall back to site community.
        """
        values = self.readInput()
        result = values.get('user') \
              or values.get('users')
        if result:
            entities = result.split(',')
            result = self._get_entities(entities)
        else:
            if self._site_community is not None:
                result = (self._site_community,)
        if not result:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"No entities given for bundle access."),
                                 'code': 'NoBundleAccessEntitiesGiven',
                             },
                             None)
        return result

    @Lazy
    def access_provider(self):
        return IAccessProvider(self.context)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='POST',
             name=VIEW_BUNDLE_GRANT_ACCESS,
             permission=ACT_NTI_ADMIN,
             context=IContentPackageBundle)
class BundleGrantAccessView(AbstractBundleUpdateAccessView):
    """
    Grant access to a particular bundle.
    """

    def __call__(self):
        for entity in self._entities:
            self.access_provider.grant_access(entity)
        return hexc.HTTPNoContent()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='POST',
             name=VIEW_BUNDLE_REMOVE_ACCESS,
             permission=ACT_NTI_ADMIN,
             context=IContentPackageBundle)
class BundleRemoveAccessView(AbstractBundleUpdateAccessView):
    """
    Remove access to a particular bundle.
    """

    def __call__(self):
        for entity in self._entities:
            self.access_provider.remove_access(entity)
        return hexc.HTTPNoContent()


class ContentPackageBundleMixinView(AbstractAuthenticatedView,
                                    ModeledContentUploadRequestUtilsMixin):

    def readInput(self, value=None):
        result = super(ContentPackageBundleMixinView, self).readInput(value)
        return CaseInsensitiveDict(result)

    def get_ntiids(self):
        data = self.readInput()
        ntiids = data.get('ntiid') \
              or data.get('ntiids') \
              or data.get('pacakge') \
              or data.get('pacakges')
        if isinstance(ntiids, six.string_types):
            ntiids = ntiids.split()
        if not ntiids:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"No content package specified."),
                             },
                             None)
        return set(ntiids)


@view_config(name='AddPackage')
@view_config(name='AddPackages')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=ACT_UPDATE,
               context=IContentPackageBundle)
class ContentPackageBundleAddPackagesView(ContentPackageBundleMixinView):

    def __call__(self):
        ntiids = self.get_ntiids()
        packages = {x.ntiid for x in self.context.ContentPackages or ()}
        ntiids.update(packages)
        added = ntiids.difference(packages)
        if added:
            ext_obj = {'ContentPackages': sorted(ntiids)}
            update_object_from_external_object(self.context, ext_obj, False)
            added = [find_object_with_ntiid(x) for x in added]
            notify(ContentBundleUpdatedEvent(self.context, added=added, external=ext_obj))
        return self.context


@view_config(name='RemovePackage')
@view_config(name='RemovePackages')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=ACT_UPDATE,
               context=IContentPackageBundle)
class ContentPackageBundleRemovePackagesView(ContentPackageBundleMixinView):

    def __call__(self):
        ntiids = self.get_ntiids()
        packages = {x.ntiid for x in self.context.ContentPackages or ()}
        removed = packages.difference(ntiids)
        if removed:
            ext_obj = {'ContentPackages': sorted(removed)}
            update_object_from_external_object(self.context, ext_obj, False)
            removed = [find_object_with_ntiid(x) for x in removed]
            notify(ContentBundleUpdatedEvent(self.context, removed=removed, external=ext_obj))
        return self.context

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import uuid
import shutil
import zipfile

from requests.structures import CaseInsensitiveDict

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

import six

from zope import component

from zope import lifecycleevent

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite
from zope.component.hooks import site as current_site

from zope.event import notify

from zope.file.file import File

from zope.intid.interfaces import IIntIds

from nti.app.authentication import get_remote_user

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary import VIEW_USER_BUNDLE_RECORDS
from nti.app.contentlibrary import VIEW_BUNDLE_GRANT_ACCESS
from nti.app.contentlibrary import VIEW_BUNDLE_REMOVE_ACCESS

from nti.app.contentlibrary import MessageFactory as _

from nti.app.contentlibrary.hostpolicy import get_site_provider

from nti.app.contentlibrary.interfaces import IUserBundleRecord

from nti.app.contentlibrary.model import UserBundleRecord

from nti.app.contentlibrary.utils import is_bundle_visible_to_user
from nti.app.contentlibrary.utils import get_visible_bundles_for_user

from nti.app.contentlibrary.utils.bundle import save_bundle

from nti.app.contentlibrary.views import ContentBundlesPathAdapter
from nti.app.contentlibrary.views import ContentPackageBundleUsersPathAdapter

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.internalization import update_object_from_external_object

from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentEditRequestUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.publishing import VIEW_PUBLISH
from nti.app.publishing import VIEW_UNPUBLISH

from nti.app.publishing.views import PublishView
from nti.app.publishing.views import UnpublishView

from nti.app.users.utils import get_community_or_site_members

from nti.app.users.views.list_views import SiteUsersView

from nti.appserver.ugd_edit_views import ContainerContextUGDPostView

from nti.contentlibrary.bundle import DEFAULT_BUNDLE_MIME_TYPE
from nti.contentlibrary.bundle import PUBLISHABLE_BUNDLE_MIME_TYPE

from nti.contentlibrary.interfaces import IContentPackageBundle
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary
from nti.contentlibrary.interfaces import IFilesystemContentPackageLibrary
from nti.contentlibrary.interfaces import IPublishableContentPackageBundle

from nti.contentlibrary.interfaces import ContentBundleUpdatedEvent

from nti.contentlibrary.utils import make_presentation_asset_dir
from nti.contentlibrary.utils import make_content_package_bundle_ntiid
from nti.contentlibrary.utils import is_valid_presentation_assets_source

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ACT_NTI_ADMIN
from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.authorization import is_site_admin
from nti.dataserver.authorization import is_admin_or_site_admin

from nti.dataserver.authorization import is_admin_or_content_admin_or_site_admin

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import IAccessProvider
from nti.dataserver.interfaces import ISiteAdminUtility

from nti.dataserver.users.entity import Entity

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import StandardInternalFields

from nti.externalization.proxy import removeAllProxies

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.interfaces import IHostPolicyFolder

NTIID = StandardExternalFields.NTIID
TOTAL = StandardExternalFields.TOTAL
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

    ASSET_MULTIPART_KEYS = ('catalog-source',
                            'catalog-background',
                            'catalog-promo-large',
                            'catalog-entry-cover',
                            'catalog-entry-thumbnail')

    @Lazy
    def extra(self):
        return str(uuid.uuid4().time_low)

    @Lazy
    def _source_dict(self):
        """
        A dictionary of multipart inputs: name -> file.
        """
        return get_all_sources(self.request)

    def _make_asset_tmpdir(self, source_dict):
        """
        Make a tmp directory holding the presentation asset files to be moved
        to the appropriate destination.
        """
        if not source_dict:
            return
        if set(self.ASSET_MULTIPART_KEYS) - set(source_dict):
            # Do not have all of our multipart keys
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Missing presentation asset files."),
                                 'code': 'InvalidPresenationAssetFiles',
                             },
                             None)
        catalog_source = source_dict.get('catalog-source')
        catalog_promo = source_dict.get('catalog-promo-large')
        catalog_cover = source_dict.get('catalog-entry-cover')
        catalog_background = source_dict.get('catalog-background')
        catalog_thumbnail = source_dict.get('catalog-entry-thumbnail')
        return make_presentation_asset_dir(catalog_source,
                                           catalog_background,
                                           catalog_promo,
                                           catalog_cover,
                                           catalog_thumbnail)

    def get_source(self, request=None):
        """
        Return the validated presentation asset source.
        """
        request = self.request if not request else request
        # pylint: disable=no-member
        source_files = self._source_dict.values()
        for source_file in source_files or ():
            source_file.seek(0)
            if zipfile.is_zipfile(source_file):
                # Ok, return our zip file once validated
                return self._validate_asset_zip(source_file)
        # Otherwise, we have asset files we need to process
        return self._make_asset_tmpdir(self._source_dict)

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

    def _validate_asset_zip(self, assets):
        """
        Validate and return the given presentation asset zip.
        """
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
        # pylint: disable=expression-not-assigned
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
        # pylint: disable=no-member
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
            # save assets source in a zope file
            archive = File()
            with archive.open("w") as fp:
                fp.write(assets.read())
            # pylint: disable=protected-access
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
            # pylint: disable=expression-not-assigned
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
             request_method='DELETE',
             context=IContentPackageBundle)
class DeleteContentPackageBundleView(AbstractAuthenticatedView):

    def __call__(self):
        if not is_admin_or_content_admin_or_site_admin(self.remoteUser):
            raise hexc.HTTPForbidden()
        # pylint: disable=no-member
        bundle = self.context
        logger.info('Deleting bundle (%s)', bundle.ntiid)
        library = component.queryUtility(IContentPackageBundleLibrary)
        try:
            del library[bundle.ntiid]
        except (AttributeError, KeyError):
            logger.info("Bundle not in library (%s)", bundle.ntiid)
        return hexc.HTTPNoContent()


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
        if assets is None:
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
        elif self._site_community is not None:
            result = (self._site_community,)
        else:
            result = get_community_or_site_members(True)
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
        # pylint: disable=no-member,not-an-iterable
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
        # pylint: disable=no-member,not-an-iterable
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
              or data.get('package') \
              or data.get('packages')
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
        # pylint: disable=no-member
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
        # pylint: disable=no-member
        packages = {x.ntiid for x in self.context.ContentPackages or ()}
        remaining = packages.difference(ntiids)
        if len(remaining) != len(packages):
            ext_obj = {'ContentPackages': sorted(remaining)}
            update_object_from_external_object(self.context, ext_obj, False)
            removed = [find_object_with_ntiid(x) for x in ntiids]
            notify(ContentBundleUpdatedEvent(self.context, removed=removed, external=ext_obj))
        return self.context


class AbstractBundleRecordView(AbstractAuthenticatedView):

    @Lazy
    def _is_admin(self):
        return is_admin_or_site_admin(self.remoteUser)

    def _can_admin_user(self, user):
        # Verify a site admin is administering a user in their site.
        result = True
        if is_site_admin(self.remoteUser):
            admin_utility = component.getUtility(ISiteAdminUtility)
            result = admin_utility.can_administer_user(self.remoteUser, user)
        return result

    def _check_access(self, user):
        # 403 if not admin or instructor or self
        return (   self._is_admin \
                or self.remoteUser == user) \
            and self._can_admin_user(user)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IUserBundleRecord,
             request_method='GET')
class UserBundleRecordView(AbstractBundleRecordView):
    """
    A view that returns the :class:`IUserBundleRecord`.
    """

    def __call__(self):
        # pylint: disable=no-member
        if not self._check_access(self.context.User):
            raise_json_error(self.request,
                             hexc.HTTPForbidden,
                             {
                                 'message': _(u"Cannot view user bundle record."),
                                 'code': 'CannotAccessUserBundleRecordsError'
                             },
                             None)
        return self.context


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IUser,
             name=VIEW_USER_BUNDLE_RECORDS,
             request_method='GET')
class UserBundleRecordsView(AbstractBundleRecordView,
                            BatchingUtilsMixin):
    """
    A view that returns the user book records.
    """

    _DEFAULT_BATCH_START = 0
    _DEFAULT_BATCH_SIZE = None

    def __call__(self):
        if not self._check_access(self.context):
            raise_json_error(self.request,
                             hexc.HTTPForbidden,
                             {
                                 'message': _(u"Cannot view user bundle record."),
                                 'code': 'CannotAccessUserBundleRecordsError'
                             },
                             None)
        bundles = get_visible_bundles_for_user(self.context)
        if not bundles:
            raise_json_error(self.request,
                             hexc.HTTPNotFound,
                             {
                                 'message': _(u"User bundle records not found."),
                                 'code': 'UserBundleRecordsNotFound'
                             },
                             None)
        result = LocatedExternalDict()
        bundles = sorted(bundles, key=lambda x:x.title)
        records = []
        for bundle in bundles:
            bundle_record = UserBundleRecord(User=self.context, Bundle=bundle)
            # We want this so we have a traversable path to this record.
            bundle_record.__parent__  = ContentPackageBundleUsersPathAdapter(bundle, self.request)
            records.append(bundle_record)
        result[TOTAL] = len(records)
        self._batch_items_iterable(result, records)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ContentPackageBundleUsersPathAdapter,
             request_method='GET')
class BundleMembersView(SiteUsersView):
    """
    A view that returns the members of this :class:`IContentPackageBundle`.
    This will be either the full site membership, or, if a bundle is
    restricted, the members which have access.

    SiteUsers restricts this `call` to only admins and site admins.
    """

    @Lazy
    def bundle(self):
        # pylint: disable=no-member
        return self.context.context

    def transformer(self, user):  # pylint: disable=arguments-differ
        # We do not want to externalize the bundle `n` times.
        result = UserBundleRecord(User=user, Bundle=None)
        result.__parent__ = self.context
        return result

    def get_users(self, site):
        result = super(BundleMembersView, self).get_users(site)
        # pylint: disable=no-member
        if self.bundle.RestrictedAccess:
            result = [x for x in result if is_bundle_visible_to_user(x, self.bundle)]
        return result

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import time
import datetime

from BTrees.OOBTree import OOBTree

from pyramid.interfaces import IRequest

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.deprecation import deprecated

from zope.location.interfaces import IContained

from zope.security.interfaces import IPrincipal

from nti.app.contentlibrary.acl import role_for_content_bundle

from nti.app.contentlibrary.interfaces import IContentPackageMetadata

from nti.app.contentlibrary.model import ContentPackageSyncMetadata

from nti.app.contentlibrary.utils import role_for_content_package

from nti.appserver.context_providers import get_top_level_contexts

from nti.appserver.interfaces import IJoinableContextProvider
from nti.appserver.interfaces import ForbiddenContextException
from nti.appserver.interfaces import IHierarchicalContextProvider
from nti.appserver.interfaces import ITopLevelContainerContextProvider

from nti.appserver.pyramid_authorization import is_readable

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageBundle
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.coremetadata.interfaces import IContextLastSeenContainer
from nti.coremetadata.interfaces import ILastSeenProvider

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import CONTENT_ROLE_PREFIX

from nti.dataserver.authorization_acl import has_permission

from nti.dataserver.contenttypes.forums.interfaces import IPost
from nti.dataserver.contenttypes.forums.interfaces import ITopic
from nti.dataserver.contenttypes.forums.interfaces import IForum

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import system_user
from nti.dataserver.interfaces import IAccessProvider
from nti.dataserver.interfaces import IMutableGroupMember

from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject

from nti.externalization.proxy import removeAllProxies

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


# Bundles


@interface.implementer(IPrincipal)
@component.adapter(IContentPackageBundle)
def bundle_to_principal(bundle):
    bundle = removeAllProxies(bundle)
    creator = getattr(bundle, 'creator', None)
    return IPrincipal(creator) if creator else system_user


def _content_unit_to_bundles(unit):
    result = []
    package = find_interface(unit, IContentPackage, strict=False)
    bundle_catalog = component.queryUtility(IContentPackageBundleLibrary)
    bundles = bundle_catalog.getBundles() if bundle_catalog is not None else ()
    for bundle in bundles or ():
        if package in bundle.ContentPackages or ():
            result.append(bundle)
    return result


@component.adapter(IContentUnit)
@interface.implementer(IContentPackageBundle)
def _content_unit_to_bundle(unit):
    bundles = _content_unit_to_bundles(unit)
    return bundles[0] if bundles else None


# Context providers


def _get_bundles_from_container(obj):
    results = set()
    catalog = get_library_catalog()
    if catalog:
        containers = catalog.get_containers(obj)
        for container in containers:
            container = find_object_with_ntiid(container)
            bundle = IContentPackageBundle(container, None)
            if bundle is not None:
                results.add(bundle)
    return results


@component.adapter(interface.Interface, IUser)
@interface.implementer(IHierarchicalContextProvider)
def _hierarchy_from_obj(obj, unused_user):
    container_bundles = _get_bundles_from_container(obj)
    results = [(bundle,) for bundle in container_bundles]
    results = (results,) if results else results
    return results


@component.adapter(IContentUnit, IUser)
@interface.implementer(ITopLevelContainerContextProvider)
def _bundles_from_unit(obj, unused_user):
    # We could tweak the adapter above to return
    # all possible bundles, or use the container index.
    bundle = IContentPackageBundle(obj, None)
    result = None
    if bundle:
        result = (bundle,)
    else:
        # Content package
        # same in hierarchy
        package = IContentPackage(obj, None)
        result = (package,)
    return result


@component.adapter(IPost)
@interface.implementer(ITopLevelContainerContextProvider)
def _bundles_from_post(obj):
    bundle = find_interface(obj, IContentPackageBundle, strict=False)
    if bundle is not None:
        return (bundle,)


@component.adapter(ITopic)
@interface.implementer(ITopLevelContainerContextProvider)
def _bundles_from_topic(obj):
    bundle = find_interface(obj, IContentPackageBundle, strict=False)
    if bundle is not None:
        return (bundle,)


@component.adapter(IForum)
@interface.implementer(ITopLevelContainerContextProvider)
def _bundles_from_forum(obj):
    bundle = find_interface(obj, IContentPackageBundle, strict=False)
    if bundle is not None:
        return (bundle,)


def _get_top_level_contexts(obj):
    results = set()
    try:
        top_level_contexts = get_top_level_contexts(obj)
        for top_level_context in top_level_contexts:
            if IContentPackageBundle.providedBy(top_level_context):
                results.add(top_level_context)
    except ForbiddenContextException:
        pass
    return results


@component.adapter(interface.Interface)
@interface.implementer(IJoinableContextProvider)
def _bundles_from_container_object(obj):
    """
    Using the container index, look for catalog entries that contain
    the given object.
    """
    results = set()
    bundles = _get_top_level_contexts(obj)
    for bundle in bundles or ():
        # We only want to add publicly available entries.
        if is_readable(bundle):
            results.add(bundle)
    return results


# traversal


@component.adapter(IRequest)
@interface.implementer(IContentUnit)
def _unit_from_request(request):
    """
    We may have our content unit instance stashed in the request if it
    was in our path.
    """
    try:
        return request.unit_traversal_context
    except AttributeError:
        return None


@component.adapter(IRequest)
@interface.implementer(IContentPackage)
def _package_from_request(request):
    return _unit_from_request(request)


# Containers


from persistent.mapping import PersistentMapping


deprecated('_PresentationAssetContainer', 'no longer used')
class _PresentationAssetContainer(PersistentMapping,
                                  PersistentCreatedAndModifiedTimeObject):
    def assets(self):
        return ()


@interface.implementer(IPresentationAssetContainer, IContained)
class _PresentationAssetOOBTree(OOBTree, PersistentCreatedAndModifiedTimeObject):

    __name__ = None
    __parent__ = None

    _SET_CREATED_MODTIME_ON_INIT = False

    def __init__(self, *args, **kwargs):
        OOBTree.__init__(self)
        PersistentCreatedAndModifiedTimeObject.__init__(self, *args, **kwargs)

    def append(self, item):
        self[item.ntiid] = item

    def extend(self, items):
        for item in items or ():
            self.append(item)

    def assets(self):
        return list(self.values())


@interface.implementer(IPresentationAssetContainer)
def presentation_asset_items_factory(context):
    try:
        # pylint: disable=protected-access
        result = context._presentation_asset_item_container
        return result
    except AttributeError:
        result = context._presentation_asset_item_container = _PresentationAssetOOBTree()
        result.createdTime = time.time()
        result.__parent__ = context
        result.__name__ = '_presentation_asset_item_container'
        return result


@component.adapter(IContentPackage)
@interface.implementer(IAccessProvider)
class _PackageAccessProvider(object):
    """
    An access provider that grants and removes access to a package.
    """

    def __init__(self, context):
        self.context = self.bundle = context

    @Lazy
    def _package_role(self):
        return role_for_content_package(self.context)

    def _get_membership(self, entity):
        membership = component.getAdapter(entity,
                                          IMutableGroupMember,
                                          CONTENT_ROLE_PREFIX)
        return membership

    def grant_access(self, entity, *unused_args, **unused_kwargs):
        """
        Grant access to the package.
        """
        logger.info("Granting access to package (%s) (%s)",
                    self.context.ntiid, entity.username)
        membership = self._get_membership(entity)
        original_groups = set(membership.groups)
        new_groups = original_groups | set((self._package_role,))
        if new_groups != original_groups:
            # be idempotent
            membership.setGroups(new_groups)

    def remove_access(self, entity):
        """
        Remove access to the package.
        """
        logger.info("Removing access to package (%s) (%s)",
                    self.context.ntiid, entity.username)
        membership = self._get_membership(entity)
        original_groups = set(membership.groups)
        new_groups = original_groups - set((self._package_role,))
        if new_groups != original_groups:
            # be idempotent
            membership.setGroups(new_groups)


@component.adapter(IContentPackageBundle)
@interface.implementer(IAccessProvider)
class _BundleAccessProvider(object):
    """
    An access provider that grants and removes access to a bundle and its
    underlying packages.
    """

    def __init__(self, context):
        self.context = self.bundle = context

    @Lazy
    def _packages(self):
        return tuple(self.context.ContentPackages or ())

    @Lazy
    def _bundle_role(self):
        return role_for_content_bundle(self.context)

    @Lazy
    def _package_context_roles(self):
        result = set()
        # pylint: disable=not-an-iterable
        for package in self._packages:
            package_role = role_for_content_package(package)
            result.add(package_role)
        return result

    def _get_membership(self, entity):
        membership = component.getAdapter(entity,
                                          IMutableGroupMember,
                                          CONTENT_ROLE_PREFIX)
        return membership

    def grant_access(self, entity, *unused_args, **unused_kwargs):
        """
        Grant access to the bundle and all :class:`IContentPackage` objects
        within the bundle.
        """
        logger.info("Granting access to bundle (%s) (%s)",
                    self.context.ntiid, entity.username)
        membership = self._get_membership(entity)
        original_groups = set(membership.groups)
        new_groups = original_groups | set((self._bundle_role,)) | self._package_context_roles
        if new_groups != original_groups:
            # be idempotent
            membership.setGroups(new_groups)

    def _has_access(self, bundle, entity):
        # Make sure we do not include our context
        # This is tricky; normally bundles that are completely visible only
        # point to packages that are also completely visible. We should not
        # interfere in that relationship (e.g. unrestricted bundles that point
        # to restricted packages is an undefined relationship).
        # Must pass entity here to get effective principals.
        # Must skip cache since bundle access has changed.
        return  bundle != self.context \
            and bundle.RestrictedAccess \
            and has_permission(ACT_READ, bundle, entity,
                               skip_cache=True)

    def _get_accessible_packages(self, entity):
        """
        We're losing access to a set of packages, but take care to make sure
        we do not have access via an alternate bundle.
        """
        # This might be expensive once we get a lot of bundles; should be fine
        # for now though.
        result = set()
        bundle_library = component.getUtility(IContentPackageBundleLibrary)
        for bundle in bundle_library.getBundles() or ():
            if self._has_access(bundle, entity):
                result.update(bundle.ContentPackages)
        return result

    def _get_context_roles_to_remove(self, entity):
        accessible_packages = set(self._packages) & self._get_accessible_packages(entity)
        accessible_roles = set(
            role_for_content_package(x) for x in accessible_packages
        )
        return self._package_context_roles - accessible_roles

    def remove_access(self, entity):
        """
        Grant access to the bundle and all :class:`IContentPackage` objects
        within the bundle that are not accessible otherwise.
        """
        logger.info("Removing access to bundle (%s) (%s)",
                    self.context.ntiid, entity.username)
        membership = self._get_membership(entity)
        original_groups = set(membership.groups)
        # Must update bundle access first to determine whether we still have
        # access to the underlying packages (perhaps from another entity).
        new_bundle_groups = original_groups - set((self._bundle_role,))
        if new_bundle_groups != original_groups:
            # be idempotent
            membership.setGroups(new_bundle_groups)
        # If we still have access to the bundle (from another entity/membership
        # perhaps), we are a no-op since the entity should still have access to
        # the underlying packages.
        if not has_permission(ACT_READ, self.context, entity.username):
            context_roles = self._get_context_roles_to_remove(entity)
            new_groups = new_bundle_groups - context_roles
            if new_groups != new_bundle_groups:
                # be idempotent
                membership.setGroups(new_groups)


@component.adapter(IContentPackage)
@interface.implementer(IContentPackageMetadata)
def content_package_sync_meta_factory(context):
    try:
        # pylint: disable=protected-access
        result = context._content_package_sync_metadata
    except AttributeError:
        result = context._content_package_sync_metadata = ContentPackageSyncMetadata()
        result.createdTime = time.time()
        result.__parent__ = context
        result.__name__ = '_content_package_sync_metadata'
    return result


@component.adapter(IUser, IContentPackageBundle)
@interface.implementer(ILastSeenProvider)
class _BundleLastSeenProvider(object):

    def __init__(self, user, context):
        self.user = user
        self.context = context

    @Lazy
    def lastSeenTime(self):
        container = IContextLastSeenContainer(self.user, None)
        if container:
            # pylint: disable=too-many-function-args
            ntiid = getattr(self.context, 'ntiid', None)
            _dt = container.get_timestamp(ntiid) if ntiid else None
            return datetime.datetime.utcfromtimestamp(_dt) if _dt else None
        return None

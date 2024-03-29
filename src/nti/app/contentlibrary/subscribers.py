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

from zope.securitypolicy.rolepermission import AnnotationRolePermissionManager

from zope.traversing.interfaces import IBeforeTraverseEvent

from nti.app.contentlibrary.interfaces import IContentBoard
from nti.app.contentlibrary.interfaces import IContentPackageRolePermissionManager

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageBundle
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageAddedEvent
from nti.contentlibrary.interfaces import IContentPackageReplacedEvent
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary
from nti.contentlibrary.interfaces import IContentPackageLibraryDidSyncEvent

from nti.contenttypes.completion.interfaces import IUserProgressUpdatedEvent

from nti.contenttypes.completion.utils import update_completion

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ACT_CONTENT_EDIT
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.publishing.interfaces import IObjectPublishedEvent

from nti.site.interfaces import IHostPolicySiteManager

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


# role events


@component.adapter(IContentPackage)
@interface.implementer(IContentPackageRolePermissionManager)
class ContentPackageRolePermissionManager(AnnotationRolePermissionManager):

    def initialize(self):
        # pylint: disable=protected-access
        if not self.map or not self.map._byrow:
            # Initialize with perms for our global content admin.
            for perm in (ACT_READ, ACT_CONTENT_EDIT, ACT_UPDATE):
                self.grantPermissionToRole(perm.id, ROLE_CONTENT_ADMIN.id)


def _initialize_content_package_roles(package):
    package_role_manager = IContentPackageRolePermissionManager(package)
    if package_role_manager is not None:
        # pylint: disable=too-many-function-args
        package_role_manager.initialize()


@component.adapter(IContentPackage, IContentPackageAddedEvent)
def _initialize_package_roles(content_package, unused_event):
    _initialize_content_package_roles(content_package)


@component.adapter(IContentPackage, IContentPackageReplacedEvent)
def _update_package_roles(content_package, unused_event):
    _initialize_content_package_roles(content_package)


# forum events


@component.adapter(IContentPackageLibrary, IContentPackageLibraryDidSyncEvent)
def _on_content_pacakge_library_synced(library, unused_event):
    site = find_interface(library, IHostPolicySiteManager, strict=False)
    if site is not None:
        bundle_library = site.getUtility(IContentPackageBundleLibrary)
        for bundle in bundle_library.values():
            board = IContentBoard(bundle, None)
            if board is not None:
                # pylint: disable=too-many-function-args
                board.createDefaultForum()


# bundle events


@component.adapter(IContentPackageBundle, IObjectPublishedEvent)
def _on_content_bundle_published(bundle, unused_event):
    board = IContentBoard(bundle, None)
    if board is not None:
        # pylint: disable=too-many-function-args
        board.createDefaultForum()


# traversal


@component.adapter(IContentUnit, IBeforeTraverseEvent)
def unit_traversal_context_subscriber(unit, _):
    """
    We commonly need access to the unit context in underlying
    requests/decorators. Store that here for easy access.
    """
    request = get_current_request()
    if request is not None:
        request.unit_traversal_context = unit


@component.adapter(IContentUnit, IUserProgressUpdatedEvent)
def _content_unit_progress(content_unit, event):
    """
    On reading progress update, update completion.
    """
    update_completion(content_unit,
                      content_unit.ntiid,
                      event.user,
                      event.context)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from zope.lifecycleevent.interfaces import IObjectAddedEvent

from zope.securitypolicy.rolepermission import AnnotationRolePermissionManager

from nti.app.contentlibrary.interfaces import IContentBoard
from nti.app.contentlibrary.interfaces import IContentPackageRolePermissionManager

from nti.app.contentlibrary.model import ContentBundleCommunity

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageBundle
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageAddedEvent
from nti.contentlibrary.interfaces import IContentPackageReplacedEvent
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary
from nti.contentlibrary.interfaces import IContentPackageLibraryDidSyncEvent

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ACT_CONTENT_EDIT
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.site.interfaces import IHostPolicySiteManager

from nti.traversal.traversal import find_interface


# role events


@component.adapter(IContentPackage)
@interface.implementer(IContentPackageRolePermissionManager)
class ContentPackageRolePermissionManager(AnnotationRolePermissionManager):

    def initialize(self):
        if not self.map or not self.map._byrow:
            # Initialize with perms for our global content admin.
            for perm in (ACT_READ, ACT_CONTENT_EDIT, ACT_UPDATE):
                self.grantPermissionToRole(perm.id, ROLE_CONTENT_ADMIN.id)


def _initialize_content_package_roles(package):
    package_role_manager = IContentPackageRolePermissionManager(package)
    if package_role_manager is not None:
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
                board.createDefaultForum()


# bundle events


@component.adapter(IContentPackageBundle, IObjectAddedEvent)
def _on_content_bundle_added(bundle, unused_event):
    try:
        intids = component.getUtility(IIntIds)
        doc_id = intids.queryId(bundle)
        if doc_id is not None:
            doc_id = str(doc_id)
            community = ContentBundleCommunity.get_community(doc_id)
            if community is None:
                ContentBundleCommunity.create_community(username=doc_id)
    except (TypeError, LookupError):  # tests
        pass

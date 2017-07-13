#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Atom workspace/collection related functionality for content package library.

This also handles external permissioning of entries in the library.

.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.cachedescriptors.property import CachedProperty

from zope.container.interfaces import IContained

from zope.proxy.decorator import ProxyBase

from pyramid.threadlocal import get_current_request

from nti.app.contentlibrary.workspaces.interfaces import ILibraryCollection

from nti.appserver.pyramid_authorization import is_readable

from nti.appserver.workspaces.interfaces import IWorkspace
from nti.appserver.workspaces.interfaces import ICollection
from nti.appserver.workspaces.interfaces import IUserService

from nti.contentlibrary import ALL_CONTENT_MIMETYPES

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.property.property import alias


class _PermissionedContentPackageLibrary(ProxyBase):
    """
    A wrapper around the global library that implements
    permissioning of the available titles for the user (which in
    turn gets better etags; see :class:`.library_views.ContentPackageLibraryCacheController`)
    This is a first-step towards better user-specific libraries.

    .. note:: This currently only uses the request, not the user,
            so no matter how you traverse to it, it will be
            permissioned to the current user, not the user in the path.
    """

    def __new__(cls, base, request):
        return ProxyBase.__new__(cls, base)

    def __init__(self, base, request):
        ProxyBase.__init__(self, base)
        self.library = base
        self._v_request = request
        self._v_contentPackages = None

    def _test_is_readable(self, content_package, request=None):
        # test readability
        request = request or self._v_request
        result = is_readable(content_package, request)
        if not result:
            # Nope. What about a top-level child?
            # TODO: Why we check children?
            result = any(is_readable(x, request)
                         for x in content_package.children or ())
        return result

    @property
    def contentPackages(self):
        if self._v_contentPackages is None:
            self._v_contentPackages = list(filter(self._test_is_readable,
                                                  self.library.contentPackages))
        return self._v_contentPackages


# A chain for getting the library that a user can view
# during workspace access.
# The chain is a bit convoluted, but very flexible. (note that the
# bundle library does not yet use a chain like this.)
#
# At the top, the workspace for the (user,request) is queried.
# That proceeds to get a ContentpackageLibrary for the (user,request)
#   (instead of the global library).
# That library turns out to wrap the global library and apply permissioning
#   through the proxy defined above.
# Ultimately, it is that proxy that goes in the workspace.


@interface.implementer(IContentPackageLibrary)
def _library_for_library(library, request):
    result = _PermissionedContentPackageLibrary(library, request)
    return result


@interface.implementer(IContentPackageLibrary)
def _library_for_user(unused_user, request):
    global_library = component.queryUtility(IContentPackageLibrary)
    result = component.queryMultiAdapter((global_library, request),
                                         IContentPackageLibrary)
    return result


@interface.implementer(IWorkspace)
def _library_workspace_for_library(library, request):
    library = component.getMultiAdapter((library, request),
                                        IContentPackageLibrary)
    ws = LibraryWorkspace(library)
    return ws


@interface.implementer(IWorkspace)
def _library_workspace_for_user(user, request):
    library = component.queryMultiAdapter((user, request),
                                          IContentPackageLibrary)
    if library is not None:
        ws = LibraryWorkspace(library)
        ws.__parent__ = user
        return ws


@component.adapter(IUserService)
@interface.implementer(IWorkspace)
def _library_workspace(user_service):
    request = get_current_request()
    user = user_service.user
    ws = component.queryMultiAdapter((user, request),
                                     IWorkspace,
                                     name='Library')
    if ws is not None:
        ws.__parent__ = user
        return ws


@interface.implementer(IWorkspace, IContained)
class LibraryWorkspace(object):

    __parent__ = None
    __name__ = 'Library'

    name = alias('__name__')

    def __init__(self, lib):
        self._library = lib

    @CachedProperty
    def collections(self):
        # Right now, we're assuming one collection for the whole library
        adapt = component.getAdapter(self._library, ICollection)
        adapt.__parent__ = self
        return (adapt,)

    # Traversable
    def __getitem__(self, key):
        # Yes, we traverse to our actual library,
        # not the collection wrapper. It will get
        # converted back to the collection for externalization.
        for i in self.collections:
            if key == i.__name__:
                return i.library
        raise KeyError(key)

    def __len__(self):
        return 1


@interface.implementer(ILibraryCollection)
@component.adapter(IContentPackageLibrary)
class LibraryCollection(object):

    __parent__ = None
    __name__ = 'Main'

    name = alias('__name__')

    # BWC
    _library = alias('context')

    def __init__(self, lib):
        self.context = lib

    @property
    def library(self):
        return self.context

    @property
    def library_items(self):
        return self.context.contentPackages

    @property
    def accepts(self):
        return ALL_CONTENT_MIMETYPES


# bundles


@interface.implementer(ILibraryCollection)
@component.adapter(IContentPackageBundleLibrary)
class BundleLibraryCollection(LibraryCollection):

    __name__ = 'VisibleContentBundles'

    @property
    def library_items(self):
        for bundle in self.library.getBundles() or ():
            if is_readable(bundle):
                yield bundle

    def getBundles(self):
        return self.library_items


class BundleLibraryWorkspace(LibraryWorkspace):
    __name__ = 'ContentBundles'


@interface.implementer(IContentPackageBundleLibrary)
def _bundle_for_library(bundle_library, unused_request):
    return bundle_library


@interface.implementer(IContentPackageBundleLibrary)
def _bundle_for_user(unused_user, request):
    bundle_library = component.queryUtility(IContentPackageBundleLibrary)
    return component.queryMultiAdapter((bundle_library, request),
                                       IContentPackageBundleLibrary)


@interface.implementer(IWorkspace)
def _bundle_workspace_for_library(bundle_library, request):
    bundle_library = component.getMultiAdapter((bundle_library, request),
                                               IContentPackageBundleLibrary)
    if bundle_library is not None:
        return BundleLibraryWorkspace(bundle_library)


@interface.implementer(IWorkspace)
def _bundle_workspace_for_user(user, request):
    bundle_library = component.queryMultiAdapter((user, request),
                                                 IContentPackageBundleLibrary)
    if bundle_library is not None:
        ws = BundleLibraryWorkspace(bundle_library)
        ws.__parent__ = user
        return ws


@component.adapter(IUserService)
@interface.implementer(IWorkspace)
def _bundle_workspace(user_service):
    request = get_current_request()
    user = user_service.user
    ws = component.queryMultiAdapter((user, request),
                                     IWorkspace,
                                     name='ContentBundles')
    if ws is not None:
        ws.__parent__ = user
        return ws


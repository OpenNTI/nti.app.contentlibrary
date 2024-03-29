#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.app.contentlibrary.interfaces import IContentBoard

from nti.contentlibrary.interfaces import IGlobalContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.publishing.interfaces import IPublishable
from nti.publishing.interfaces import IPublishables

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IPublishables)
class LibraryPublishables(object):

    __slots__ = ()

    def __init__(self, *args):
        pass

    def _process_package(self, package, result):
        def _recur(unit):
            # check unit
            if IPublishable.providedBy(unit):
                result.append(unit)
            # assets
            container = IPresentationAssetContainer(unit)
            # pylint: disable=too-many-function-args
            for asset in container.assets():
                if IPublishable.providedBy(asset):
                    result.append(asset)
            # check children
            for child in unit.children or ():
                _recur(child)
        _recur(package)

    def _process_packages(self, result):
        result = [] if result is None else result
        library = component.queryUtility(IContentPackageLibrary)
        if library is not None:
            for package in library.contentPackages or ():
                if not IGlobalContentPackage.providedBy(package):
                    self._process_package(package, result)
        return result

    def _process_bundle(self, bundle, result):
        result = [] if result is None else result
        if IPublishable.providedBy(bundle):
            result.append(bundle)
        board = IContentBoard(bundle, None)
        if board:
            for forum in board.values():
                for topic in forum.values():
                    if IPublishable.providedBy(topic):
                        result.append(topic)
        return result

    def _process_bundles(self, result):
        result = [] if result is None else result
        library = component.queryUtility(IContentPackageBundleLibrary)
        if library is not None:
            for bundle in library.values():
                self._process_bundle(bundle, result)
        return result

    def iter_objects(self):
        result = self._process_packages([])
        result = self._process_bundles(result)
        return result

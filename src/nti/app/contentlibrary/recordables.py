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

from nti.contentlibrary.interfaces import IGlobalContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.recorder.interfaces import IRecordable
from nti.recorder.interfaces import IRecordables


@interface.implementer(IRecordables)
class LibraryRecordables(object):

    __slots__ = ()

    def _process_package(self, package, result):

        def _recur(unit):
            if IRecordable.providedBy(unit):
                result.append(unit)
            container = IPresentationAssetContainer(unit)
            for asset in container.assets():
                if IRecordable.providedBy(asset):
                    result.append(asset)
            for child in unit.children or ():
                _recur(child)

        _recur(package)

    def iter_objects(self):
        result = []
        library = component.queryUtility(IContentPackageLibrary)
        if library is not None:
            for package in library.contentPackages:
                if not IGlobalContentPackage.providedBy(package):
                    self._process_package(package, result)
        return result

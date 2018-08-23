#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: recordables.py 125307 2018-01-05 22:09:53Z carlos.sanchez $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.contentlibrary.interfaces import IGlobalContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.completion.interfaces import ICompletables
from nti.contenttypes.completion.interfaces import ICompletableItem

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICompletables)
class LibraryCompletables(object):

    __slots__ = ()

    def __init__(self, *args):
        pass

    def _process_package(self, package, result):

        def _recur(unit):
            if ICompletableItem.providedBy(unit):
                result.append(unit)
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

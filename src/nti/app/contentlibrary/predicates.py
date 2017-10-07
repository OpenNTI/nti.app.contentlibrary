#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IEditableContentPackage
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.dataserver.metadata.predicates import BasePrincipalObjects

logger = __import__('logging').getLogger(__name__)


class _PackageObjectsMixin(BasePrincipalObjects):

    @property
    def library(self):
        return component.queryUtility(IContentPackageLibrary)

    def _content_units(self, context):
        result = []
        def _recur(obj):
            result.append(obj)
            for child in obj.children or ():
                _recur(child)
        _recur(context)
        return result

    def _predicate(self, _):
        return False

    def iter_objects(self):
        result = []
        if self.library is not None:
            for item in self.library.contentPackages:
                if self._predicate(item):
                    result.extend(self._content_units(item))
        return result


@component.adapter(ISystemUserPrincipal)
class _SystemContentPackages(_PackageObjectsMixin):

    def _predicate(self, item):
        return not IEditableContentPackage.providedBy(item) \
            or self.is_system_username(self.creator(item))


@component.adapter(IUser)
class _UserContentPackages(_PackageObjectsMixin):

    def _predicate(self, item):
        result = IEditableContentPackage.providedBy(item) \
             and self.creator(item) == self.username
        return result


class _BundleObjectsMixin(BasePrincipalObjects):

    @property
    def library(self):
        return component.queryUtility(IContentPackageBundleLibrary)
        
    def _predicate(self, _):
        return False

    def iter_objects(self):
        result = []
        library = self.library
        bundles = library.getBundles() if library is not None else ()
        for item in bundles or ():
            if self._predicate(item):
                result.append(item)
        return result


@component.adapter(ISystemUserPrincipal)
class _SystemContentPackageBundles(_BundleObjectsMixin):

    def _predicate(self, item):
        return self.is_system_username(self.creator(item))


@component.adapter(IUser)
class _UserContentPackageBundles(_BundleObjectsMixin):

    def _predicate(self, item):
        return self.creator(item) == self.username

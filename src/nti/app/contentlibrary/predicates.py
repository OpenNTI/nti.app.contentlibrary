#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from functools import partial

from zope import component

from zope.cachedescriptors.property import Lazy

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IEditableContentPackage
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.dataserver.metadata.predicates import BasePrincipalObjects

from nti.site.hostpolicy import run_job_in_all_host_sites


class _PackageObjectsMixin(BasePrincipalObjects):

    @Lazy
    def intids(self):
        return component.getUtility(IIntIds)

    @property
    def library(self):
        return component.queryUtility(IContentPackageLibrary)

    def _content_units(self, context):
        result = []
        def _recur(obj):
            doc_id = self.intids.queryId(obj)
            if doc_id is not None:
                result.append(obj)
            for child in obj.children or ():
                _recur(child)
        _recur(context)
        return result

    def _predicate(self, _):
        return False

    def iter_items(self, result, seen):
        library = self.library
        if library is None:
            return result
        for item in library.contentPackages:
            doc_id = self.intids.queryId(item)
            if doc_id is not None and doc_id not in seen:
                seen.add(doc_id)
                if self._predicate(item):
                    result.append(item)
                    result.extend(self._content_units(item))
        return result
    
    def iter_objects(self):
        result = []
        seen = set()
        run_job_in_all_host_sites(partial(self.iter_items, result, seen))
        return result


@component.adapter(ISystemUserPrincipal)
class _SystemContentPackages(_PackageObjectsMixin):

    def _predicate(self, item):
        return not IEditableContentPackage.providedBy(item)


@component.adapter(IUser)
class _UserContentPackages(_PackageObjectsMixin):

    def _predicate(self, item):
        result = False
        if IEditableContentPackage.providedBy(item):
            creator = getattr(item.creator, 'username', None)
            creator = getattr(creator, 'id', creator) or ''
            result = creator.lower() == self.user.username.lower()
        return result


class _BundleObjectsMixin(BasePrincipalObjects):

    @Lazy
    def intids(self):
        return component.getUtility(IIntIds)

    @property
    def library(self):
        return component.queryUtility(IContentPackageBundleLibrary)

    def get_creator(self, bundle):
        creator = getattr(bundle.creator, 'username', None)
        creator = getattr(creator, 'id', creator)
        return creator or SYSTEM_USER_ID
        
    def _predicate(self, _):
        return False

    def iter_items(self, result, seen):
        library = self.library
        bundles = library.getBundles() if library is not None else ()
        for item in bundles or ():
            doc_id = self.intids.queryId(item)
            if doc_id is not None and doc_id not in seen:
                seen.add(doc_id)
                if self._predicate(item):
                    result.append(item)
        return result

    def iter_objects(self):
        result = []
        seen = set()
        run_job_in_all_host_sites(partial(self.iter_items, result, seen))
        return result


@component.adapter(ISystemUserPrincipal)
class _SystemContentPackageBundles(_BundleObjectsMixin):

    def _predicate(self, item):
        creator = self.get_creator(item)
        return creator == SYSTEM_USER_ID


@component.adapter(IUser)
class _UserContentPackageBundles(_BundleObjectsMixin):

    def _predicate(self, item):
        creator = self.get_creator(item)
        return creator.lower() == self.user.username.lower()

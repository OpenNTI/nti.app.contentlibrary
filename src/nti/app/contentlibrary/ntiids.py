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

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.ntiids.interfaces import INTIIDResolver

logger = __import__('logging').getLogger(__name__)


@interface.implementer(INTIIDResolver)
class _ContentResolver(object):

    def resolve(self, key):
        result = None
        library = component.queryUtility(IContentPackageLibrary)
        path = library.pathToNTIID(key) if library else None
        if path:
            result = path[-1]
        return result


@interface.implementer(INTIIDResolver)
class _BundleResolver(object):

    def resolve(self, key):
        result = None
        library = component.queryUtility(IContentPackageBundleLibrary)
        if library is not None:
            try:
                return library[key]
            except KeyError:
                pass
        return result

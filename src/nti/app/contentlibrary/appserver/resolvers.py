#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.appserver.interfaces import IContainerLeafResolver
from nti.appserver.interfaces import IContainerRootResolver

from nti.contentlibrary.interfaces import IContentPackageLibrary

class _DefaultContainerPathResolver(object):

    index = None

    def __init__(self, *args):
        pass

    @classmethod
    def resolve(cls, ntiid):
        library = component.queryUtility(IContentPackageLibrary)
        paths = library.pathToNTIID(ntiid) if library is not None else None
        return paths[cls.index] if paths else None

@interface.implementer(IContainerLeafResolver)
class _DefaultContainerLeafResolver(_DefaultContainerPathResolver):
    index = -1

@interface.implementer(IContainerRootResolver)
class _DefaultContainerRootResolver(_DefaultContainerPathResolver):
    index = 0

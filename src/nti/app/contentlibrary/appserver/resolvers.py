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

from nti.appserver.interfaces import INTIIDRootResolver

from nti.contentlibrary.interfaces import IContentPackageLibrary

@interface.implementer(INTIIDRootResolver)
class _DefaultNTIIDRootResolver(object):

    def __init__(self, *args):
        pass

    def resolve(self, ntiid):
        library = component.queryUtility(IContentPackageLibrary)
        paths = library.pathToNTIID(ntiid) if library is not None else None
        return paths[0] if paths else None

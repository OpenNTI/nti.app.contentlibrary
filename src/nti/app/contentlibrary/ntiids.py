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

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.dataserver import authorization_acl as nacl

from nti.dataserver.interfaces import ACLLocationProxy

from nti.ntiids.interfaces import INTIIDResolver


@interface.implementer(INTIIDResolver)
class _ContentResolver(object):

    def resolve(self, key):
        result = None
        library = component.queryUtility(IContentPackageLibrary)
        path = library.pathToNTIID(key) if library else None
        if path:
            result = path[-1]
            result = ACLLocationProxy(result, result.__parent__,
                                      result.__name__, nacl.ACL(result))
        return result


@interface.implementer(INTIIDResolver)
class _BundleResolver(object):

    def resolve(self, key):
        result = None
        library = component.queryUtility(IContentPackageBundleLibrary)
        if library is not None:
            try:
                result = library[key]
                result = ACLLocationProxy(result, result.__parent__,
                                          result.__name__, nacl.ACL(result))
            except KeyError:
                pass
        return result

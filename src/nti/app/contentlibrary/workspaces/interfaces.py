#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

from nti.appserver.workspaces.interfaces import ICollection

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.schema.field import Object


class ILibraryCollection(ICollection):
    """
    An :class:`ICollection` wrapping a :class:`.IContentPackageLibrary`.
    """

    library = Object(IContentPackageLibrary,
                     title=u"The library",
                     readonly=True)


class IContentBundleLibraryCollection(ILibraryCollection):
    """
    An :class:`ICollection` wrapping a :class:`.IContentPackageBundleLibrary`.
    """

    library = Object(IContentPackageBundleLibrary,
                     title=u"The library",
                     readonly=True)

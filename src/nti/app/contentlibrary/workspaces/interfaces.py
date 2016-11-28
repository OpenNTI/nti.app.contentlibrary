#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

from nti.appserver.workspaces.interfaces import ICollection

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.schema.field import Object

class ILibraryCollection(ICollection):
    """
    An :class:`ICollection` wrapping a :class:`.IContentPackageLibrary`.
    """

    library = Object(IContentPackageLibrary,
                      title="The library",
                      readonly=True)

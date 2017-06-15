#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

from zope.location.interfaces import ILocation

from nti.contentfragments.interfaces import IUnicode

from nti.dataserver.interfaces import ILastModified

from nti.schema.field import Object
from nti.schema.field import ListOrTuple


class IContentUnitPreferences(ILocation, ILastModified):
    """
    Storage location for preferences related to a content unit.
    """

    sharedWith = ListOrTuple(value_type=Object(IUnicode),
                             title="List of usernames to share with",
                             required=False)

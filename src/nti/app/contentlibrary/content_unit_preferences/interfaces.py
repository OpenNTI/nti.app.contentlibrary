#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope.location.interfaces import ILocation

from nti.base.interfaces import ILastModified

from nti.contentfragments.interfaces import IUnicode

from nti.schema.field import Object
from nti.schema.field import ListOrTuple


class IContentUnitPreferences(ILocation, ILastModified):
    """
    Storage location for preferences related to a content unit.
    """

    sharedWith = ListOrTuple(value_type=Object(IUnicode),
                             title=u"List of usernames to share with",
                             required=False)

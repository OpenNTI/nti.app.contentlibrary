#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

from zope.location.interfaces import ILocation

from dolmen.builtins import IUnicode

from nti.dataserver.interfaces import ILastModified

from nti.schema.field import List
from nti.schema.field import Object

class IContentUnitPreferences(ILocation, ILastModified):
	"""
	Storage location for preferences related to a content unit.
	"""
	# NOTE: This can actually be None in some cases, which makes it
	# impossible to validate this schema.
	sharedWith = List( value_type=Object(IUnicode),
					   title="List of usernames to share with" )

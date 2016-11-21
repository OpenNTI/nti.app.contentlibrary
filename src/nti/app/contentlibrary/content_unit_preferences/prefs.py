#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Support functions for dealing with preferences.


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.app.contentlibrary.content_unit_preferences.interfaces import IContentUnitPreferences

from nti.contentlibrary.interfaces import IContentUnit

from nti.ntiids import ntiids

def prefs_present(prefs):
	"""
	Does `prefs`, an IContentUnitPreferences object, represent a valid
	preference stored by the user? Note that even a blank, empty set
	of targets is a valid preference; a None value removes the
	preference.
	"""
	return prefs and prefs.sharedWith is not None

def find_prefs_for_content_and_user(starting_content_unit, remote_user):
	"""
	Given a :class:`.IContentUnit`, try to find sharing preferences
	for the user. These will first come from the stored values
	of the user, and secondarily from the data in the content units
	themselves.

	:return: A three-tuple giving the found prefereces object, a string
		giving the provenance of that, and finally the content unit
		it was found on.

	"""

	# Walk up the parent tree of content units (not including the mythical root)
	# until we run out, or find preferences
	def units():
		contentUnit = starting_content_unit
		while IContentUnit.providedBy(contentUnit):
			yield contentUnit, contentUnit.ntiid, contentUnit.ntiid
			contentUnit = contentUnit.__parent__
		# Also include the mythical root
		# (which has an empty container name)
		yield None, '', ntiids.ROOT

	# We will go at least once through this loop
	contentUnit = provenance = prefs = None
	for contentUnit, containerId, provenance in units():
		container = remote_user.getContainer(containerId)
		prefs = IContentUnitPreferences(container, None)
		if prefs_present(prefs):
			break
		prefs = None

	if not prefs_present(prefs):
		# OK, nothing found by querying the user. What about looking at
		# the units themselves?
		for contentUnit, containerId, provenance in units():
			if not contentUnit:
				# Don't try this for the root
				break

			prefs = IContentUnitPreferences(contentUnit, None)
			if prefs_present(prefs):
				break
			prefs = None
	return prefs, provenance, contentUnit

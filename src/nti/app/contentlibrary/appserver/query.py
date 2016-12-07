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

from nti.appserver.interfaces import IUserContainerQuerier

from nti.contentlibrary.indexed_data import get_catalog as lib_catalog

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIPollRef
from nti.contenttypes.presentation.interfaces import INTISurveyRef

from nti.ntiids import ntiids

from nti.site.site import get_component_hierarchy_names

@interface.implementer(IUserContainerQuerier)
class _UserContainerQuerier(object):

	def query(self, user, ntiid, include_stream, stream_only):
		containers = ()
		if ntiid == ntiids.ROOT:
			containers = set(user.iterntiids(include_stream=include_stream,
											 stream_only=stream_only))
		else:
			library = component.getUtility(IContentPackageLibrary)
			containers = set(library.childrenOfNTIID(ntiid))
			containers.add(ntiid)  # item

			# include media containers.
			catalog = lib_catalog()
			if catalog is not None:  # test mode
				# Should this be all types, or is that too expensive?
				sites = get_component_hierarchy_names()
				objects = catalog.search_objects(container_ntiids=containers,
												 sites=sites,
												 container_all_of=False,
												 provided=(INTIVideo, INTIAudio,
														   INTIPollRef, INTISurveyRef))
				for obj in objects:
					ntiid = getattr(obj, 'target', None) or obj.ntiid
					containers.add(ntiid)

		# We always include the unnamed root (which holds things like CIRCLED)
		# NOTE: This is only in the stream. Normally we cannot store contained
		# objects with an empty container key, so this takes internal magic
		containers.add('')  # root
		return containers
	__call__ = query

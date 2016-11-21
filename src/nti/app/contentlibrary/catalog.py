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

from pyramid.location import lineage

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage

from nti.contentlibrary.indexed_data.interfaces import INTIIDAdapter
from nti.contentlibrary.indexed_data.interfaces import ITargetAdapter
from nti.contentlibrary.indexed_data.interfaces import INamespaceAdapter
from nti.contentlibrary.indexed_data.interfaces import ISlideDeckAdapter
from nti.contentlibrary.indexed_data.interfaces import IContainersAdapter
from nti.contentlibrary.indexed_data.interfaces import IContainedTypeAdapter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import IPointer 
from nti.contenttypes.presentation.interfaces import IAssetRef
from nti.contenttypes.presentation.interfaces import INTISlide 
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.contenttypes.courses.utils import get_course_subinstances
from nti.contenttypes.courses.utils import get_courses_for_packages

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface

# Type

class _Type(object):

	__slots__ = (b'type',)

	def __init__(self, type_):
		self.type = type_

@component.adapter(IPresentationAsset)
@interface.implementer(IContainedTypeAdapter)
def _asset_to_contained_type(context):
	provided = iface_of_asset(context)
	return _Type(provided.__name__)

# Namespace

class _Namespace(object):

	__slots__ = (b'namespace',)

	def __init__(self, namespace):
		self.namespace = namespace

@interface.implementer(INamespaceAdapter)
@component.adapter(IPresentationAsset)
def _asset_to_namespace(context):
	node = find_interface(context, ICourseOutlineNode, strict=False)
	if node is not None:
		source = getattr(node, 'src', None)
		result = _Namespace(source) if source else None
	else:
		package = find_interface(context, IContentPackage, strict=False)
		result = _Namespace(package.ntiid) if package is not None else None
	return result

# Namespace

class _NTIID(object):

	__slots__ = (b'ntiid',)

	def __init__(self, ntiid):
		self.ntiid = ntiid

@interface.implementer(INTIIDAdapter)
@component.adapter(IPresentationAsset)
def _asset_to_ntiid(context):
	return _NTIID(context.ntiid)

# Namespace

class _Target(object):

	__slots__ = (b'target',)

	def __init__(self, target):
		self.target = target

@component.adapter(IPresentationAsset)
@interface.implementer(ITargetAdapter)
def _asset_to_target(context):
	if IPointer.providedBy(context) or IAssetRef.providedBy(context):
		return _Target(context.target)
	return None

# Containers

class _Containers(object):

	__slots__ = (b'containers',)

	def __init__(self, containers):
		self.containers = containers

def _package_lineage_to_containers(context):
	result = set()
	for location in lineage(context):
		if IContentUnit.providedBy(location):
			result.add(location.ntiid)
		if IContentPackage.providedBy(location):
			break
	result.discard(None)
	return result

def _course_lineage_to_containers(context):
	result = set()
	for location in lineage(context):
		if IPresentationAsset.providedBy(location):
			result.add(location.ntiid)
		if ICourseInstance.providedBy(location):
			course = location
			entry = ICourseCatalogEntry(course, None)
			result.add(getattr(entry, 'ntiid', None))
			break
	result.discard(None)
	return result

@component.adapter(IPresentationAsset)
@interface.implementer(IContainersAdapter)
def _asset_to_containers(context):
	containers = set()
	package = find_interface(context, IContentPackage, strict=False)
	if package is not None: # package asset
		containers.update(_package_lineage_to_containers(context))
		folder = find_interface(context, IHostPolicyFolder, strict=False)
		if folder is not None:
			courses = get_courses_for_packages(folder.__name__, package.ntiid)
			for course in courses:
				entry = ICourseCatalogEntry(course, None)
				containers.add(getattr(entry, 'ntiid', None))
	else: # course asset
		containers.update(_course_lineage_to_containers(context))
		for instance in get_course_subinstances(course):
			entry = ICourseCatalogEntry(instance, None)
			containers.add(getattr(entry, 'ntiid', None))
		
	# check for slides and slidevideos
	if		(INTISlide.providedBy(context) or INTISlideVideo.providedBy(context)) \
		and context.__parent__ is not None \
		and context.__parent__.ntiid:
		containers.add(context.__parent__.ntiid)
	
	containers.discard(None)
	containers.discard(context.ntiid)
	return _Containers(tuple(containers))

# Slide deck

class _SlideDeck(object):

	__slots__ = (b'videos',)

	def __init__(self, videos):
		self.videos = videos

@component.adapter(INTISlideDeck)
@interface.implementer(ISlideDeckAdapter)
def _slideck_data(context):
	videos = {v.video_ntiid for v in context.Videos or ()}
	return _SlideDeck(videos)

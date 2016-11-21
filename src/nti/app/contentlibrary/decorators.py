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

from zope.location.interfaces import ILocation

from pyramid.interfaces import IRequest

from nti.app.contentlibrary import LIBRARY_PATH_GET_VIEW

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.interfaces import IContentUnitInfo

from nti.contentlibrary.interfaces import IContentPackageBundle
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.dataserver.contenttypes.forums.interfaces import IPost
from nti.dataserver.contenttypes.forums.interfaces import ITopic
from nti.dataserver.contenttypes.forums.interfaces import IForum

from nti.dataserver.interfaces import IHighlight

from nti.externalization.externalization import to_external_ntiid_oid

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import SingletonDecorator

from nti.links.links import Link

from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

LINKS = StandardExternalFields.LINKS

def get_content_package_paths(ntiid):
	library = component.queryUtility(IContentPackageLibrary)
	paths = library.pathToNTIID(ntiid) if library else ()
	return paths

def get_content_package_ntiid(ntiid):
	paths = get_content_package_paths(ntiid)
	result = paths[0].ntiid if paths else None
	return result

@interface.implementer(IExternalMappingDecorator)
@component.adapter(IContentUnitInfo, IRequest)
class _ContentUnitInfoDecorator(AbstractAuthenticatedRequestAwareDecorator):
	"""
	Decorates context with ContentPackage NTIID
	"""

	def _predicate(self, context, result):
		result = bool(self._is_authenticated and context.contentUnit is not None)
		if result:
			try:
				ntiid = context.contentUnit.ntiid
				result = bool(is_valid_ntiid_string(ntiid))
			except AttributeError:
				result = False
		return result

	def _do_decorate_external(self, context, result):
		ntiid = get_content_package_ntiid(context.contentUnit.ntiid)
		if ntiid is not None:
			result['ContentPackageNTIID'] = ntiid

@interface.implementer(IExternalMappingDecorator)
@component.adapter(IContentUnitInfo, IRequest)
class _ContentUnitInfoTitleDecorator(AbstractAuthenticatedRequestAwareDecorator):
	"""
	Decorates context with ContentPackage title.
	"""

	def _predicate(self, context, result):
		result = bool(self._is_authenticated and context.contentUnit is not None)
		if result:
			try:
				context.contentUnit.title
			except AttributeError:
				result = False
		return result

	def _do_decorate_external(self, context, result):
		result['Title'] = context.contentUnit.title

@interface.implementer(IExternalMappingDecorator)
@component.adapter(IContentPackageBundle)
class _ContentBundlePagesLinkDecorator(object):
	"""
	Places a link to the pages view of a content bundle.
	"""

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping(self, context, result):
		_links = result.setdefault(LINKS, [])
		link = Link(context, rel='Pages', elements=('Pages',))
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		_links.append(link)

@interface.implementer(IExternalMappingDecorator)
@component.adapter(IHighlight)
class _UGDLibraryPathLinkDecorator(object):
	"""
	Create a `LibraryPath` link to our container id.
	"""

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping(self, context, result):
		container_id = context.containerId
		container = find_object_with_ntiid(container_id)
		external_ntiid = to_external_ntiid_oid(container) if container else None
		if external_ntiid is None:
			# Non-persistent content unit perhaps.
			# Just add library path to our note.
			external_ntiid = to_external_ntiid_oid(context)

		if external_ntiid is not None:
			path = '/dataserver2/%s' % LIBRARY_PATH_GET_VIEW
			link = Link(path, rel=LIBRARY_PATH_GET_VIEW, method='GET',
						params={'objectId': external_ntiid})
			_links = result.setdefault(LINKS, [])
			interface.alsoProvides(link, ILocation)
			link.__name__ = ''
			link.__parent__ = context
			_links.append(link)

@interface.implementer(IExternalMappingDecorator)
@component.adapter(IPost)
class _PostLibraryPathLinkDecorator(object):
	"""
	Create a `LibraryPath` link to our post.
	"""

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping(self, context, result):
		# Use the OID NTIID rather than the 'physical' path because
		# the 'physical' path may not quite be traversable at this
		# point. Not sure why that would be, but the ILocation parents
		# had a root above dataserver.
		target_ntiid = to_external_ntiid_oid(context)
		if target_ntiid is None:
			logger.warn("Failed to get ntiid; not adding LibraryPath link for %s", context)
			return

		_links = result.setdefault(LINKS, [])
		link = Link(target_ntiid, rel=LIBRARY_PATH_GET_VIEW, elements=(LIBRARY_PATH_GET_VIEW,))
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		_links.append(link)

class AbstractLibraryPathLinkDecorator(object):
	"""
	Create a `LibraryPath` link to our object.
	"""

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping(self, context, result):
		_links = result.setdefault(LINKS, [])
		link = Link(context,
					rel=LIBRARY_PATH_GET_VIEW,
					elements=(LIBRARY_PATH_GET_VIEW,))
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		_links.append(link)

@component.adapter(ITopic)
@interface.implementer(IExternalMappingDecorator)
class _TopicLibraryPathLinkDecorator(AbstractLibraryPathLinkDecorator):
	pass

@component.adapter(IForum)
@interface.implementer(IExternalMappingDecorator)
class _ForumLibraryPathLinkDecorator(AbstractLibraryPathLinkDecorator):
	pass

class _IPad120BundleContentPackagesAdjuster(AbstractAuthenticatedRequestAwareDecorator):
	"""
	there is a class naming issue parsing this data right now which is
	parsing the objects coming from the server with Class:
	NTIContentPackage to an object that isn't a descendant of
	NTIUserData. I have no idea why we didn't see this when we were
	testing. The issue has been in the version all along but I think
	maybe it only gets triggered when we head down certain code paths.
	It seems like the main code path was turning these into NTIIDs
	that were then cross referenced into Library/Main but there is a
	merge/update path that isn't doing that and when we resolve a
	class for this data we find a non NTIUserData and that causes
	things to crash. Since this and all prior versions require
	Library/Main to have all accessible ContentPackages anyway I'm
	hoping you can just conditionally externalize those objects as
	NTIIDs for this specific version of the ipad app.
	"""

	_BAD_UAS = ("NTIFoundation DataLoader NextThought/1.2.0",)

	def _predicate(self, context, result):
		ua = self.request.environ.get('HTTP_USER_AGENT', '')
		if not ua:
			return False

		for bua in self._BAD_UAS:
			if ua.startswith(bua):
				return True

	def _do_decorate_external(self, context, result):
		# Depending on what we're registered on, the result
		# may already contain externalized values or still ContentPackage
		# objects.
		new_packages = []
		for x in result['ContentPackages']:
			ntiid = None
			try:
				ntiid = x.get('NTIID')
			except AttributeError:
				pass
			if not ntiid:
				ntiid = getattr(x, 'ntiid', None) or getattr(x, 'NTIID', None)
			if ntiid:
				new_packages.append(ntiid)
		result['ContentPackages'] = new_packages

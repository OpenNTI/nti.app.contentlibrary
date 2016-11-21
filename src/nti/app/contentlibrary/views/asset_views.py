#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from zope import component

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary.subscribers import can_be_removed
from nti.app.contentlibrary.subscribers import removed_registered
from nti.app.contentlibrary.subscribers import clear_content_package_assets
from nti.app.contentlibrary.subscribers import update_indices_when_content_changes

from nti.app.contentlibrary.utils import yield_content_packages
from nti.app.contentlibrary.utils.common import remove_package_inaccessible_assets

from nti.app.contentlibrary.views import iface_of_thing

from nti.app.contentlibrary.views.sync_views import _AbstractSyncAllLibrariesView

from nti.app.externalization.internalization import read_body_as_external_object

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.common.maps import CaseInsensitiveDict

from nti.common.string import is_true

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES

from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.recorder.record import remove_transaction_history

from nti.site.hostpolicy import get_host_site

from nti.site.interfaces import IHostPolicyFolder

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
TOTAL = StandardExternalFields.TOTAL
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

def _get_package_ntiids(values):
	ntiids = values.get('ntiid') or values.get('ntiids')
	if ntiids and isinstance(ntiids, six.string_types):
		ntiids = ntiids.split()
	return ntiids

def _read_input(request):
	result = CaseInsensitiveDict()
	if request:
		if request.body:
			values = read_body_as_external_object(request)
		else:
			values = request.params
		result.update(values)
	return result

@view_config(context=IDataserverFolder)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='GetPackagePresentationAssets')
class GetPackagePresentationAssetsView(AbstractAuthenticatedView,
									   ModeledContentUploadRequestUtilsMixin):

	def __call__(self):
		params = CaseInsensitiveDict(self.request.params)
		ntiids = _get_package_ntiids(params)
		packages = list(yield_content_packages(ntiids=ntiids))

		catalog = get_library_catalog()
		intids = component.getUtility(IIntIds)

		total = 0
		result = LocatedExternalDict()
		result[ITEMS] = items = {}
		sites = get_component_hierarchy_names()
		for package in packages:
			objects = catalog.search_objects(intids=intids,
											 provided=PACKAGE_CONTAINER_INTERFACES,
											 namespace=package.ntiid,
											 sites=sites)
			items[package.ntiid] = sorted(objects or (),
										  key=lambda x: x.__class__.__name__)
			total += len(items[package.ntiid])

		result[ITEM_COUNT] = result[TOTAL] = total
		return result

@view_config(context=IDataserverFolder)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='ResetPackagePresentationAssets')
class ResetPackagePresentationAssetsView(_AbstractSyncAllLibrariesView):

	def _unit_assets(self, package):
		result = []
		def recur(unit):
			for child in unit.children or ():
				recur(child)
			container = IPresentationAssetContainer(unit)
			for key, value in container.items():
				provided = iface_of_thing(value)
				if provided in PACKAGE_CONTAINER_INTERFACES:
					result.append((key, value, container))
		recur(package)
		return result

	def _do_call(self):
		total = 0
		values = self.readInput()
		ntiids = _get_package_ntiids(values)
		force = is_true(values.get('force'))

		result = LocatedExternalDict()
		items = result[ITEMS] = {}
		for package in yield_content_packages(ntiids):
			seen = set()
			removed = []
			folder = find_interface(package, IHostPolicyFolder, strict=False)
			with current_site(get_host_site(folder.__name__)):
				registry = folder.getSiteManager()
				# remove using catalog
				removed.extend(clear_content_package_assets(package, force=force))
				# remove anything left in containters
				for ntiid, item, container in self._unit_assets(package):
					if can_be_removed(item, force=force):
						container.pop(ntiid, None)
					if ntiid not in seen:
						seen.add(ntiid)
						provided = iface_of_thing(item)
						if removed_registered(provided,
										  	  ntiid,
										  	  force=force,
										   	  registry=registry) is not None:
							removed.append(item)
							remove_transaction_history(item)
				# record output
				items[package.ntiid] = removed
				total += len(removed)
		result[TOTAL] = total
		return result

@view_config(context=IDataserverFolder)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='SyncPackagePresentationAssets')
class SyncPackagePresentationAssetsView(_AbstractSyncAllLibrariesView):

	def _do_call(self):
		values = self.readInput()
		result = LocatedExternalDict()
		items = result[ITEMS] = []
		ntiids = _get_package_ntiids(values)
		for package in yield_content_packages(ntiids):
			folder = find_interface(package, IHostPolicyFolder, strict=False)
			with current_site(get_host_site(folder.__name__)):
				items.append(package.ntiid)
				update_indices_when_content_changes(package)
		return result

@view_config(context=IDataserverFolder)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='RemovePackageInaccessibleAssets')
class RemovePackageInaccessibleAssetsView(AbstractAuthenticatedView,
										  ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		return _read_input(self.request)

	def __call__(self):
		result = LocatedExternalDict()
		endInteraction()
		try:
			result = remove_package_inaccessible_assets()
		finally:
			restoreInteraction()
		return result

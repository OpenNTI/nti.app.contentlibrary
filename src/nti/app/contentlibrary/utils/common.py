#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.interface.adapter import _lookupAll as zopeLookupAll  # Private func

from zope.intid.interfaces import IIntIds

from nti.app.contentlibrary.utils import yield_content_packages

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES
from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import ILegacyPresentationAsset
from nti.contenttypes.presentation.interfaces import IPackagePresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.intid.common import removeIntId

from nti.recorder.record import remove_transaction_history

from nti.site.hostpolicy import get_host_site

from nti.site.interfaces import IHostPolicyFolder

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import unregisterUtility

from nti.traversal.traversal import find_interface

INTID = StandardExternalFields.INTID
ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE

def _package_assets(package):
	result = []
	def recur(unit):
		for child in unit.children or ():
			recur(child)
		container = IPresentationAssetContainer(unit)
		for key, value in container.items():
			provided = iface_of_asset(value)
			if provided in PACKAGE_CONTAINER_INTERFACES:
				result.append((key, value, container))
	recur(package)
	return result

def get_package_site(package):
	folder = find_interface(package, IHostPolicyFolder, strict=False)
	return folder.__name__

def lookup_all_presentation_assets(site_registry):
	result = {}
	required = ()
	order = len(required)
	for registry in site_registry.utilities.ro:  # must keep order
		byorder = registry._adapters
		if order >= len(byorder):
			continue
		components = byorder[order]
		extendors = ALL_PRESENTATION_ASSETS_INTERFACES
		zopeLookupAll(components, required, extendors, result, 0, order)
		break  # break on first
	return result

def remove_package_inaccessible_assets():
	items = []
	seen = set()
	sites = set()
	master = set()
	registered = 0
	result = LocatedExternalDict()
	catalog = get_library_catalog()
	intids = component.getUtility(IIntIds)
	all_packages = tuple(yield_content_packages())

	# clean containers by removing those assets that either
	# don't have an intid or cannot be found in the registry
	for package in all_packages:
		site_name = get_package_site(package)
		registry = get_host_site(site_name).getSiteManager()
		for ntiid, asset, container in _package_assets(package):
			if ILegacyPresentationAsset.providedBy(asset):
				continue
			uid = intids.queryId(asset)
			provided = iface_of_asset(asset)
			if uid is None:
				container.pop(ntiid, None)
				remove_transaction_history(asset)
			elif registry.queryUtility(provided, name=ntiid) is None:
				catalog.unindex(uid)
				removeIntId(asset)
				container.pop(ntiid, None)
				remove_transaction_history(asset)
			else:
				master.add(ntiid)
			sites.add(site_name)

	# always hae sites to examine
	sites = get_component_hierarchy_names() if not all_packages else sites

	# unregister those utilities that cannot be found in the package containers
	for site in sites:
		registry = get_host_site(site).getSiteManager()
		for ntiid, asset in lookup_all_presentation_assets(registry).items():
			if 		ILegacyPresentationAsset.providedBy(asset) \
				or	not IPackagePresentationAsset.providedBy(asset):
				continue
			uid = intids.queryId(asset)
			provided = iface_of_asset(asset)
			if uid is None or ntiid not in master:
				remove_transaction_history(asset)
				unregisterUtility(registry,
								  name=ntiid,
							   	  provided=provided)
				if uid is not None:
					catalog.unindex(uid)
					removeIntId(asset)
				if ntiid not in seen:
					seen.add(ntiid)
					items.append({
						INTID:uid,
						NTIID:ntiid,
						MIMETYPE:asset.mimeType,
					})
			else:
				registered += 1

	# unindex invalid entries in catalog
	references = catalog.get_references(sites=sites,
									 	provided=PACKAGE_CONTAINER_INTERFACES)
	for uid in references or ():
		asset = intids.queryObject(uid)
		if asset is None or not IPresentationAsset.providedBy(asset):
			catalog.unindex(uid)
		else:
			ntiid = asset.ntiid
			provided = iface_of_asset(asset)
			if component.queryUtility(provided, name=ntiid) is None:
				catalog.unindex(uid)
				removeIntId(asset)
				remove_transaction_history(asset)
				if ntiid not in seen:
					seen.add(ntiid)
					items.append({
						INTID:uid,
						NTIID:ntiid,
						MIMETYPE:asset.mimeType,
					})

	items.sort(key=lambda x:x[NTIID])
	result[ITEMS] = items
	result['Sites'] = list(sites)
	result['TotalContainedAssets'] = len(master)
	result['TotalRegisteredAssets'] = registered
	result['Total'] = result['ItemCount'] = len(items)
	return result

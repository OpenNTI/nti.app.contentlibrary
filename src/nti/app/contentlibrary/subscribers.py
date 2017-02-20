#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import simplejson

from zope import component
from zope import interface

from zope.component.hooks import getSite

from zope.intid.interfaces import IIntIds

from zope.lifecycleevent.interfaces import IObjectRemovedEvent

from zope.securitypolicy.rolepermission import AnnotationRolePermissionManager

from ZODB.interfaces import IConnection

from nti.app.contentlibrary.interfaces import IContentBoard
from nti.app.contentlibrary.interfaces import IContentPackageRolePermissionManager

from nti.coremetadata.interfaces import IRecordable

from nti.contentlibrary.indexed_data import get_site_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IGlobalContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageAddedEvent
from nti.contentlibrary.interfaces import IContentPackageSyncResults
from nti.contentlibrary.interfaces import IContentPackageReplacedEvent
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary
from nti.contentlibrary.interfaces import IContentPackageLibraryDidSyncEvent

from nti.contentlibrary.synchronize import ContentPackageSyncResults

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import ILegacyPresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import IContentBackedPresentationAsset

from nti.contenttypes.presentation.utils import create_object_from_external
from nti.contenttypes.presentation.utils import create_ntiaudio_from_external
from nti.contenttypes.presentation.utils import create_ntivideo_from_external
from nti.contenttypes.presentation.utils import create_timelime_from_external
from nti.contenttypes.presentation.utils import create_relatedwork_from_external

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ACT_CONTENT_EDIT
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.externalization.interfaces import StandardExternalFields

from nti.intid.common import addIntId
from nti.intid.common import removeIntId

from nti.ntiids.ntiids import is_valid_ntiid_string

from nti.recorder.record import copy_transaction_history
from nti.recorder.record import remove_transaction_history

from nti.site.interfaces import IHostPolicySiteManager

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility

ITEMS = StandardExternalFields.ITEMS

INDICES = (
	('audio_index.json', INTIAudio, create_ntiaudio_from_external),
	('video_index.json', INTIVideo, create_ntivideo_from_external),
	('timeline_index.json', INTITimeline, create_timelime_from_external),
	('slidedeck_index.json', INTISlideDeck, create_object_from_external),
	('related_content_index.json', INTIRelatedWorkRef, create_relatedwork_from_external)
)

def prepare_json_text(s):
	result = unicode(s, 'utf-8') if isinstance(s, bytes) else s
	return result

def get_connection(registry=None):
	registry = get_site_registry(registry)
	if registry == component.getGlobalSiteManager():
		return None
	else:
		result = IConnection(registry)
		return result

def intid_register(item, intids, connection):
	if connection is not None and intids.queryId(item) is None:
		connection.add(item)
		addIntId(item)
		return True
	return False

def _register_utility(item, provided, ntiid, registry=None):
	if provided.providedBy(item):
		registry = get_site_registry(registry)
		registered = registry.queryUtility(provided, name=ntiid)
		if registered is None:
			assert is_valid_ntiid_string(ntiid), "Invalid NTIID %s" % ntiid
			registerUtility(registry, item, provided=provided, name=ntiid)
			logger.debug("(%s,%s) has been registered", provided.__name__, ntiid)
			return (True, item)
		return (False, registered)
	return (False, None)

def _was_utility_registered(item, item_iface, ntiid, registry=None):
	result, _ = _register_utility(item, item_iface, ntiid, registry=registry)
	return result

def _load_and_register_items(item_iterface,
							 items,
							 registry=None,
							 content_package=None,
							 external_object_creator=create_object_from_external):
	result = []
	registry = get_site_registry(registry)
	for ntiid, data in items.items():
		internal = external_object_creator(data, notify=False)
		if _was_utility_registered(internal, item_iterface, ntiid, registry=registry):
			result.append(internal)
	return result

def _load_and_register_json(item_iterface,
							jtext,
							registry=None,
							content_package=None,
							external_object_creator=create_object_from_external):
	index = simplejson.loads(prepare_json_text(jtext))
	items = index.get(ITEMS) or {}
	result = _load_and_register_items(item_iterface,
									  items,
									  registry=registry,
									  content_package=content_package,
									  external_object_creator=external_object_creator)
	return result

def _canonicalize(items, item_iface, registry):
	recorded = []
	for idx, item in enumerate(items or ()):
		ntiid = item.ntiid
		result, registered = _register_utility(item, item_iface, ntiid, registry)
		if result:
			recorded.append(item)
		else:
			items[idx] = registered  # replaced w/ registered
	return recorded

def _load_and_register_slidedeck_json(jtext,
									  registry=None,
									  content_package=None,
									  object_creator=create_object_from_external):
	result = []
	registry = get_site_registry(registry)
	index = simplejson.loads(prepare_json_text(jtext))
	items = index.get(ITEMS) or {}
	for ntiid, data in items.items():
		internal = object_creator(data, notify=False)
		if 	INTISlide.providedBy(internal) and \
			_was_utility_registered(internal, INTISlide, ntiid, registry):
			result.append(internal)
		elif INTISlideVideo.providedBy(internal) and \
			 _was_utility_registered(internal, INTISlideVideo, ntiid, registry):
			result.append(internal)
		elif INTISlideDeck.providedBy(internal):
			result.extend(_canonicalize(internal.Slides, INTISlide, registry))
			result.extend(_canonicalize(internal.Videos, INTISlideVideo, registry))
			if _was_utility_registered(internal, INTISlideDeck, ntiid, registry):
				result.append(internal)
	return result

def _is_obj_locked(node):
	return IRecordable.providedBy(node) and node.isLocked()

def _can_be_removed(registered, force=False):
	result = registered is not None and (force or not _is_obj_locked(registered))
	return result
can_be_removed = _can_be_removed

def _removed_registered(provided, name, intids=None, registry=None,
						catalog=None, force=False, item=None):
	registry = get_site_registry(registry)
	registered = registry.queryUtility(provided, name=name) if item is None else item
	intids = component.getUtility(IIntIds) if intids is None else intids
	if _can_be_removed(registered, force=force):
		catalog = get_library_catalog() if catalog is None else catalog
		catalog.unindex(registered, intids=intids)
		if not unregisterUtility(registry, provided=provided, name=name):
			logger.error("Could not unregister (%s,%s) during sync, continuing...",
						 provided.__name__, name)
		else:
			logger.debug("(%s,%s) has been unregistered",
						 provided.__name__, name)
		removeIntId(registered)
		registered.__parent__ = None  # ground
	elif registered is not None:
		logger.warn("Object (%s,%s) is locked cannot be removed during sync",
					provided.__name__, name)
		registered = None  # set to None since it was not removed
	return registered
removed_registered = _removed_registered

def _remove_from_registry(namespace=None,
						  provided=None,
						  registry=None,
						  intids=None,
						  catalog=None,
						  force=False,
						  sync_results=None):
	"""
	For our type, get our indexed objects so we can remove from both the
	registry and the index.
	"""
	result = []
	registry = get_site_registry(registry)
	catalog = get_library_catalog() if catalog is None else catalog
	if catalog is None:  # may be None in test mode
		return result
	else:
		sites = get_component_hierarchy_names()
		intids = component.getUtility(IIntIds) if intids is None else intids
		for item in catalog.search_objects(intids=intids,
										   provided=provided,
										   namespace=namespace,
										   sites=sites):
			ntiid = item.ntiid
			removed = _removed_registered(provided,
										  name=ntiid,
										  force=force,
										  intids=intids,
										  catalog=catalog,
										  registry=registry,
										  item=item)
			if removed is not None:
				result.append(removed)
			elif sync_results is not None:
				sync_results.add_asset(ntiid, locked=True)
	return result

def _get_container_tree(container_id):
	library = component.queryUtility(IContentPackageLibrary)
	paths = library.pathToNTIID(container_id)
	results = {path.ntiid for path in paths} if paths else ()
	return results

def _get_file_last_mod_namespace(unit, filename):
	return '%s.%s.LastModified' % (unit.ntiid, filename)

def _index_item(item, content_package, container_id, catalog, intids, connection):
	result = 1
	intid_register(item, intids, connection)
	sites = get_component_hierarchy_names()
	lineage_ntiids = _get_container_tree(container_id)
	lineage_ntiids = None if not lineage_ntiids else lineage_ntiids
	# index item
	catalog.index(item, container_ntiids=lineage_ntiids,
				  namespace=content_package.ntiid, sites=sites)
	# check for slide decks
	if INTISlideDeck.providedBy(item):
		extended = tuple(lineage_ntiids or ()) + (item.ntiid,)
		for slide in item.Slides or ():
			result += 1
			intid_register(slide, intids, connection)
			catalog.index(slide, container_ntiids=extended,
				  		  namespace=content_package.ntiid, sites=sites)

		for video in item.Videos or ():
			result += 1
			intid_register(video, intids, connection)
			catalog.index(video, container_ntiids=extended,
				  		  namespace=content_package.ntiid, sites=sites)

	return result

def _copy_remove_transactions(items, registry=None):
	registry = get_site_registry(registry)
	for item in items or ():
		provided = iface_of_asset(item)
		obj = registry.queryUtility(provided, name=item.ntiid)
		if obj is None:
			remove_transaction_history(item)
		else:
			copy_transaction_history(item, obj)

def _store_asset(content_package, container_id, ntiid, item):
	try:
		unit = content_package[container_id]
	except KeyError:
		unit = content_package

	if item.__parent__ is None:
		item.__parent__ = unit  # set lineage

	container = IPresentationAssetContainer(unit)

	if INTISlideDeck.providedBy(item):
		# CS: 20160114 Slide and SlideVideos are unique for slides,
		# so we can reparent those items
		for slide in item.Slides or ():
			slide.__parent__ = item
			container[slide.ntiid] = slide

		for video in item.Videos or ():
			video.__parent__ = item
			container[video.ntiid] = video

	container[ntiid] = item
	return True

def _index_items(content_package, index, item_iface, catalog, registry,
				 intids=None, connection=None, is_global_manager=False):
	result = 0
	for container_id, indexed_ids in index['Containers'].items():
		for indexed_id in indexed_ids:
			# find asset
			obj = registry.queryUtility(item_iface, name=indexed_id)
			if obj is None and INTISlideDeck.isOrExtends(item_iface):
				obj = 	registry.queryUtility(INTISlide, name=indexed_id) \
					 or	registry.queryUtility(INTISlideVideo, name=indexed_id)

			# if found index it
			if obj is not None:
				_store_asset(content_package,
							 container_id,
							 indexed_id,
							 obj)

				# Only index it if not global
				if not is_global_manager:
					result += _index_item(obj,
										  content_package,
										  container_id,
										  catalog=catalog,
										  intids=intids,
										  connection=connection)
	return result

def _clear_assets_by_interface(content_package, iface, force=False):
	def recur(unit):
		for child in unit.children or ():
			recur(child)
		container = IPresentationAssetContainer(unit)
		for key, value in tuple(container.items()):  # mutating
			provided = iface_of_asset(value)
			registered = component.queryUtility(provided, name=key) if not force else None
			if 	registered is None or \
				(provided.isOrExtends(iface) and can_be_removed(registered, force)):
				del container[key]
	recur(content_package)

def _update_index_when_content_changes(content_package,
									   index_filename,
									   item_iface,
									   object_creator,
									   catalog=None,
									   sync_results=None):
	catalog = get_library_catalog() if catalog is None else catalog
	sibling_key = content_package.does_sibling_entry_exist(index_filename)
	if not sibling_key:
		# Nothing to do
		return

	if sync_results is None:
		sync_results = _new_sync_results(content_package)

	index_text = content_package.read_contents_of_sibling_entry(index_filename)

	if isinstance(index_text, bytes):
		index_text = index_text.decode('utf-8')

	# remove assets with the specified interface
	_clear_assets_by_interface(content_package, item_iface)

	index = simplejson.loads(index_text)
	registry = get_site_registry()
	connection = get_connection(registry)
	intids = component.getUtility(IIntIds)

	removed = _remove_from_registry(namespace=content_package.ntiid,
									provided=item_iface,
									registry=registry,
									catalog=catalog,
									intids=intids,
									sync_results=sync_results)

	# These are structured as follows:
	# {
	#   Items: { ntiid-of_item: data }
	#   Containers: { ntiid-of-content-unit: [list-of-ntiid-of-item ] }
	# }

	# Load our json index files
	# We should not need to register our global, non-persistent catalog.
	added = ()
	if item_iface == INTISlideDeck:
		# Also remove our other slide types
		for provided in (INTISlide, INTISlideVideo):
			_clear_assets_by_interface(content_package, provided)
			removed.extend(_remove_from_registry(namespace=content_package.ntiid,
								  				 provided=provided,
								  				 registry=registry,
								 				 catalog=catalog,
								  			 	 intids=intids,
								  			 	 sync_results=sync_results))

		added = _load_and_register_slidedeck_json(index_text,
										  		  registry=registry,
										 		  object_creator=object_creator,
										 		  content_package=content_package)
	elif object_creator is not None:
		added = _load_and_register_json(item_iface,
										index_text,
										registry=registry,
										content_package=content_package,
										external_object_creator=object_creator)
	registered_count = len(added)
	removed_count = len(removed)

	is_global_manager = bool(registry == component.getGlobalSiteManager())

	# update sync results
	for item in added or ():
		sync_results.add_asset(item, locked=False)
		if is_global_manager:
			interface.alsoProvides(item, ILegacyPresentationAsset)
		interface.alsoProvides(item, IContentBackedPresentationAsset)

	# Index our contained items; ignoring the global library.
	index_item_count = _index_items(content_package,
									index,
									item_iface,
									catalog,
									registry,
									intids=intids,
									connection=connection,
									is_global_manager=is_global_manager)

	if not is_global_manager:
		# keep transaction history
		_copy_remove_transactions(removed, registry=registry)

	logger.info('Finished indexing %s (registered=%s) (indexed=%s) (removed=%s)',
				sibling_key, registered_count, index_item_count, removed_count)

def _clear_assets(content_package, force=False):
	def recur(unit):
		for child in unit.children or ():
			recur(child)
		container = IPresentationAssetContainer(unit)
		if force:
			container.clear()
		else:
			for key, value in tuple(container.items()):  # mutating
				if can_be_removed(value, force):
					del container[key]

	recur(content_package)
clear_package_assets = _clear_assets

def _clear_last_modified(content_package, catalog=None):
	catalog = get_library_catalog() if catalog is None else catalog
	if catalog is None:
		# XXX: Seen this in tests. It means our configuration is
		# screwed up.
		# XXX: Why doesn't get_library_catalog() use getComponent and raise
		# the lookup error? Better to fail fast.
		logger.warning("Failed to find catalog")
		return

	for name, _, _ in INDICES:
		namespace = _get_file_last_mod_namespace(content_package, name)
		catalog.remove_last_modified(namespace)
clear_namespace_last_modified = _clear_last_modified

# update events

def _new_sync_results(content_package):
	result = ContentPackageSyncResults(Site=getattr(getSite(), '__name__', None),
									   ContentPackageNTIID=content_package.ntiid)
	return result

def _get_sync_results(content_package, event):
	all_results = getattr(event, "results", None)
	if not all_results or not IContentPackageSyncResults.providedBy(all_results[-1]):
		result = _new_sync_results(content_package)
		if all_results is not None:
			all_results.append(result)
	elif all_results[-1].ContentPackageNTIID != content_package.ntiid:
		result = _new_sync_results(content_package)
		all_results.append(result)
	else:
		result = all_results[-1]
	return result

def update_indices_when_content_changes(content_package, sync_results=None):
	if sync_results is None:
		sync_results = _new_sync_results(content_package)

	for name, item_iface, func in INDICES:
		_update_index_when_content_changes(content_package,
										   index_filename=name,
										   object_creator=func,
										   item_iface=item_iface,
										   sync_results=sync_results)
	return sync_results

def _get_locked_objects(objects):
	for item in objects:
		if IRecordable.providedBy(item) and item.isLocked():
			yield item

def _update_container(old_unit, new_unit, new_children_dict, new_package=None):
	"""
	Move all locked objects from our old container to our new updating lineage as we go.
	"""
	new_package = new_package if new_package is not None else new_unit
	old_container = IPresentationAssetContainer(old_unit)
	new_container = IPresentationAssetContainer(new_unit)
	for item in _get_locked_objects(old_container.values()):
		# We always want to update our lineage to our new unit.
		item.__parent__ = new_unit
		new_container[item.ntiid] = item
	# Now recursively on children.
	for old_child in old_unit.children:
		# Get the corresponding new unit from our dict, if available. If non-existent,
		# use the content package to make sure we keep any created items.
		new_child = new_children_dict.get(old_child.ntiid, new_package)
		_update_container(old_child, new_child, new_children_dict, new_package)

def _get_children_dict(new_package):
	accum = dict()
	def _recur(obj, accum):
		accum[obj.ntiid] = obj
		for child in obj.children:
			_recur(child, accum)
	_recur(new_package, accum)
	return accum

@component.adapter(IContentPackage, IContentPackageReplacedEvent)
def _update_indices_when_content_changes(content_package, event):
	sync_results = _get_sync_results(content_package, event)
	update_indices_when_content_changes(content_package, sync_results)
	if IContentPackageReplacedEvent.providedBy(event):
		new_children_dict = _get_children_dict(content_package)
		_update_container(event.original, content_package, new_children_dict)

# clear events

def _clear_when_removed(content_package, force=True, process_global=False):
	"""
	Because we don't know where the data is stored, when an
	content package is removed we need to clear its data.
	"""
	result = []
	catalog = get_library_catalog()
	_clear_assets(content_package, force)

	# Remove indexes for our contained items; ignoring the global library.
	# Not sure if this will work when we have shared items
	# across multiple content packages.
	if not process_global and IGlobalContentPackage.providedBy(content_package):
		return result
	_clear_last_modified(content_package, catalog)

	for _, item_iface, _ in INDICES:
		removed = _remove_from_registry(namespace=content_package.ntiid,
							  			provided=item_iface,
							  			catalog=catalog,
							  			force=force)
		result.extend(removed)

	removed = _remove_from_registry(namespace=content_package.ntiid,
						  			provided=INTISlide,
						  			catalog=catalog,
						  			force=force)
	result.extend(removed)

	removed = _remove_from_registry(namespace=content_package.ntiid,
						  			provided=INTISlideVideo,
						 			catalog=catalog,
						 			force=force)
	result.extend(removed)

	for item in result:
		remove_transaction_history(item)

	logger.info('Removed indexes for content package %s (removed=%s)',
				content_package, len(result))
	return result
clear_content_package_assets = _clear_when_removed

@component.adapter(IContentPackage, IObjectRemovedEvent)
def _clear_index_when_content_removed(content_package, event):
	return _clear_when_removed(content_package)

# role events

@component.adapter(IContentPackage)
@interface.implementer(IContentPackageRolePermissionManager)
class ContentPackageRolePermissionManager(AnnotationRolePermissionManager):

	def initialize(self):
		if not self.map or not self.map._byrow:
			# Initialize with perms for our global content admin.
			for perm in (ACT_READ, ACT_CONTENT_EDIT, ACT_UPDATE):
				self.grantPermissionToRole(perm.id, ROLE_CONTENT_ADMIN.id)

def _initialize_content_package_roles(package):
	package_role_manager = IContentPackageRolePermissionManager(package)
	if package_role_manager is not None:
		package_role_manager.initialize()

@component.adapter(IContentPackage, IContentPackageAddedEvent)
def _initialize_package_roles(content_package, event):
	_initialize_content_package_roles(content_package)

@component.adapter(IContentPackage, IContentPackageReplacedEvent)
def _update_package_roles(content_package, event):
	_initialize_content_package_roles(content_package)

# forum events

@component.adapter(IContentPackageLibrary, IContentPackageLibraryDidSyncEvent)
def _on_content_pacakge_library_synced(library, event):
	site = library.__parent__
	if IHostPolicySiteManager.providedBy(site):
		bundle_library = site.getUtility(IContentPackageBundleLibrary)
		for bundle in bundle_library.values():
			board = IContentBoard(bundle, None)
			if board is not None:
				board.createDefaultForum()

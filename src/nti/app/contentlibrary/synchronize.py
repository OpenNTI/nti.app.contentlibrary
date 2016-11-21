#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import gc
import time

import gevent

from zope import component

from zope.event import notify

from zope.traversing.interfaces import IEtcNamespace

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import ISyncableContentPackageLibrary
from nti.contentlibrary.interfaces import AllContentPackageLibrariesDidSyncEvent
from nti.contentlibrary.interfaces import AllContentPackageLibrariesWillSyncEvent

from nti.contentlibrary.subscribers import install_site_content_library

from nti.contentlibrary.synchronize import SynchronizationParams
from nti.contentlibrary.synchronize import SynchronizationResults

from nti.site.hostpolicy import run_job_in_all_host_sites
from nti.site.hostpolicy import synchronize_host_policies

def _do_synchronize(method, sleep=None, site=None, ntiids=(), allowRemoval=True):
	results = SynchronizationResults()
	params = SynchronizationParams(ntiids=ntiids or (), allowRemoval=allowRemoval)

	# notify
	notify(AllContentPackageLibrariesWillSyncEvent(params))

	# First, synchronize the policies, make sure everything is all nice and installed.
	synchronize_host_policies()

	# Next, the libraries.
	# NOTE: We do not synchronize the global library; it is not
	# expected to be persistent and is not shared across
	# instances, so synchronizing it now will actually cause
	# things to be /out/ of sync.
	# We just keep track of it to make sure we don't.
	seen = set()
	seen.add(None)
	global_lib = component.getGlobalSiteManager().queryUtility(IContentPackageLibrary)
	seen.add(global_lib)

	def sync_site_library():
		# Mostly for testing, if we started up with a different library
		# that could not provide valid site libraries, install
		# one if we can get there now.
		site_manager = component.getSiteManager()
		site_name = site_manager.__parent__.__name__
		site_lib = install_site_content_library(site_manager)
		if site_lib in seen:
			return

		seen.add(site_lib)
		if site and site_name != site:
			return

		if sleep:
			gevent.sleep()

		syncer = ISyncableContentPackageLibrary(site_lib, None)
		if syncer is not None:
			logger.info("Sync library %s", site_lib)
			executable = getattr(site_lib, method)
			executable(params, results)
			return True
		return False

	# sync
	run_job_in_all_host_sites(sync_site_library)

	# mark sync time
	hostsites = component.getUtility(IEtcNamespace, name='hostsites')
	hostsites.lastSynchronized = time.time()

	# clean up
	gc.collect()

	# notify
	notify(AllContentPackageLibrariesDidSyncEvent(params, results))
	return params, results

def syncContentPackages(sleep=None, allowRemoval=True, site=None, ntiids=()):
	result = _do_synchronize("syncContentPackages", sleep, site, ntiids, allowRemoval)
	return result
synchronize = syncContentPackages

def addRemoveContentPackages(sleep=None, site=None):
	result = _do_synchronize("addRemoveContentPackages", sleep, site)
	return result

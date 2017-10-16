#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import gc
import time

import gevent

from zope import component

from zope.event import notify as zope_notify

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

logger = __import__('logging').getLogger(__name__)


def _do_synchronize(sleep=None, site=None, ntiids=(), allowRemoval=True, notify=True):
    results = SynchronizationResults()
    params = SynchronizationParams(ntiids=ntiids or (),
                                   allowRemoval=allowRemoval)

    # send event
    zope_notify(AllContentPackageLibrariesWillSyncEvent(params))

    # First, synchronize the policies, make sure everything is all nice and
    # installed.
    synchronize_host_policies()

    # Next, the libraries.
    # NOTE: We do not synchronize the global library; it is not
    # expected to be persistent and is not shared across
    # instances, so synchronizing it now will actually cause
    # things to be /out/ of sync.
    # We just keep track of it to make sure we don't.
    seen = set()
    seen.add(None)
    gsm = component.getGlobalSiteManager()
    global_lib = gsm.queryUtility(IContentPackageLibrary)
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
            gevent.sleep(sleep)

        syncer = ISyncableContentPackageLibrary(site_lib, None)
        if syncer is not None:
            logger.info("Sync library %s", site_lib)
            site_lib.syncContentPackages(params, results, notify)
            return True
        return False

    # sync
    run_job_in_all_host_sites(sync_site_library)

    # mark sync time
    hostsites = component.getUtility(IEtcNamespace, name='hostsites')
    hostsites.lastSynchronized = time.time()

    # clean up
    gc.collect()

    # send event
    zope_notify(AllContentPackageLibrariesDidSyncEvent(params, results))
    return params, results


def syncContentPackages(sleep=None, allowRemoval=True, site=None, ntiids=(), notify=True):
    return _do_synchronize(sleep, site, ntiids, allowRemoval, notify)
synchronize = sync_content_packages = syncContentPackages

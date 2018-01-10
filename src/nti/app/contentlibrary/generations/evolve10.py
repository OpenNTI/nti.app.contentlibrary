#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IEditableContentPackage

from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer
from nti.contenttypes.presentation.interfaces import IContentBackedPresentationAsset

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

generation = 10

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warn("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
        return None


def process_site(current_site, intids,  seen):
    with site(current_site):
        library = component.queryUtility(IContentPackageLibrary)
        if library is None:
            return

        def _recur(unit):
            container = IPresentationAssetContainer(unit)
            for asset in container.values():
                if not IContentBackedPresentationAsset.providedBy(asset):
                    interface.alsoProvides(asset, IContentBackedPresentationAsset)
                    logger.info("Marking asset %s", asset.ntiid)
            for child in unit.children or ():
                _recur(child)

        for package in library.contentPackages or ():
            doc_id = intids.queryId(package)
            if doc_id is None or doc_id in seen:
                continue
            if not IEditableContentPackage.providedBy(package):
                _recur(package)
            seen.add(doc_id)


def process_sites(intids):
    seen = set()
    for current_site in get_all_host_sites():
        process_site(current_site, intids, seen)
    return seen


def do_evolve(context, generation=generation):  # pylint: disable=redefined-outer-name
    setHooks()
    conn = context.connection
    root = conn.root()
    ds_folder = root['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    with site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
               "Hooks not installed?"

        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)

        library = component.queryUtility(IContentPackageLibrary)
        if library is not None:
            library.syncContentPackages()
        process_sites(intids)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Content library evolution %s done.',
                generation)


def evolve(context):
    """
    Evolve to gen 10 by marking assets in unit as content backed
    """
    do_evolve(context)

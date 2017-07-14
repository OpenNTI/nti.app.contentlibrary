#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 9

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from zope.location import locate

from nti.app.contentlibrary.generations import evolve8

from nti.contentlibrary.index import IX_RESTRICTED_ACCESS
from nti.contentlibrary.index import install_contentbundle_catalog
from nti.contentlibrary.index import ContentBundleRestrictedAccessIndex

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver


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


def do_evolve(context, generation=generation):
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

        catalog = install_contentbundle_catalog(ds_folder, intids)
        if IX_RESTRICTED_ACCESS not in catalog:
            index = ContentBundleRestrictedAccessIndex(family=intids.family)
            locate(index, catalog, IX_RESTRICTED_ACCESS)
            catalog[IX_RESTRICTED_ACCESS] = index
            intids.register(index)
        # index sites
        seen = evolve8.process_sites(catalog, intids)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Content library evolution %s done. %s bundle(s) indexed', 
                generation, len(seen))


def evolve(context):
    """
    Evolve to gen 9 by adding the restricted access index
    """
    do_evolve(context)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 8

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.index import install_contentbundle_catalog

from nti.contentlibrary.interfaces import IContentPackageBundleLibrary

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warn("sing dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
        return None


def index_site(current_site, catalog, intids,  seen):
    with site(current_site):
        library = component.queryUtility(IContentPackageBundleLibrary)
        if library is None:
            return
        for bundle in library.getBundles() or ():
            doc_id = intids.queryId(intids)
            if doc_id is None or doc_id in seen:
                continue
            catalog.index_doc(doc_id, bundle)


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

        seen = set()
        catalog = install_contentbundle_catalog(ds_folder, intids)
        for current_site in get_all_host_sites():
            index_site(current_site, catalog, intids, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Content library evolution %s done.', generation)


def evolve(context):
    """
    Evolve to gen 8 by installing the content bundle catalog
    """
    do_evolve(context)

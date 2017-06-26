#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 6

from zope import component
from zope import interface

from zope.catalog.interfaces import ICatalog

from zope.component.hooks import site
from zope.component.hooks import setHooks

from nti.contentlibrary.index import CATALOG_INDEX_NAME

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

OLD_REG_NAME = '++etc++contentlibrary.catalog'


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
        catalog = lsm.queryUtility(ICatalog, name=OLD_REG_NAME)
        if catalog is not None:
            lsm.unregisterUtility(provided=ICatalog, name=OLD_REG_NAME)
            lsm.registerUtility(catalog, provided=ICatalog,
                                name=CATALOG_INDEX_NAME)
            catalog.__name__ = CATALOG_INDEX_NAME

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Content library evolution %s done.', generation)


def evolve(context):
    """
    Evolve to gen 6 by changing the registration name of the library catalog
    """
    do_evolve(context)

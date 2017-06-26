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

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.index import install_library_catalog

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

IX_CREATEDTIME = 'createdTime'
IX_LASTMODIFIED = 'lastModified'

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
        assert  component.getSiteManager() == ds_folder.getSiteManager(), \
                "Hooks not installed?"

        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)

        catalog = install_library_catalog(ds_folder, intids)
        for name in (IX_CREATEDTIME, IX_LASTMODIFIED):
            if name in catalog:
                index = catalog[name]
                index.index.clear()
                intids.unregister(index)
                del catalog[name]
                index.__parent__ = None

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Content library evolution %s done.', generation)


def evolve(context):
    """
    Evolve to gen 6 by removing lastMod, createdTime indexes from library catalog
    """
    do_evolve(context)

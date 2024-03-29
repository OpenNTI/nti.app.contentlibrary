#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 2

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from BTrees.OOBTree import OOBTree

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites


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


def do_evolve(context):
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

        for current_site in get_all_host_sites():
            with site(current_site):
                library = component.queryUtility(IContentPackageLibrary)
                if library is None:
                    continue
                last_modified = 0
                contentPackages = OOBTree()
                contentUnitsByNTIID = OOBTree()

                for package in library._contentPackages or ():
                    contentPackages[package.ntiid] = package
                    index_lm = getattr(package, 'index_last_modified', None)
                    last_modified = max(last_modified, index_lm or -1)

                def _recur(unit):
                    contentUnitsByNTIID[unit.ntiid] = unit
                    for child in unit.children:
                        _recur(child)
                for package in library._contentPackages or ():
                    _recur(package)

                library._last_modified = last_modified
                library._contentPackages = contentPackages
                library._contentUnitsByNTIID = contentUnitsByNTIID

                for name in ('_content_packages_by_ntiid', '_content_units_by_ntiid'):
                    try:
                        delattr(library, name)
                    except AttributeError:
                        pass

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Content library evolution %s done.', generation)


def evolve(context):
    """
    Evolve to gen 2 by migrating content pacakge storage in libraries
    """
    do_evolve(context)

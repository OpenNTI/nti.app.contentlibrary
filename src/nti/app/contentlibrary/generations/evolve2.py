#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
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
            logger.warn("sing dataserver without a proper ISiteManager.")
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
        assert  component.getSiteManager() == ds_folder.getSiteManager(), \
            "Hooks not installed?"

        for current_site in get_all_host_sites():
            with site(current_site):
                library = component.queryUtility(IContentPackageLibrary)
                if library is None:
                    continue
                contentPackages = OOBTree()
                contentUnitsByNTIID = OOBTree()
                for package in library.contentPackages or ():
                    contentPackages[package.ntiid] = package

                def _recur(unit):
                    contentUnitsByNTIID[unit.ntiid] = unit
                    for child in unit.children:
                        _recur(child)
                for package in library.contentPackages or ():
                    _recur(package)

                library._contentPackages = contentPackages
                library._contentUnitsByNTIID = contentUnitsByNTIID

                for name in ('_content_packages_by_ntiid', '_content_units_by_ntiid'):
                    try:
                        delattr(library, name)
                    except AttributeError:
                        pass
    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Dataserver evolution %s done.', generation)


def evolve(context):
    """
    Evolve to gen 2 by installing the new library asset catalog.
    """
    # do_evolve(context) DON"T Install YET

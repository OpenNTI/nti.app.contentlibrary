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
            logger.warn("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
        return None


def index_site(current_site, catalog, intids,  seen):
    with site(current_site):
        library = component.queryUtility(IContentPackageBundleLibrary)
        bundles = library.getBundles() if library else ()
        for bundle in bundles:
            doc_id = intids.queryId(bundle)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)
            catalog.index_doc(doc_id, bundle)


def process_sites(catalog, intids):
    seen = set()
    for current_site in get_all_host_sites():
        index_site(current_site, catalog, intids, seen)
    return seen

def evolve(context):
    pass

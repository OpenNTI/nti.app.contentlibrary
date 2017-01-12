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

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.indexed_data.catalog import install_library_catalog

def do_evolve(context):
    setHooks()
    conn = context.connection
    root = conn.root()
    ds_folder = root['nti.dataserver']

    with site(ds_folder):
        assert  component.getSiteManager() == ds_folder.getSiteManager(), \
            "Hooks not installed?"

        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)

        install_library_catalog(ds_folder, intids)
        logger.info('Dataserver evolution %s done.', generation)


def evolve(context):
    """
    Evolve to gen 2 by installing the new library asset catalog.
    """
    # do_evolve(context) DON"T Install YET

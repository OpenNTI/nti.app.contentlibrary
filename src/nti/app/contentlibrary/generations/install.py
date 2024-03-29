#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from zope.generations.generations import SchemaManager as BaseSchemaManager

from zope.generations.interfaces import IInstallableSchemaManager

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.index import install_library_catalog
from nti.contentlibrary.index import install_contentbundle_catalog

from nti.contentlibrary.indexed_data.index import install_container_catalog

generation = 10

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IInstallableSchemaManager)
class _SchemaManager(BaseSchemaManager):
    """
    A schema manager that we can register as a utility in ZCML.
    """

    def __init__(self):
        super(_SchemaManager, self).__init__(
                generation=generation,
                minimum_generation=generation,
                package_name='nti.app.contentlibrary.generations')

    def install(self, context):
        evolve(context)


def evolve(context):
    conn = context.connection
    root = conn.root()
    dataserver_folder = root['nti.dataserver']
    lsm = dataserver_folder.getSiteManager()
    intids = lsm.getUtility(IIntIds)
    install_library_catalog(dataserver_folder, intids)
    install_container_catalog(dataserver_folder, intids)
    install_contentbundle_catalog(dataserver_folder, intids)

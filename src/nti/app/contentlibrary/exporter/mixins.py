#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from six import StringIO

import simplejson

from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields

from nti.mimetype.externalization import decorateMimeType

from nti.ntiids.ntiids import hash_ntiid

ITEMS = StandardExternalFields.ITEMS
MIMETYPE = StandardExternalFields.MIMETYPE


class AssetExporterMixin(object):

    def __init__(self, *args, **kwargs):
        AssetExporterMixin.__init__(self, *args, **kwargs)

    def dump(self, ext_obj):
        source = StringIO()
        simplejson.dump(ext_obj, source, indent='\t', sort_keys=True)
        source.seek(0)
        return source

    def do_export(self, package, provided=IPresentationAsset, backup=True, salt=None):

        assets = dict()
        containers = dict()

        def _recur(unit):
            container = IPresentationAssetContainer(unit, None)
            if container:
                ntiid = unit.ntiid
                unit_ntiid = ntiid if backup else hash_ntiid(ntiid, salt)
                containers.setdefault(unit.ntiid, [])
                for item in container.assets():
                    ntiid = item.ntiid
                    item_ntiid = ntiid if backup else hash_ntiid(ntiid, salt)
                    if provided.providedBy(item):
                        if item_ntiid not in assets:
                            assets[item_ntiid] = item
                        containers[unit_ntiid].append(item_ntiid)
            for child in unit.children or ():
                _recur(child)

        _recur(package)

        items = dict()
        for asset in assets.values():
            ext_obj = to_external_object(asset,
                                         name="exporter",
                                         decorate=False)
            decorateMimeType(asset, ext_obj)
            ext_obj['mimeType'] = ext_obj[MIMETYPE]
            items[asset.ntiid] = ext_obj

        result = dict()
        if items:
            result[ITEMS] = items
            result['Containers'] = containers
        return result

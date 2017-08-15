#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from six import StringIO
from collections import Mapping

import simplejson

from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import StandardInternalFields

from nti.mimetype.externalization import decorateMimeType

from nti.ntiids.ntiids import hash_ntiid

OID = StandardExternalFields.OID
ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE
CREATED_TIME = StandardExternalFields.CREATED_TIME
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

INTERNAL_NTIID = StandardInternalFields.NTIID


class AssetExporterMixin(object):

    def __init__(self, *args, **kwargs):
        super(AssetExporterMixin, self).__init__(*args, **kwargs)

    def dump(self, ext_obj):
        source = StringIO()
        simplejson.dump(ext_obj, source, indent='\t', sort_keys=True)
        source.seek(0)
        return source

    def _prunner(self, ext_obj, backup=True, salt=None):
        if isinstance(ext_obj, Mapping):
            if not backup:
                for name in (OID, CREATED_TIME, LAST_MODIFIED):
                    ext_obj.pop(name, None)
            else:
                ext_obj.pop(OID, None)
            for name, value in list(ext_obj.items()):
                if not backup and value and name in (NTIID, INTERNAL_NTIID):
                    ext_obj[name] = hash_ntiid(value, salt)
                self._prunner(value, backup, salt)
        if isinstance(ext_obj, (set, tuple, list)):
            for value in ext_obj:
                self._prunner(value, backup, salt)

    def do_export(self, package, provided=IPresentationAsset, backup=True, salt=None):

        assets = dict()
        containers = dict()

        def _recur(unit):
            container = IPresentationAssetContainer(unit, None)
            if container:
                ntiid = unit.ntiid
                unit_ntiid = ntiid if backup else hash_ntiid(ntiid, salt)
                containers.setdefault(unit_ntiid, [])
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
            ntiid = asset.ntiid
            asset_ntiid = ntiid if backup else hash_ntiid(ntiid, salt)
            ext_obj = to_external_object(asset,
                                         name="exporter",
                                         decorate=False)
            self._prunner(ext_obj, backup, salt)
            # hash ntiid
            decorateMimeType(asset, ext_obj)
            ext_obj['mimeType'] = ext_obj[MIMETYPE]
            items[asset_ntiid] = ext_obj

        result = dict()
        if items:
            result[ITEMS] = items
            result['Containers'] = containers
        return result

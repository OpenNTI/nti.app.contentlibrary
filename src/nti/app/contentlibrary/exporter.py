#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from collections import Mapping

import simplejson

from six.moves import cStringIO

from zope import component
from zope import interface

from nti.cabinet.filer import read_source

from nti.contentlibrary.interfaces import IEditableContentPackage
from nti.contentlibrary.interfaces import IContentPackageExporterDecorator

from nti.contenttypes.presentation.interfaces import INTIVideo
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

CONTAINERS = 'Containers'

logger = __import__('logging').getLogger(__name__)


def prepare_json_text(s):
    result = s.decode('utf-8') if isinstance(s, bytes) else s
    return result


class AssetExporterMixin(object):

    def __init__(self, *args, **kwargs):  # pylint: disable=useless-super-delegation
        super(AssetExporterMixin, self).__init__(*args, **kwargs)

    @classmethod
    def dump(cls, ext_obj):
        source = cStringIO()
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

    @classmethod
    def merge(cls, result, source):
        data = read_source(source)
        if data:
            if not isinstance(data, Mapping):
                data = prepare_json_text(data)
                external = simplejson.loads(data)
            else:
                external = data

            items = result.get(ITEMS, None) or dict()
            source_items = external.get(ITEMS) or ()
            for ntiid in source_items:
                if not ntiid in items:
                    items[ntiid] = source_items[ntiid]

            containers = result.get(CONTAINERS, None) or dict()
            source_containers = external.get(CONTAINERS) or ()
            for ntiid in source_containers:
                a = set(source_containers[ntiid] or ())
                b = set(containers.get(ntiid) or ())
                b.update(a)
                containers[ntiid] = sorted(b)

            result[ITEMS] = items
            result[CONTAINERS] = containers

        return result

    def do_export(self, package, provided=IPresentationAsset, backup=True, salt=None):

        assets = dict()
        containers = dict()

        def _recur(unit):
            container = IPresentationAssetContainer(unit, None)
            if container:
                ntiid = unit.ntiid
                unit_ntiid = ntiid if backup else hash_ntiid(ntiid, salt)
                containers.setdefault(unit_ntiid, [])
                # pylint: disable=too-many-function-args
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
            decorateMimeType(asset, ext_obj)
            ext_obj['mimeType'] = ext_obj[MIMETYPE]
            items[asset_ntiid] = ext_obj

        result = dict()
        if items:
            result[ITEMS] = items
            result['Containers'] = containers
        return result


@component.adapter(IEditableContentPackage)
@interface.implementer(IContentPackageExporterDecorator)
class _EditableContentPackageExporterDecorator(AssetExporterMixin):

    VIDEO_INDEX = 'video_index.json'

    def __init__(self, *args):  # pylint: disable=super-init-not-called
        pass

    def export_videos(self, package, external, backup=True, salt=None):
        result = self.do_export(package, INTIVideo, backup, salt)
        if result:
            external[self.VIDEO_INDEX] = result

    def decorateExternalObject(self, package, external, backup=True, salt=None, unused_filer=None):
        self.export_videos(package, external, backup, salt)

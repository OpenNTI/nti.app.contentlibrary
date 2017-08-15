#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.app.contentlibrary.exporter.mixins import AssetExporterMixin

from nti.contentlibrary.interfaces import IEditableContentPackage
from nti.contentlibrary.interfaces import IContentPackageExporterDecorator

from nti.contenttypes.presentation.interfaces import INTIVideo


@component.adapter(IEditableContentPackage)
@interface.implementer(IContentPackageExporterDecorator)
class _EditableContentPackageExporterDecorator(AssetExporterMixin):

    VIDEO_INDEX = 'video_index.json'

    def __init__(self, *args):
        pass

    def export_videos(self, package, external, backup=True, salt=None, filer=None):
        result = self.do_export(package, INTIVideo, backup, salt)
        if not result:
            return
        if filer is not None:
            bucket = getattr(filer, 'default_bucket', None)
            if filer.contains(self.VIDEO_INDEX, bucket):
                source = filer.get(self.VIDEO_INDEX, bucket)
                result = self.merge(result, source)
            source = self.dump(result)
            filer.save(self.VIDEO_INDEX, source,
                       contentType="application/json", overwrite=True)
        else:
            external[self.VIDEO_INDEX] = result

    def decorateExternalObject(self, package, external, backup=True, salt=None, filer=None):
        self.export_videos(package, external, backup, salt, filer)

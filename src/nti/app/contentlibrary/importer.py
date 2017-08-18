#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from collections import Mapping

import simplejson

from zope import component
from zope import interface

from nti.app.contentlibrary.synchronize.subscribers import update_index_when_content_changes

from nti.cabinet.filer import read_source

from nti.cabinet.mixins import SourceFile
from nti.cabinet.mixins import SourceBucket

from nti.contentlibrary.interfaces import IEditableContentPackage
from nti.contentlibrary.interfaces import IContentPackageImporterUpdater


def prepare_json_text(s):
    result = s.decode('utf-8') if isinstance(s, bytes) else s
    return result


class FakeSource(SourceFile):

    def __init__(self, index_filename, data):
        SourceFile.__init__(self, name=index_filename, data=data)


class FakeBucket(SourceBucket):

    def __init__(self, index_filename, data):
        SourceBucket.__init__(self, "bucket", None)
        self.data = data
        self.index_filename = index_filename

    def getChildNamed(self, name):
        if name == self.index_filename:
            return FakeSource(self.index_filename, self.data)
        return None

    def enumerateChildren(self):
        return (self.getChildNamed(self.index_filename),)


class AssetImporterMixin(object):

    def __init__(self, *args, **kwargs):
        super(AssetImporterMixin, self).__init__(*args, **kwargs)

    def do_import(self, package, source, index_filename):
        if not isinstance(source, Mapping):
            source = prepare_json_text(read_source(source))
            source = simplejson.loads(source)
        buckets = (FakeBucket(index_filename, source),)
        return update_index_when_content_changes(package, index_filename, 
                                                 buckets=buckets, force=True)


@component.adapter(IEditableContentPackage)
@interface.implementer(IContentPackageImporterUpdater)
class _EditableContentPackageImporterUpdater(AssetImporterMixin):

    VIDEO_INDEX = 'video_index.json'

    def __init__(self, *args):
        pass

    def import_videos(self, package, external):
        data = external.get(self.VIDEO_INDEX, None)
        if data:
            self.do_import(package, data, self.VIDEO_INDEX)

    def updateFromExternalObject(self, package, external, *unused_args, **unused_kwargs):
        self.import_videos(package, external)

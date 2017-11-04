#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import six
import shutil
import tempfile

import simplejson

from xml.dom import minidom

from pyramid import httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from nti.app.contentlibrary import MessageFactory as _

from nti.app.externalization.error import raise_json_error

from nti.base._compat import text_

from nti.contentlibrary import CONTENT_PACKAGE_BUNDLES

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contentlibrary.utils import is_valid_presentation_assets_source

from nti.namedfile.file import safe_filename


def bundle_meta_info(bundle):
    result = {
        "title": bundle.title,
        "ntiid": bundle.ntiid,
        "ContentPackages": [x.ntiid for x in bundle.ContentPackages or ()]
    }
    return simplejson.dumps(result, indent='\t')


def dc_metadata(bundle):
    DOMimpl = minidom.getDOMImplementation()
    xmldoc = DOMimpl.createDocument(None, "metadata", None)
    doc_root = xmldoc.documentElement
    doc_root.setAttributeNS(None, "xmlns:dc",
                            "http://purl.org/dc/elements/1.1/")
    # add creators
    creators = set(bundle.creators or ())
    creators.union({getattr(bundle, 'creator', None)})
    for name in creators:
        if not name:
            continue
        node = xmldoc.createElement("dc:creator")
        node.appendChild(xmldoc.createTextNode(name))
        doc_root.appendChild(node)
    # add title
    if bundle.title:
        node = xmldoc.createElement("dc:title")
        node.appendChild(xmldoc.createTextNode(bundle.title))
        doc_root.appendChild(node)
    return xmldoc.toprettyxml(encoding="UTF-8")


def save_presentation_assets_to_disk(assets, target):
    if     not isinstance(assets, six.string_types) \
        or not os.path.isdir(assets):
        assets = is_valid_presentation_assets_source(assets)

    if not assets:
        raise_json_error(get_current_request(),
                         hexc.HTTPUnprocessableEntity,
                         {
                             'message': _(u"Invalid presentation assets source."),
                             'code': 'LibraryNotAvailable',
                         },
                         None)
            
    if not os.path.isdir(assets):
        raise_json_error(get_current_request(),
                         hexc.HTTPUnprocessableEntity,
                         {
                             'message': _(u"Invalid presentation assets directory."),
                             'code': 'LibraryNotAvailable',
                         },
                         None)

    path = os.path.join(target, 'presentation-assets')
    shutil.move(assets, path)
    return path
        

def save_bundle_to_disk(bundle, target, assets=None, name=None):
    name = name or safe_filename(bundle.title)
    tmpdir = os.path.join(tempfile.mkdtemp(), name)
    os.makedirs(tmpdir)
    # save bundle meta info
    path = os.path.join(tmpdir, "bundle_meta_info.json")
    with open(path, "wb") as fp:
        fp.write(bundle_meta_info(bundle))
    # save dc_metadata
    path = os.path.join(tmpdir, "dc_metadata.xml")
    with open(path, "wb") as fp:
        fp.write(dc_metadata(bundle))
    # save assets
    if assets is not None:
        save_presentation_assets_to_disk(assets, tmpdir)
    # save to destination
    absolute_path = getattr(target, 'absolute_path', None) or target
    dest_path = os.path.join(absolute_path, CONTENT_PACKAGE_BUNDLES, name)
    if not os.path.exists(dest_path):
        os.makedirs(dest_path)
    for name in os.listdir(tmpdir):
        source = os.path.join(tmpdir, name)
        target = os.path.join(dest_path, name)
        if os.path.exists(target) and os.path.isdir(target):
            shutil.rmtree(target)
        shutil.move(source, target)
    # clean up
    shutil.rmtree(tmpdir, ignore_errors=True)
    return dest_path


def save_bundle(bundle, target, assets=None, name=None):
    if IFilesystemBucket.providedBy(target):
        name = text_(name or safe_filename(bundle.title))
        path = save_bundle_to_disk(bundle, target, assets, name)
        bucket = FilesystemBucket(name=name)
        bucket.absolute_path = path
        bundle.root = bucket
        return bucket

    raise_json_error(get_current_request(),
                     hexc.HTTPUnprocessableEntity,
                     {
                         'message': _(u"Only saving to file system is supported."),
                     },
                     None)

def save_presentation_assets(assets, target):
    if IFilesystemBucket.providedBy(target):
        path = save_presentation_assets_to_disk(assets, target)
        bucket = FilesystemBucket(name=u'presentation-assets')
        bucket.absolute_path = path
        return bucket

    raise_json_error(get_current_request(),
                     hexc.HTTPUnprocessableEntity,
                     {
                         'message': _(u"Only saving to file system is supported."),
                     },
                     None)


def remove_bundle_from_disk(bundle, target, name=None):
    name = name or safe_filename(bundle.title)
    absolute_path = getattr(target, 'absolute_path', None) or target
    dest_path = os.path.join(absolute_path, CONTENT_PACKAGE_BUNDLES, name)
    if os.path.exists(dest_path):
        shutil.rmtree(dest_path, ignore_errors=False)
        return True
    return False


def remove_bundle(bundle, target, name=None):
    if IFilesystemBucket.providedBy(target):
        return remove_bundle_from_disk(bundle, target, name)
    raise_json_error(get_current_request(),
                     hexc.HTTPUnprocessableEntity,
                     {
                         'message': _(u"Only removing from file system is supported."),
                     },
                     None)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import stat
import shutil
import tempfile

from xml.dom import minidom

from pyramid import httpexceptions as hexc

from pyramid.threadlocal import get_current_request

import simplejson

import six

from nti.app.contentlibrary import MessageFactory as _

from nti.app.externalization.error import raise_json_error

from nti.base._compat import text_

from nti.contentlibrary import CONTENT_PACKAGE_BUNDLES

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contentlibrary.utils import is_valid_presentation_assets_source

from nti.namedfile.file import safe_filename

logger = __import__('logging').getLogger(__name__)


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


def _update_perms(file_path):
    """
    We shouldn't have to do this, but make sure our perms (775) for the
    output dir retain our parent group id as well as give RW access
    to both user and (copied) group.
    """
    parent = os.path.dirname(file_path)
    parent_stat = os.stat(parent)
    parent_gid = parent_stat.st_gid
    # -1 unchanged
    os.chown(file_path, -1, parent_gid)
    os.chmod(file_path,
             stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
             stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP |
             stat.S_IROTH | stat.S_IXOTH )


def save_presentation_assets_to_disk(assets, target):
    """
    Copy the presentation-assets found in `assets` to the target path.
    """
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
    # With NFS, we need to be careful we do os operations that ensure we will
    # not have random issues. Thus, we walk and copy files over as needed.
    # Make sure we touch the dirs so lastModified times are updated correctly
    # (as if we are in new directories). It may be better to write paths in a
    # GUID path to ensure uniqueness.

    # Recursively iterate until we find our images. Then copy them over.
    for current_dir, unused_dirs, files in os.walk(assets):
        for filename in files:
            if filename.endswith('.png'):
                # Makedirs and copy file
                rel_path = os.path.relpath(current_dir, assets)
                source_path = os.path.join(current_dir, filename)
                target_dir = os.path.join(path, rel_path)
                target_path = os.path.join(target_dir, filename)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
                shutil.copy2(source_path, target_path)
                shutil.copystat(current_dir, target_dir)
    # Update mod time
    shutil.copystat(assets, path)
    _update_perms(path)
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
        save_bundle_to_disk(bundle, target, assets, name)
        bundles = target.getChildNamed(CONTENT_PACKAGE_BUNDLES)
        bucket = bundles.getChildNamed(name)
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
        path = target.absolute_path
        path = save_presentation_assets_to_disk(assets, path)
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

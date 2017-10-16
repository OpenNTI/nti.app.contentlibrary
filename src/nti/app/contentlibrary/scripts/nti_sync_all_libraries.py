#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import sys
import argparse

from zope import component

from nti.app.contentlibrary.synchronize import synchronize

from nti.base._compat import text_

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.dataserver.utils import run_with_dataserver

from nti.dataserver.utils.base_script import create_context

logger = __import__('logging').getLogger(__name__)


def _process_args(site, ntiids, removal=True, notify=True):
    library = component.getUtility(IContentPackageLibrary)
    library.syncContentPackages()
    return synchronize(site=site, ntiids=ntiids,
                       allowRemoval=removal, notify=notify)


def main():
    arg_parser = argparse.ArgumentParser(description="Synchronize all libraries")
    arg_parser.add_argument('-v', '--verbose', help="Be verbose", action='store_true',
                            dest='verbose')
    arg_parser.add_argument('-s', '--site', help="Sites name",
                            dest='site', default=None)
    arg_parser.add_argument('-r', '--removal', help="Allow removal", action='store_true',
                            dest='removal', default=False)
    arg_parser.add_argument('-t', '--notify', help="Notify completion", action='store_true',
                            dest='notify', default=False)
    arg_parser.add_argument('-n', '--ntiids', help="NTIIDs", nargs="+",
                            dest='ntiids', default=())

    args = arg_parser.parse_args()

    env_dir = os.getenv('DATASERVER_DIR')
    if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
        raise IOError("Invalid dataserver environment root directory")

    site = args.site
    notify = args.notify
    removal = args.removal
    ntiids = set(args.ntiids) if args.ntiids else ()
    ntiids = map(text_, ntiids)
    if not site and ntiids:
        raise IOError("Must specify a site")

    conf_packages = ('nti.appserver',)
    context = create_context(env_dir, with_library=True)
    run_with_dataserver(environment_dir=env_dir,
                        xmlconfig_packages=conf_packages,
                        verbose=args.verbose,
                        context=context,
                        function=lambda: _process_args(site, ntiids, removal, notify))

    sys.exit(0)


if __name__ == '__main__':
    main()

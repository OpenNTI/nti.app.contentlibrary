#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os

from zope import component

from zope.configuration import xmlconfig

from nti.appserver.interfaces import IApplicationSettings

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.processlifetime import IProcessStarting
from nti.processlifetime import IApplicationTransactionOpenedEvent

@component.adapter(IApplicationTransactionOpenedEvent)
def _sync_global_library(_):
	library = component.getGlobalSiteManager().queryUtility(IContentPackageLibrary)
	if library is not None:
		# Ensure the library is enumerated at this time during startup
		# when we have loaded all the basic ZCML slugs but while
		# we are in control of the site.
		# NOTE: We are doing this in a transaction for the dataserver
		# to allow loading the packages to make persistent changes.
		library.syncContentPackages()

@component.adapter(IProcessStarting)
def _on_process_starting(event):
	# Load a library, if needed. We take the first of:
	# settings['library_zcml']
	# $DATASERVER_DIR/etc/library.zcml
	# settings[__file__]/library.zcml
	# (This last is for existing environments and tests, as it lets us put a
	# file beside development.ini). In most environments, this can be handled
	# with site.zcml; NOTE: this could not be in pre_site_zcml, as we depend
	# on our configuration listeners being in place
	# TODO: Note that these should probably be configured by site (e.g, componont registery)
	# A global one is fine, but lower level sites need the ability to override it
	# easily.
	# This will come with the splitting of the policy files into their own
	# projects, together with buildout.
	DATASERVER_DIR = os.getenv('DATASERVER_DIR', '')
	dataserver_dir_exists = os.path.isdir(DATASERVER_DIR)
	if dataserver_dir_exists:
		DATASERVER_DIR = os.path.abspath(DATASERVER_DIR)
	def dataserver_file(*args):
		return os.path.join(DATASERVER_DIR, *args)
	def is_dataserver_file(*args):
		return dataserver_dir_exists and os.path.isfile(dataserver_file(*args))

	xml_conf_machine = event.xml_conf_machine
	settings = component.getGlobalSiteManager().getUtility(IApplicationSettings)

	library_zcml = None
	if 'library_zcml' in settings:
		library_zcml = settings['library_zcml']
	elif is_dataserver_file('etc', 'library.zcml'):
		library_zcml = dataserver_file('etc', 'library.zcml')
	elif 	'__file__' in settings \
		and os.path.isfile(os.path.join(os.path.dirname(settings['__file__']), 'library.zcml')):
		library_zcml = os.path.join(os.path.dirname(settings['__file__']), 'library.zcml')

	if library_zcml and component.queryUtility(IContentPackageLibrary) is None:
		# If tests have already registered a library, use that instead
		library_zcml = os.path.normpath(os.path.expanduser(library_zcml))
		logger.debug("Loading library settings from %s", library_zcml)
		xml_conf_machine = xmlconfig.file(library_zcml,
										  package='nti.appserver',
										  context=xml_conf_machine,
										  execute=False)

	xml_conf_machine.execute_actions()

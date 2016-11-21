#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import has_key
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import greater_than
from hamcrest import has_property

from nti.contentlibrary import filesystem

from nti.contentlibrary.tests import ContentlibraryLayerTest

from nti.app.contentlibrary.content_unit_preferences.interfaces import IContentUnitPreferences
IPrefs = IContentUnitPreferences

from nti.testing.matchers import verifiably_provides

from nti.app.testing.layers import AppTestLayer

class TestAppFilesystem(ContentlibraryLayerTest):
	layer = AppTestLayer

	def test_adapter_prefs(self):

		unit = filesystem.FilesystemContentPackage(
			#filename='prealgebra/index.html',
			href = 'index.html',
			#root = 'prealgebra',
			#icon = 'icons/The%20Icon.png'
		)

		assert_that( IPrefs( unit, None ), is_( none() ) )

		unit.sharedWith = ['foo']

		assert_that( IPrefs( unit ), verifiably_provides( IPrefs ) )
		assert_that( IPrefs( unit ), has_property( '__parent__', unit ) )


import anyjson as json

from zope import interface
from zope.traversing.api import traverse

from pyramid import traversal
from pyramid.interfaces import IAuthorizationPolicy
from pyramid.interfaces import IAuthenticationPolicy

from nti.appserver import interfaces as app_interfaces

from nti.contentlibrary import interfaces as lib_interfaces

from nti.dataserver import users
from nti.dataserver.contenttypes import Note
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.ntiids import ntiids

from nti.app.contentlibrary.content_unit_preferences.views import _ContentUnitPreferencesPutView
from nti.app.contentlibrary.content_unit_preferences.decorators import _ContentUnitPreferencesDecorator

from nti.app.testing.layers import NewRequestLayerTest
from nti.app.testing.layers import NewRequestSharedConfiguringTestLayer

class _SecurityPolicyNewRequestSharedConfiguringTestLayer(NewRequestSharedConfiguringTestLayer):
	
	rem_username = 'foo@bar'

	@classmethod
	def setUp(cls):
		config = NewRequestSharedConfiguringTestLayer.config
		cls.__old_author = config.registry.queryUtility(IAuthorizationPolicy)
		cls.__old_authen = config.registry.queryUtility(IAuthenticationPolicy)
		cls.__new_policy = config.testing_securitypolicy(cls.rem_username)

	@classmethod
	def tearDown(cls):
		config = NewRequestSharedConfiguringTestLayer.config
		config.registry.unregisterUtility(cls.__new_policy, IAuthorizationPolicy)
		config.registry.unregisterUtility(cls.__new_policy, IAuthenticationPolicy)
		if cls.__old_author:
			config.registry.registerUtility(cls.__old_author, IAuthorizationPolicy)
		if cls.__old_authen:
			config.registry.registerUtility(cls.__old_authen, IAuthenticationPolicy)

	@classmethod
	def testSetUp(cls):
		pass

	@classmethod
	def testTearDown(cls):
		pass

@interface.implementer(lib_interfaces.IContentUnit)
class ContentUnit(object):
	href = 'prealgebra'
	ntiid = None
	__parent__ = None
	lastModified = 0

	def does_sibling_entry_exist( self, sib_name ):
		return None

	def __conform__( self, iface ):
		if iface == lib_interfaces.IContentUnitHrefMapper:
			return NIDMapper( self )

@interface.implementer(lib_interfaces.IContentUnitHrefMapper)
class NIDMapper(object):
	def __init__( self, context ):
		href = context.href
		root_package = traversal.find_interface( context, lib_interfaces.IContentPackage )
		if root_package:
			href = root_package.root + '/' + context.href
		href = href.replace( '//', '/' )
		if not href.startswith( '/' ):
			href = '/' + href

		self.href = href

class ContentUnitInfo(object):
	contentUnit = None
	lastModified = 0

from pyramid.threadlocal import get_current_request

class TestContainerPrefs(NewRequestLayerTest):
	
	layer = _SecurityPolicyNewRequestSharedConfiguringTestLayer
	
	rem_username = layer.rem_username

	def _do_check_root_inherited(self, ntiid=None, sharedWith=None, state='inherited', provenance=ntiids.ROOT):
		unit = ContentUnit()
		unit.ntiid = ntiid
		# Notice that the root is missing from the lineage

		info = ContentUnitInfo()
		info.contentUnit = unit
		decorator = _ContentUnitPreferencesDecorator( info, get_current_request() )
		result_map = {}

		decorator.decorateExternalMapping( info, result_map )

		assert_that( result_map, has_entry( 'sharingPreference',
											has_entry( 'State', state ) ) )

		assert_that( result_map, has_entry( 'sharingPreference',
											has_entry( 'Provenance', provenance ) ) )
		assert_that( result_map, has_entry( 'sharingPreference',
											has_entry( 'sharedWith', sharedWith ) ) )
		if sharedWith:
			assert_that( result_map, has_key( 'Last Modified' ) )
			assert_that( info, has_property( 'lastModified', greater_than( 0 ) ) )

	@WithMockDSTrans
	def test_decorate_inherit(self):
		user = users.User.create_user( username=self.rem_username )

		cid = "tag:nextthought.com:foo,bar"
		root_cid = ''

		# Create the containers
		for c in (cid,root_cid):
			user.containers.getOrCreateContainer( c )

		# Add sharing prefs to the root
		prefs = IContentUnitPreferences( user.getContainer( root_cid ) )
		prefs.sharedWith = ['a@b']

		self._do_check_root_inherited( ntiid=cid, sharedWith=['a@b'] )

		# Now, if we set something at the leaf node, then it trumps
		cid_prefs = IContentUnitPreferences( user.getContainer( cid ) )
		cid_prefs.sharedWith = ['leaf']

		self._do_check_root_inherited( ntiid=cid, sharedWith=['leaf'], state='set', provenance=cid )

		# Even setting something blank at the leaf trumps
		cid_prefs.sharedWith = []

		self._do_check_root_inherited( ntiid=cid, sharedWith=[], state='set', provenance=cid )

		# But if we delete it from the leaf, we're back to the root
		cid_prefs.sharedWith = None
		self._do_check_root_inherited( ntiid=cid, sharedWith=['a@b'] )

	@WithMockDSTrans
	def test_traverse_container_to_prefs(self):
		user = users.User.create_user( username="foo@bar" )

		cont_obj = Note()
		cont_obj.containerId = "tag:nextthought.com:foo,bar"

		user.addContainedObject( cont_obj )

		container = user.getContainer( cont_obj.containerId )
		prefs = traverse( container, "++fields++sharingPreference" )
		assert_that( prefs, verifiably_provides( IContentUnitPreferences ) )

	@WithMockDSTrans
	def test_traverse_content_unit_to_prefs(self):
		user = users.User.create_user( username=self.rem_username )

		cont_obj = Note()
		cont_obj.containerId = "tag:nextthought.com:foo,bar"

		user.addContainedObject( cont_obj )

		content_unit = ContentUnit()
		content_unit.ntiid = cont_obj.containerId

		prefs = traverse( content_unit, "++fields++sharingPreference", request=self.request )
		assert_that( prefs, verifiably_provides( IContentUnitPreferences ) )

	def _do_update_prefs( self, content_unit, sharedWith=None ):
		self.request.method = 'PUT'
		prefs = traverse( content_unit, "++fields++sharingPreference", request=self.request )
		assert_that( prefs, verifiably_provides( IContentUnitPreferences ) )

		self.request.context = prefs
		self.request.body = json.dumps( {"sharedWith": sharedWith } )
		self.request.content_type = 'application/json'

		class Accept(object):
			def best_match( self, *args ): return 'application/json'

		self.request.accept = Accept()

		@interface.implementer( lib_interfaces.IContentPackageLibrary )
		class Lib(object):
			titles = ()
			def pathToNTIID( self, ntiid ):
				return [content_unit]

		self.request.registry.registerUtility( Lib(), lib_interfaces.IContentPackageLibrary )

		result = _ContentUnitPreferencesPutView(self.request)()

		assert_that( prefs, has_property( 'sharedWith', sharedWith ) )
		assert_that( result, verifiably_provides( app_interfaces.IContentUnitInfo ) )

	@WithMockDSTrans
	def test_update_shared_with_in_preexisting_container(self):

		user = users.User.create_user( username=self.rem_username )
		# Make the container exist
		cont_obj = Note()
		cont_obj.containerId = "tag:nextthought.com:foo,bar"
		user.addContainedObject( cont_obj )

		content_unit = ContentUnit()
		content_unit.ntiid = cont_obj.containerId

		self._do_update_prefs( content_unit, sharedWith=['a','b']  )

	@WithMockDSTrans
	def test_update_shared_with_in_non_existing_container(self):

		_ = users.User.create_user( username=self.rem_username )
		# Note the container does not exist
		containerId = "tag:nextthought.com:foo,bar"

		content_unit = ContentUnit()
		content_unit.ntiid = containerId

		# The magic actually happens during traversal
		# That's why the method must be 'PUT' before traversal
		self._do_update_prefs( content_unit, sharedWith=['a','b'] )

	@WithMockDSTrans
	def test_update_shared_with_in_root_inherits(self):

		_ = users.User.create_user( username=self.rem_username )
		# Note the container does not exist
		containerId = "tag:nextthought.com:foo,bar"

		content_unit = ContentUnit()
		content_unit.ntiid = ntiids.ROOT

		self._do_update_prefs( content_unit, sharedWith=['a','b'] )

		self._do_check_root_inherited( ntiid=containerId, sharedWith=['a','b'] )

	@WithMockDSTrans
	def test_prefs_from_content_unit(self):
		_ = users.User.create_user( username=self.rem_username )
		# Note the container does not exist
		# containerId = "tag:nextthought.com:foo,bar"

		content_unit = ContentUnit()
		content_unit.ntiid = ntiids.ROOT

		interface.alsoProvides( content_unit, IContentUnitPreferences )
		content_unit.sharedWith = ['2@3']

		info = ContentUnitInfo()
		info.contentUnit = content_unit
		decorator = _ContentUnitPreferencesDecorator( info, get_current_request() )
		result_map = {}

		decorator.decorateExternalMapping( info, result_map )

		assert_that( result_map, has_entry( 'sharingPreference',
											has_entry( 'State', 'set' ) ) )

		assert_that( result_map, has_entry( 'sharingPreference',
											has_entry( 'sharedWith', ['2@3'] ) ) )

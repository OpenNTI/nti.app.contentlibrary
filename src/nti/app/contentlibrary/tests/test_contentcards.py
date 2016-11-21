#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_entries
does_not = is_not

from nti.app.contentlibrary.views.library_views import PAGE_INFO_MT_JSON as page_info_mt_json

from nti.app.contentlibrary.tests import ContentLibraryApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

class TestApplicationContentCard(ApplicationLayerTest):

	layer = ContentLibraryApplicationTestLayer

	child_ntiid = b'tag:nextthought.com,2011-10:testing-NTICard-temp.nticard.1'

	card_ntiid = child_ntiid

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_fetch_content_card_by_ntiid_accept_pageinfo(self):
		# If we fetch the URL of a content card, but specify that we accept PageInfo,
		# that's what we get back
		res = self.fetch_by_ntiid(self.card_ntiid,
								  headers={b'Accept': str(page_info_mt_json)})

		assert_that(res.status_int, is_(200))
		res = res.json_body
		assert_that(res, has_entry('Class', 'PageInfo'))

		# The content info we return points to an actual physical page
		assert_that(res, has_entry('Links',
									has_item(
										has_entries(
											'rel', 'content',
											'href', '/TestFilesystem/tag_nextthought_com_2011-10_USSC-HTML-Cohen_18.html'))))
		# We externalize title and cp-ntiid
		assert_that(res, has_entries('ContentPackageNTIID', 'tag:nextthought.com,2011-10:USSC-HTML-Cohen.cohen_v._california.',
									 'Title', 'COHEN v. CALIFORNIA.'))

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_fetch_content_card_by_ntiid_accept_link(self):
		# Asking for a link isn't supported
		self.fetch_by_ntiid(self.card_ntiid,
							headers={b'Accept': b'application/vnd.nextthought.link+json'},
							status=400)

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_fetch_content_card_by_ntiid(self):
		res = self.fetch_by_ntiid(self.card_ntiid)
		# Provisional!
		assert_that(res.json_body, has_entries(	'href', '/foo/bar',
												'MimeType', 'application/vnd.nextthought.nticard',
												'creator', 'biz baz',
												'description', 'The description.',
												# image is almost certainly wrong
												'image', 'resources/temp/cbb33e652dd64ca308905a138dec165c4619ae32/2cff8dc544afd32305107ce559484cb4ce1730df.png'))

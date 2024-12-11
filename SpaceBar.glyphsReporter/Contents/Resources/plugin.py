# encoding: utf-8

###########################################################################################################
#
#
#	Reporter Plugin
#
#	Read the docs:
#	https://github.com/schriftgestalt/GlyphsSDK/tree/master/Python%20Templates/Reporter
#
#
###########################################################################################################


import spacinginvaderlib
import objc
from GlyphsApp import Glyphs, MOUSEMOVED, Message
from GlyphsApp.plugins import ReporterPlugin
from AppKit import NSUserDefaults, NSHomeDirectory, NSSize, NSMenuItem, NSMenu, NSWorkspace, NSURL, NSBundle, NSOnState

path = __file__
Bundle = NSBundle.bundleWithPath_(path[:path.rfind("Contents/Resources/")])
VERSION = Bundle.objectForInfoDictionaryKey_("CFBundleShortVersionString")


class SpacingInvader(ReporterPlugin):

	@objc.python_method
	def settings(self):
		self.menuName = 'Space Bar'

		self.areas = []

		# margin = 20
		# innerMargin = 5
		# column = 120
		# elementHeight = 20
		# y = margin / 2.0
		self.modeSettings = [["masters", Glyphs.localize({'en': 'Masters', 'de': 'Master'})], ["instances", Glyphs.localize({'en': 'Instances', 'de': 'Instanzen'})]]

		# Default settings:
		justInstalled = False
		if self.getPreference('mode') is None:
			justInstalled = True
			self.setPreference('mode', 'instances')
		if self.getPreference('sidebearings') is None:
			self.setPreference('sidebearings', True)
		if self.getPreference('kerning') is None:
			self.setPreference('kerning', True)
		if self.getPreference('interpolation') is None:
			self.setPreference('interpolation', False)
		if self.getPreference('bboxw') is None:
			self.setPreference('bboxw', False)
		if self.getPreference('bboxh') is None:
			self.setPreference('bboxh', False)
		if self.getPreference('bboxt') is None:
			self.setPreference('bboxt', False)
		if self.getPreference('bboxb') is None:
			self.setPreference('bboxb', False)
		if self.getPreference('width') is None:
			self.setPreference('width', False)
		if self.getPreference('onlyActiveInstances') is None:
			self.setPreference('onlyActiveInstances', False)

		self.names = {
			'mode': 'Modus',
			'show': Glyphs.localize({'en': 'Show', 'de': 'Zeige'}),
			'interpolation': Glyphs.localize({'en': 'Interpolation Space', 'de': 'Interpolationsraum'}),
			'kerning': 'Kerning',
			'bboxw': Glyphs.localize({'en': u'BBox Width', 'de': 'BBox-Breite'}),
			'bboxh': Glyphs.localize({'en': u'BBox Height', 'de': u'BBox-Höhe'}),
			'bboxt': Glyphs.localize({'en': u'BBox Highest Point', 'de': u'BBox Höchster Punkt'}),
			'bboxb': Glyphs.localize({'en': u'BBox Lowest Point', 'de': u'BBox Niedrigster Punkt'}),
			'width': Glyphs.localize({'en': u'Width', 'de': 'Breite'}),
			'sidebearings': Glyphs.localize({'en': 'Sidebearings', 'de': 'Vor/Nachbreite'}),
			'LSB': Glyphs.localize({'en': u'Left Sidebearing', 'de': 'Vorbreite'}),
			'RSB': Glyphs.localize({'en': u'Right Sidebearing', 'de': 'Nachbreite'}),
			'onlyActiveInstances': Glyphs.localize({'en': u'Only active', 'de': 'Nur aktive'}),
		}

		# Define the menu
		self.generalContextMenus = []

		if NSHomeDirectory() == '/Users/yanone':
			self.generalContextMenus.append(
				{"name": "Reload Space Bar", "action": self.reloadLib}
			)

		Glyphs.addCallback(self.mouse, MOUSEMOVED)

		# Welcome
		if justInstalled:
			Message(Glyphs.localize({
				'en': u'Welcome to Space Bar %s' % VERSION,
				'de': u'Willkommen zu Space Bar %s' % VERSION,
			}), Glyphs.localize({
				'en': u'Thank you for choosing Space Bar. You’ll find me in the View menu under ‘Show Space Bar’.\n\nEnjoy and make sure to follow @yanone on Twitter.',
				'de': u'Danke zur Wahl von Space Bar. Du findest mich im Ansicht-Menü unter ‘Space Bar anzeigen’.\n\nViel Spaß und wir sehen uns bei @yanone auf Twitter.',
			}))

	@objc.python_method
	def conditionalContextMenus(self):
		# Empty list of context menu items
		contextMenus = []

		# Dot Icon
		dot = Bundle.imageForResource_('menudot')
		dot.setTemplate_(True)  # Makes the icon blend in with the toolbar.
		dot.setSize_(NSSize(16, 16))

		# Show Masters
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(Glyphs.localize({'en': 'Masters', 'de': 'Master'}), self.callbackShowMasters_, "")
		if self.getPreference('mode') == 'masters':
			menu.setState_(NSOnState)
			menu.setOnStateImage_(dot)
		contextMenus.append({"menu": menu})

		# Show Instances
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(Glyphs.localize({'en': 'Instances', 'de': 'Instanzen'}), self.callbackShowInstances_, "")
		if self.getPreference('mode') == 'instances':
			menu.setState_(NSOnState)
			menu.setOnStateImage_(dot)
		contextMenus.append({"menu": menu})

		# Only active instances
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(Glyphs.localize({'en': 'Show Only Active Instances', 'de': 'Zeige nur aktive Instanzen'}), self.callbackShowOnlyActiveInstances_, "")
		if self.getPreference('onlyActiveInstances'):
			menu.setState_(NSOnState)
		if self.getPreference('mode') == 'masters':
			menu.setAction_(None)
		contextMenus.append({"menu": menu})

		# ---------- Separator
		contextMenus.append({"menu": NSMenuItem.separatorItem()})

		# Show Interpolations Space
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['interpolation'], self.callbackShowInterpolation_, "")
		if self.getPreference('interpolation'):
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# Show Kerning
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['kerning'], self.callbackShowKerning_, "")
		if self.getPreference('kerning'):
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# ---------- Separator
		contextMenus.append({"menu": NSMenuItem.separatorItem()})

		# Show Width
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['width'], self.callbackShowWidth_, "")
		if self.getPreference('width'):
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# Show Sidebearings
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['sidebearings'], self.callbackShowSidebearings_, "")
		if self.getPreference('sidebearings'):
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# Show BBox Width
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['bboxw'], self.callbackShowBboxw_, "")
		if self.getPreference('bboxw'):
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# Show BBox Height
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['bboxh'], self.callbackShowBboxh_, "")
		if self.getPreference('bboxh'):
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# Show BBox Heighest
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['bboxt'], self.callbackShowBboxt_, "")
		if self.getPreference('bboxt'):
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# Show BBox Lowest
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['bboxb'], self.callbackShowBboxb_, "")
		if self.getPreference('bboxb'):
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# ---------- Separator
		contextMenus.append({"menu": NSMenuItem.separatorItem()})

		# Website
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(Glyphs.localize({'en': 'Space Bar Website...', 'de': 'Space Bar Webseite...'}), self.callbackGoToWebsite_, "")
		contextMenus.append({"menu": menu})

		# Twitter
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(Glyphs.localize({'en': '@yanone on Twitter...', 'de': '@yanone auf Twitter...'}), self.callbackGoToTwitter_, "")
		contextMenus.append({"menu": menu})

		# Put them into a sub menu
		menu = NSMenuItem.alloc().init()
		menu.setTitle_('Space Bar v%s' % VERSION)
		subMenu = NSMenu.alloc().init()
		for item in contextMenus:
			item['menu'].setTarget_(self)
			subMenu.addItem_(item['menu'])
		menu.setSubmenu_(subMenu)

		return [{'menu': menu}]

	def callbackGoToWebsite_(self, sender):
		NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_('https://yanone.de/software/spacebar/'))

	def callbackGoToTwitter_(self, sender):
		NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_('https://twitter.com/yanone/'))

	def callbackShowMasters_(self, sender):
		self.setPreference('mode', 'masters')
		Glyphs.redraw()

	def callbackShowInstances_(self, sender):
		self.setPreference('mode', 'instances')
		Glyphs.redraw()

	def callbackShowOnlyActiveInstances_(self, sender):
		self.setPreference('onlyActiveInstances', not self.getPreference('onlyActiveInstances'))
		Glyphs.redraw()

	def callbackShowWidth_(self, sender):
		self.setPreference('width', not self.getPreference('width'))
		Glyphs.redraw()

	def callbackShowSidebearings_(self, sender):
		self.setPreference('sidebearings', not self.getPreference('sidebearings'))
		Glyphs.redraw()

	def callbackShowInterpolation_(self, sender):
		self.setPreference('interpolation', not self.getPreference('interpolation'))
		Glyphs.redraw()

	def callbackShowKerning_(self, sender):
		self.setPreference('kerning', not self.getPreference('kerning'))
		Glyphs.redraw()

	def callbackShowBboxw_(self, sender):
		self.setPreference('bboxw', not self.getPreference('bboxw'))
		Glyphs.redraw()

	def callbackShowBboxh_(self, sender):
		self.setPreference('bboxh', not self.getPreference('bboxh'))
		Glyphs.redraw()

	def callbackShowBboxt_(self, sender):
		self.setPreference('bboxt', not self.getPreference('bboxt'))
		Glyphs.redraw()

	def callbackShowBboxb_(self, sender):
		self.setPreference('bboxb', not self.getPreference('bboxb'))
		Glyphs.redraw()

	def allowed(self):
		return True

	@objc.python_method
	def mouse(self, info):
		spacinginvaderlib.mouse(self, info)

	# do we need those
	'''
	def modeCallback_(self, sender):
		self.setPreference('mode', self.modeSettings[sender.get()][0])
		Glyphs.redraw()

	def onlyActiveInstancesCallback_(self, sender):
		self.setPreference('onlyActiveInstances', sender.get())
		Glyphs.redraw()

	def sidebearingsCallback_(self, sender):
		self.setPreference('sidebearings', sender.get())
		Glyphs.redraw()

	def widthCallback_(self, sender):
		self.setPreference('width', sender.get())
		Glyphs.redraw()

	def kerningCallback_(self, sender):
		self.setPreference('kerning', sender.get())
		Glyphs.redraw()

	def interpolationCallback_(self, sender):
		self.setPreference('interpolation', sender.get())
		Glyphs.redraw()

	def bboxwCallback_(self, sender):
		self.setPreference('bboxw', sender.get())
		Glyphs.redraw()

	def bboxhCallback_(self, sender):
		self.setPreference('bboxh', sender.get())
		Glyphs.redraw()

	def bboxtCallback_(self, sender):
		self.setPreference('bboxt', sender.get())
		Glyphs.redraw()

	def bboxbCallback_(self, sender):
		self.setPreference('bboxb', sender.get())
		Glyphs.redraw()
	'''

	@objc.python_method
	def getPreference(self, key):
		return NSUserDefaults.standardUserDefaults().objectForKey_("de.yanone.spaceBar.%s" % (key))

	@objc.python_method
	def setPreference(self, key, value):
		NSUserDefaults.standardUserDefaults().setObject_forKey_(value, "de.yanone.spaceBar.%s" % (key))

	@objc.python_method
	def start(self):
		spacinginvaderlib.start(self)

	@objc.python_method
	def foregroundInViewCoords(self, layer=None):
		if self.allowed():
			layer = self.controller.activeLayer()
			if layer is not None:
				spacinginvaderlib.foreground(self, layer)
		#cProfile.runctx('foreground(self, layer)', globals(), locals())

	@objc.python_method
	def reloadLib(self):
		try:
			from importlib import reload
			reload(spacinginvaderlib)
			# Glyphs.clearLog()
			self.settings()
			self.start()
		except:
			import traceback
			print(traceback.format_exc())

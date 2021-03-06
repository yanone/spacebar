# encoding: utf-8
from __future__ import division, print_function, unicode_literals

import copy, traceback, time, os, plistlib, objc
import GlyphsApp.plugins
from GlyphsApp import Glyphs, GSGlyph, GSFont, GSInstance, MOUSEMOVED, RTL, Message
from AppKit import NSBezierPath, NSPoint, NSColor, NSRect, NSHomeDirectory, NSImage, NSSize, NSZeroRect, NSCompositeSourceOver, NSMenuItem, NSMenu, NSWorkspace, NSURL, NSBundle, NSOnState

plist = plistlib.readPlist(os.path.join(os.path.dirname(__file__), '..', '..', 'Info.plist'))
VERSION = plist['CFBundleShortVersionString']

PAGEMARGIN = 8
AREACORNERRADIUS = 4
AREAOUTERMARGIN = 1
AREAINNERMARGIN = 6
AREATITLEHEIGHT = 20
AREAGRAYVALUE = .90
AREATRANSPARENCY = 1.0
INACTIVEMASTERCOLOR = {
	'left': (57, 169, 220),
	'right': (248, 179, 52),
}
ACTIVEMASTERCOLOR = {
	'left': (11, 143, 181),
	'right': (242, 148, 0),
}
AREASTANDARDWIDTH = 250
AREASTANDARDHEIGHT = 80
POINTSIZESMALL = 6
POINTSIZELARGE = 15
UNSELECTEDMASTERCOLOR = (200, 200, 200)
UNSELECTEDMASTERSIZE = 14
SELECTEDMASTERCOLOR = (160, 160, 160)
SELECTEDMASTERSIZE = 20
LINECOLOR = (100, 100, 100)
ACTIVECOLOR = (0, 0, 0)
INACTIVECOLOR = (140, 140, 140)
DEVIATIONCOLOR = (233, 93, 15)
DEVIATIONORIGINALCOLOR = (120, 120, 120)
ORIGIN = 'top' # topright, topleft, top, left, right, bottomleft, bottomright, bottom

alignment = {
	'topleft': 6, 
	'topcenter': 7, 
	'topright': 8,
	'left': 3, 
	'center': 4, 
	'right': 5, 
	'bottomleft': 0, 
	'bottomcenter': 1, 
	'bottomright': 2
	}
areaCache = {}

@objc.python_method
def CleanFloat(number, locale = 'en'):
	"""\
	Return number without decimal points if .0, otherwise with .x)
	"""
	try:
		if number % 1 == 0:
			return str(int(number))
		else:
			return str(float(number))
	except:
		return number

def NormalizeMinMax(source_floor, source_ceiling, target_floor, target_ceiling, value):
	"""\
	Normalize a value from source scale to target scale.
	"""
	source_floor, source_ceiling, target_floor, target_ceiling, value = map(float, (source_floor, source_ceiling, target_floor, target_ceiling, value))
	if target_floor == 0:
		return (value - source_floor)/(source_ceiling - source_floor) * target_ceiling
	else:
		return (value - source_floor)/(source_ceiling - source_floor) * (target_ceiling - target_floor) + target_floor


def Interpolate(a, b, p, limit = False):
	"""\
	Interpolate between values a and b at float position p (0-1)
	Limit: No extrapolation
	"""
	i = a + (b - a) * p
	if limit and i < a:
		return a
	elif limit and i > b:
		return b
	else:
		return i

# GlyphsApp extentions

def GSGlyph_MasterLayers(self):
	layers = []
	for layer in self.layers:
		if layer.layerId == layer.associatedMasterId:
			layers.append([weightValueForMaster(self.parent.masters[layer.layerId]), layer])
		elif '{' in layer.name and '}' in layer.name:
			weightValue = float(layer.name.split('{')[1].split('}')[0].split(',')[0].strip())
			layers.append([weightValue, layer])
	layers.sort(key=lambda x: x[0], reverse=False)
	return layers

GSGlyph.masterLayers = property(lambda self: GSGlyph_MasterLayers(self))

def GSGlyph_ChangeString(self):
	string = self.name
	for layer in self.layers:
		string += '%s-%s' % (str(layer.bounds), layer.width)
	return string

GSGlyph.changeString = property(lambda self: GSGlyph_ChangeString(self))

def GSFont_MasterLayers(self):
	layers = []
	for master in self.masters:
		layers.append([weightValueForMaster(master), master])
	# layers.sort(key=lambda x: x[0], reverse=False)
	return layers

GSFont.masterLayers = property(lambda self: GSFont_MasterLayers(self))

def GSFont_ActiveInstances(self):
	instances = []
	for instance in self.instances:
		if instance.active:
			instances.append(instance)
	return instances

GSFont.activeInstances = property(lambda self: GSFont_ActiveInstances(self))

def GSFont_VisibleInstances(self, plugin):
	instances = []
	for instance in self.instances:
		if instance.showInPanel(plugin):
			instances.append(instance)
	return instances

GSFont.visibleInstances = GSFont_VisibleInstances

def GSInstance_ShowInPanel(self, plugin):
	return plugin.getPreference('onlyActiveInstances') == False or plugin.getPreference('onlyActiveInstances') == True and self.active == True

GSInstance.showInPanel = GSInstance_ShowInPanel

def GSInstance_SortedInterpolationValues(self):
	if Glyphs.buildNumber >= 1141:
		font = self.font
	else:
		font = self.font()
	instanceMastersKeys = list(self.instanceInterpolations.keys())
	instanceMastersKeys.sort(key=lambda x: font.masters.index(font.masters[x]))
	return [[font.masters[x], self.instanceInterpolations[x]] for x in instanceMastersKeys]

GSInstance.sortedInterpolationValues = property(lambda self: GSInstance_SortedInterpolationValues(self))

class Line(object):
	def __init__(self, x1, y1, x2, y2, color = LINECOLOR, strokeWidth = 1.0):
		self.x1 = x1
		self.y1 = y1
		self.x2 = x2
		self.y2 = y2
		self.color = color
		self.strokeWidth = strokeWidth
		self.path = None

	def draw(self):
		# NSColor.colorWithDeviceRed_green_blue_alpha_(self.color[0] / 255.0, self.color[1] / 255.0, self.color[2] / 255.0, 1.0).set()
		NSColor.textColor().set()
		if not self.path:
			self.path = NSBezierPath.alloc().init()
			self.path.setLineWidth_(self.strokeWidth)
			self.path.moveToPoint_(NSPoint(self.x1, self.y1))
			self.path.lineToPoint_(NSPoint(self.x2, self.y2))
			self.path.closePath()
		self.path.stroke()

class Dot(object):
	def __init__(self, plugin, x, y, y2 = None, color = (0, 0, 0), size = POINTSIZESMALL, label = None, associatedValue = None):
		self.plugin = plugin
		self.x = x
		self.y = y
		self.y2 = y2
		self.color = color
		self.size = size
		self.label = label
		self.associatedValue = associatedValue
		self.path = None
		self.labelObject = None

	def draw(self, tab):
		hasValue = False
		if self.associatedValue:
			hasValue = True
			if self.associatedValue.y == None:
				hasValue = False

		# Deviation dot
		if self.y2:
			blendColor = NSColor.colorWithDeviceRed_green_blue_alpha_(DEVIATIONCOLOR[0] / 255.0, DEVIATIONCOLOR[1] / 255.0, DEVIATIONCOLOR[2] / 255.0, 1.0)
			NSColor.controlTextColor().blendedColorWithFraction_ofColor_(0.5, blendColor).set()
			self.path = NSBezierPath.alloc().init()
			self.path.appendBezierPathWithOvalInRect_(NSRect(NSPoint(self.x - (self.size * 1.5) / 2.0, self.y2 - (self.size * 1.5) / 2.0), NSPoint((self.size * 1.5), (self.size * 1.5))))
			if hasValue:
				self.path.fill()
			else:
				self.path.stroke()

		# Black dot
		# NSColor.colorWithDeviceRed_green_blue_alpha_(self.color[0] / 255.0, self.color[1] / 255.0, self.color[2] / 255.0, 1.0).set()
		NSColor.controlTextColor().colorWithAlphaComponent_(0.3).set()

		self.path = NSBezierPath.alloc().init()
		self.path.appendBezierPathWithOvalInRect_(NSRect(NSPoint(self.x - self.size / 2.0, self.y - self.size / 2.0), NSPoint(self.size, self.size)))

		if hasValue:
			self.path.fill()
		else:
			self.path.stroke()

		if self.label != 0 and self.label != None and self.label != '':
			self.plugin.drawTextAtPoint(CleanFloat(self.label), NSPoint(self.x, self.y - 20), fontSize = 10 * tab.scale, align = 'center', fontColor=NSColor.textColor())
			# string = NSString.alloc().initWithString_(str(self.label))
			# string = NSString.alloc().stringWithString_(str(self.label))
			# string = NSString.alloc().init()
			# string = self.label
			# string.string_(str(self.label))
			# string.drawAtPoint_color_alignment_(NSPoint(self.x, self.y - 20), NSColor.blackColor(), 'left')

class Value(object):
	def __init__(self, x, y, color = (0, 0, 0), size = POINTSIZESMALL, label = None, layer = 'foreground', associatedObject = None):
		self.x = x
		self.y = y
		self.y2 = None
		self.color = color
		self.size = size
		self.label = label
		self.layer = layer
		self.associatedObject = associatedObject

	def __repr__(self):
		return '<Value (%s, %s) %s>' % (self.x, self.y, self.layer)


class Area(object):
	def __init__(self, w, h, title = None, titleAlign = 'left', widthAdjust = 1.0, bgColor = None, infoText = None):
		self.w = w
		self.h = h
		self.widthAdjust = widthAdjust
		self.title = title
		self.titleAlign = titleAlign
		self.bgColor = bgColor
		self.infoText = infoText
		self.top = 0
		self.left = 0
		self.isMouseOver = False
		self.values = {'foreground': [], 'background': []}
		self.xMin = None
		self.xMax = None
		self.yMin = None
		self.yMax = None
		self.xScope = 0
		self.yScope = 0

		# NSImage
		self.image = None

	def __repr__(self):
		return '<Area %s>' % (self.title)

	def addValue(self, value):
		if not value.layer in self.values:
			self.values[value.layer] = []

		self.values[value.layer].append(value)

		if self.xMin == None:
			self.xMin = value.x
		if self.xMax == None:
			self.xMax = value.x

		if self.yMin == None:
			self.yMin = value.y
		if self.yMax == None:
			self.yMax = value.y

		self.xMin = min(self.xMin or 0, value.x or 0)
		self.xMax = max(self.xMax or 0, value.x or 0)
		self.yMin = min(self.yMin or 0, value.y or 0)
		self.yMax = max(self.yMax or 0, value.y or 0)
		if value.y2:
			self.yMin = min(self.yMin or 0, value.y2 or 0)
			self.yMax = max(self.yMax or 0, value.y2 or 0)
		self.xScope = self.xMax - self.xMin
		self.yScope = self.yMax - self.yMin

	def height(self):
		if self.title:
			return self.h + AREATITLEHEIGHT
		else:
			return self.h

	def drawingArea(self):
		left, bottom, width, height = self.position()
		# top = bottom + height
		factor = 3
		bottom += AREAINNERMARGIN * factor * 1.95
		left += AREAINNERMARGIN * factor
		width -= AREAINNERMARGIN * 2 * factor
		height -= AREAINNERMARGIN * 2 * factor * 1.3
		if self.title:
			height -= AREATITLEHEIGHT
		return left, bottom, width, height

	def position(self):
		bottom = self.top - self.height()
		# top = bottom + self.height()
		width = int(self.w * self.widthAdjust)
		height = self.height()
		return round(self.left), bottom, width, height

	def mouseOver(self, mousePosition):
		left, bottom, width, height = self.position()
		if left < mousePosition.x < left + width and bottom < mousePosition.y < bottom + height:
			self.active()
		else:
			self.inactive()

	def active(self):
		return
		if self.isMouseOver == False:
			self.isMouseOver = True
			Glyphs.redraw()
			# print(self.title)

	def inactive(self):
		return
		if self.isMouseOver == True:
			self.isMouseOver = False
			Glyphs.redraw()

	def draw(self, font):
		position = self.position()
		left, bottom, width, height = position
		if width and height and not self.image:
			self.image = NSImage.alloc().initWithSize_(NSSize(width, height))
			self.image.lockFocus()
			self._draw(font, position)
			self.image.unlockFocus()

		if self.image:
			self.image.drawAtPoint_fromRect_operation_fraction_(NSPoint(left, bottom), NSZeroRect, NSCompositeSourceOver, 1.0)
		# font.currentTab.graphicView().addSubview_(self.view)

	def _draw(self, font, position):
		# Sort values by interpolation space weight value
		self.values['foreground'].sort(key=lambda value: value.x, reverse=False)

		tab = font.currentTab

		left, bottom, width, height = position
		left = 0
		bottom = 0
		top = bottom + height

		# Background
		if self.title:
			path = NSBezierPath.alloc().init()
			path.appendBezierPathWithRoundedRect_xRadius_yRadius_(NSRect(NSPoint(left, bottom), NSPoint(width, height)), AREACORNERRADIUS, AREACORNERRADIUS)
			if self.isMouseOver:
				# NSColor.colorWithDeviceRed_green_blue_alpha_(.5, .5, .5, AREATRANSPARENCY).set()
				NSColor.disabledControlTextColor().colorWithAlphaComponent_(AREATRANSPARENCY).set()
			else:
				if self.bgColor:
					self.bgColor.set()
				else:
					NSColor.windowBackgroundColor().colorWithAlphaComponent_(AREATRANSPARENCY).set()
					#NSColor.colorWithDeviceRed_green_blue_alpha_(AREAGRAYVALUE, AREAGRAYVALUE, AREAGRAYVALUE, AREATRANSPARENCY).set()
			path.fill()
			# NSColor.colorWithDeviceRed_green_blue_alpha_(.5, .5, .5, .5).set()
			# path.stroke()

		# Title
		if self.title:
			topAdjust = 7
			if self.titleAlign == 'left':
				self.parent.plugin.drawTextAtPoint(self.title, NSPoint(left + AREAINNERMARGIN, top - AREAINNERMARGIN - topAdjust), fontSize = 10 * tab.scale, align = self.titleAlign, fontColor=NSColor.textColor())
			elif self.titleAlign == 'center':
				self.parent.plugin.drawTextAtPoint(self.title, NSPoint(left + width / 2.0, top - AREAINNERMARGIN - topAdjust), fontSize = 10 * tab.scale, align = self.titleAlign, fontColor=NSColor.textColor())
			else:
				self.parent.plugin.drawTextAtPoint(self.title, NSPoint(left - AREAINNERMARGIN + width, top - AREAINNERMARGIN - topAdjust), fontSize = 10 * tab.scale, align = self.titleAlign, fontColor=NSColor.textColor())
		if False:
			drawingArea = self.drawingArea()
			path = NSBezierPath.alloc().init()
			path.appendBezierPathWithRoundedRect_xRadius_yRadius_(NSRect(NSPoint(drawingArea[0], drawingArea[1]), NSPoint(drawingArea[2], drawingArea[3])), AREACORNERRADIUS, AREACORNERRADIUS)
			NSColor.colorWithDeviceRed_green_blue_alpha_(.5, .5, .5, .5).set()
			path.stroke()

		# Draw values
		left, bottom, width, height = self.drawingArea()
		left -= position[0]
		bottom -= position[1]

		if self.infoText:
			self.parent.plugin.drawTextAtPoint(self.infoText, NSPoint(left - 15, bottom - 20), fontSize = 10 * tab.scale, align = 'bottomleft', fontColor=NSColor.textColor())
		else:
			# lastDot = None
			dots = []
			if self.yMin != None and self.yMax != None:
				xScopeAdjust = 1.0
				xMedian = 0
				if self.xScope > 0:
					xMedian = self.xMin + self.xScope / 2.0
					# if self.xScope > width:
					xScopeAdjust = width / float(self.xScope)
					xMedian = xMedian / xScopeAdjust

				yScopeAdjust = 1.0
				# yMedian = 0
				if self.yScope > 0:
					# yMedian = self.yMin + self.yScope / 2.0
					if self.yScope > height:
						yScopeAdjust = height / float(self.yScope)

				# horizontal point zero line
				y = bottom + (0 - self.yMin) * yScopeAdjust
				if bottom + AREACORNERRADIUS <= y <= bottom + height - AREACORNERRADIUS:
					line = Line(0, y, width * xScopeAdjust, y, strokeWidth = .25)
					line.draw()

				# vertical master position line
				# x = left + (font.masters[font.masterIndex].weightValue - self.xMin) * xScopeAdjust
				# line = Line(Dot(self.parent.plugin, x, position[1]), Dot(self.parent.plugin, x, position[1] + position[3]), strokeWidth = .25)
				# line.draw()

				for value in self.values['background']:
					x = left + ((value.x or 0) - self.xMin) * xScopeAdjust
					y = bottom + ((value.y or 0) - self.yMin) * yScopeAdjust
					dot = Dot(self.parent.plugin, x, y, color = value.color, size = value.size, label = value.label)
					dot.associatedValue = value
					dot.draw(tab)

				for i, value in enumerate(self.values['foreground']):
					x = left + ((value.x or 0) - self.xMin) * xScopeAdjust
					y = bottom + ((value.y or 0) - self.yMin) * yScopeAdjust
					if value.y2:
						y2 = bottom + ((value.y2 or 0) - self.yMin) * yScopeAdjust
					else:
						y2 = None

					dot = Dot(self.parent.plugin, x, y, y2 = y2, color = value.color, size = value.size, label = value.label)
					dot.associatedValue = value
					dots.append(dot)

			for i in range(len(dots) - 1):
				dot1 = dots[i]
				dot2 = dots[i+1]

				if not dot1.y2 and not dot2.y2:
					line = Line(dots[i].x, dots[i].y, dots[i+1].x, dots[i+1].y)
					line.draw()

				if dot1.y2 and not dot2.y2:
					line = Line(dots[i].x, dots[i].y2, dots[i+1].x, dots[i+1].y, color = DEVIATIONCOLOR)
					line.draw()
					line = Line(dots[i].x, dots[i].y, dots[i+1].x, dots[i+1].y)
					line.draw()

				if not dot1.y2 and dot2.y2:
					line = Line(dots[i].x, dots[i].y, dots[i+1].x, dots[i+1].y2, color = DEVIATIONCOLOR)
					line.draw()
					line = Line(dots[i].x, dots[i].y, dots[i+1].x, dots[i+1].y)
					line.draw()

				if dot1.y2 and dot2.y2:
					line = Line(dots[i].x, dots[i].y2, dots[i+1].x, dots[i+1].y2, color = DEVIATIONCOLOR)
					line.draw()
					line = Line(dots[i].x, dots[i].y, dots[i+1].x, dots[i+1].y)
					line.draw()

			for dot in dots:
				dot.draw(tab)

	def addMasterValues(self, masterValues, font, activeLayer, glyphSideOnDisplay):
		activeLayerChosen = False
		for masterValue in masterValues:

			masterValue = copy.copy(masterValue)
			instanceValue = self.values['foreground'][int(masterValue.x)]
			masterValue.y = instanceValue.y
			nachKomma = masterValue.x % 1.0

			if masterValue.x and nachKomma != 0.0:
				instanceValue2 = self.values['foreground'][int(masterValue.x) + 1]
				if instanceValue.y2 and instanceValue2.y2:
					masterValue.y = Interpolate(instanceValue.y2, instanceValue2.y2, nachKomma)
				elif instanceValue.y and instanceValue2.y2:
					masterValue.y = Interpolate(instanceValue.y, instanceValue2.y2, nachKomma)
				elif instanceValue.y2 and instanceValue2.y:
					masterValue.y = Interpolate(instanceValue.y2, instanceValue2.y, nachKomma)
				elif instanceValue.y and instanceValue2.y:
					masterValue.y = Interpolate(instanceValue.y, instanceValue2.y, nachKomma)

			# Master/layer is active
			if glyphSideOnDisplay:
				masterValue.color = INACTIVEMASTERCOLOR[glyphSideOnDisplay]
			else:
				masterValue.color = UNSELECTEDMASTERCOLOR

			if activeLayer == masterValue.associatedObject:
				# print(activeLayer, 'chosen')
				masterValue.size = SELECTEDMASTERSIZE
				if glyphSideOnDisplay:
					masterValue.color = ACTIVEMASTERCOLOR[glyphSideOnDisplay]
				else:
					masterValue.color = SELECTEDMASTERCOLOR
				activeLayerChosen = True

			if not activeLayerChosen and font.masters[activeLayer.associatedMasterId] == masterValue.associatedObject:# or activeLayer == masterValue.associatedObject:
				# print(activeLayer, 'chosen')
				masterValue.size = SELECTEDMASTERSIZE
				if glyphSideOnDisplay:
					masterValue.color = ACTIVEMASTERCOLOR[glyphSideOnDisplay]
				else:
					masterValue.color = SELECTEDMASTERCOLOR
				activeLayerChosen = True

			self.addValue(masterValue)


class Display(object):
	def __init__(self, plugin):
		self.areas = []
		self.plugin = plugin
		self.columns = []

	def addArea(self, area):
		area.parent = self
		self.areas.append(area)

	def draw(self, font):
		tab = font.currentTab
		if tab:
			widthSum = 0
			heightSum = 0
			tabViewPortSize = tab.viewPort.size
			for area in self.areas:
				widthSum += area.w
				heightSum += area.height()

			widthSum += (len(self.areas) - 1) * AREAOUTERMARGIN
			widthAdjust = 1.0
			if widthSum + 2*PAGEMARGIN > tabViewPortSize.width:
				widthAdjust = (tabViewPortSize.width - 2*PAGEMARGIN) / float(widthSum)
				widthSum *= widthAdjust

			if ORIGIN == 'top':
				top = tab.viewPort.origin.y + tabViewPortSize.height - PAGEMARGIN
				width = tabViewPortSize.width
				leftBorder = int(tab.viewPort.origin.x + width / 2.0 - widthSum / 2.0)
				# print(leftBorder)
				# Draw a blue rectangle all across the Edit View's visible area
				# NSColor.blueColor().set()
				# NSBezierPath.strokeRect_(NSRect(NSPoint(leftBorder, Glyphs.font.currentTab.viewPort.origin.y), NSPoint(width, Glyphs.font.currentTab.viewPort.size.height)))

				# Draw a blue rectangle all across the Edit View's visible area
				# NSColor.blueColor().set()
				# NSBezierPath.strokeRect_(NSRect(NSPoint(leftBorder, Glyphs.font.currentTab.viewPort.origin.y), NSPoint(width, Glyphs.font.currentTab.viewPort.size.height)))

				# Draw a blue rectangle all across the Edit View's visible area
				# NSColor.blueColor().set()
				# NSBezierPath.strokeRect_(NSRect(NSPoint(leftBorder, top - self.areas[0].height()), NSPoint(widthSum, self.areas[0].height())))

				# Draw a white rectangle all across the Edit View's visible area
				#NSColor.whiteColor().set()
				# NSColor.colorWithDeviceRed_green_blue_alpha_(1, 1, 1, .95).set()
				NSColor.textBackgroundColor().colorWithAlphaComponent_(0.35).set()
				if len(self.areas):
					height = self.areas[0].height() + 2 * PAGEMARGIN
					NSBezierPath.fillRect_(NSRect(NSPoint(tab.viewPort.origin.x, tab.viewPort.origin.y + tab.viewPort.size.height - height), NSPoint(width, height)))
					# x = tab.viewPort.origin.x + (tabViewPortSize.width / 2.0 - widthSum / 2.0) * widthAdjust
					left = 0
					for area in self.areas:
						area.top = top
						area.left = leftBorder + left
						area.widthAdjust = widthAdjust
						area.draw(font)
						#top += area.height() + AREAOUTERMARGIN
						left += area.w * widthAdjust + AREAOUTERMARGIN
						# left -= left % 2
						# left += 2

			if ORIGIN == 'bottom':
				top = tab.viewPort.origin.y + PAGEMARGIN + self.areas[0].height()
				left = int(tab.viewPort.origin.x + tab.viewPort.size.width / 2.0 - (widthSum - (len(self.areas) - 1) * AREAOUTERMARGIN) / 2.0)
				for area in self.areas:
					area.top = top
					area.left = left
					area.draw()
					# top += area.height() + AREAOUTERMARGIN
					left += area.w + AREAOUTERMARGIN

def drawValuesInInterpolationSpace(font, display, area, masterLayers, positiveColor = None, negativeColor = None, glyphSide = 'left', activeLayer = None):
	# Draw masters
	layersDrawn = []
	# masterDots = []
	layersToDots = {}

	for weightValue, layer, interpolatedValue in masterLayers:
		if not layer in layersDrawn:
			for instance in font.instances:
				if weightValueForInstance(instance) == weightValue:
					x = font.instances.index(instance)
					y = interpolatedValue

					value = Value(x, y)
					value.size = UNSELECTEDMASTERSIZE
					value.color = UNSELECTEDMASTERCOLOR
					value.layer = 'background'

					area.addValue(value)
					layersDrawn.append(layer)
					# masterDots = value
					layersToDots[layer] = value

			for i in range(len(font.instances)-1):
				firstInstance = font.instances[i]
				secondInstance = font.instances[i+1]

				if weightValueForInstance(firstInstance) < weightValue < weightValueForInstance(secondInstance):
					t = NormalizeMinMax(weightValueForInstance(firstInstance), weightValueForInstance(secondInstance), 0, 1, weightValue)
					x = i + t
					y = interpolatedValue

					value = Value(x, y)
					value.size = UNSELECTEDMASTERSIZE
					value.color = UNSELECTEDMASTERCOLOR
					value.layer = 'background'

					area.addValue(value)
					layersDrawn.append(layer)
					layersToDots[layer] = value

	masterSelected = False

	# select master by layer object
	if activeLayer:
		# print('layer', layer)
		for key in layersToDots.keys():
			if activeLayer == key:
				# print('key', key)
				value = layersToDots[key]
				value.size = SELECTEDMASTERSIZE
				value.color = SELECTEDMASTERCOLOR
				masterSelected = True
				break

	if not masterSelected:
		for key in layersToDots.keys():
			if font.selectedLayers[0] == key:
				value = layersToDots[key]
				value.size = SELECTEDMASTERSIZE
				value.color = SELECTEDMASTERCOLOR
				masterSelected = True
				break

	if not masterSelected:
		for key in layersToDots.keys():
			if ('GSFontMaster' in key.__class__.__name__ and font.selectedFontMaster.id == key.id) or ('GSLayer' in key.__class__.__name__ and font.selectedFontMaster.id == key.layerId):
				value = layersToDots[key]
				value.color = SELECTEDMASTERCOLOR
				value.size = SELECTEDMASTERSIZE

	# Draw actual values
	instanceCount = 0
	for instance in font.instances:
		# Extrapolation 
		instanceWeightValue = weightValueForInstance(instance)
		if instanceWeightValue < masterLayers[0][0]:
			l1 = masterLayers[0][2]
			l2 = masterLayers[1][2]
			t = NormalizeMinMax(masterLayers[0][0], masterLayers[1][0], 0, 1, instanceWeightValue)
			sbValue = Interpolate(l1, l2, t)

		# Interpolation
		elif masterLayers[0][0] <= instanceWeightValue <= masterLayers[-1][0]:
			for i in range(len(masterLayers) - 1):
				if masterLayers[i][0] == instanceWeightValue:
					sbValue = masterLayers[i][2]
				elif masterLayers[i][0] < instanceWeightValue < masterLayers[i + 1][0]:
					l1 = masterLayers[i][2]
					l2 = masterLayers[i+1][2]
					t = NormalizeMinMax(masterLayers[i][0], masterLayers[i+1][0], 0, 1, instanceWeightValue)
					sbValue = Interpolate(l1, l2, t)
				elif masterLayers[i + 1][0] == instanceWeightValue:
					sbValue = masterLayers[i + 1][2]

		# Extrapolation 
		if instanceWeightValue > masterLayers[-1][0]:
			l1 = masterLayers[-2][2]
			l2 = masterLayers[-1][2]
			t = NormalizeMinMax(masterLayers[-2][0], masterLayers[-1][0], 0, 1, instanceWeightValue)
			sbValue = Interpolate(l1, l2, t)

		value = Value(instanceCount, sbValue)
		# value = Value(instanceWeightValue, sbValue)
		# if layer.layerId == font.selectedFontMaster.id:
		# 	value.size = POINTSIZELARGE
		value.label = int(round(sbValue))
		value.associatedObject = instance
		area.addValue(value)
		if instance.active == False:
			value.color = (128, 128, 128)
			value.label = None
		else:
			if int(round(sbValue)) < 0 and negativeColor:
				value.color = negativeColor
			elif int(round(sbValue)) > 0 and positiveColor:
				value.color = positiveColor
				
		instanceCount+=1

def _addSidebearings(display, glyph, side, mode, title = None, titleAlign = 'left', glyphSide = 'left', activeLayer = None):
	sbArea = Area(AREASTANDARDWIDTH, AREASTANDARDHEIGHT, title, titleAlign)
	font = glyph.parent
	if mode == 'masters':
		glyphMasterLayers = glyph.masterLayers
		i = 0
		for layer in [x[1] for x in glyphMasterLayers]:
			if side == 'left':
				sbValue = layer.LSB
			elif side == 'right':
				sbValue = layer.RSB

			value = Value(i, sbValue)
			if layer == activeLayer:
				value.size = POINTSIZELARGE
			value.label = sbValue
			sbArea.addValue(value)
			i+=1
	elif mode == 'instances':
		# Cache
		compareString = str(glyph.lastChange) + str(activeLayer) + str(font.selectedFontMaster) + str(font.selectedLayers[0]) + str(glyphSide) + str(side) + str(font.activeInstances)
		key = 'sidebearing_%s_%s' % (glyphSide, side)
		if not key in areaCache or compareString != areaCache[key]['compareString']:
			glyphMasterLayers = glyph.masterLayers
			# extend masters list with interpolatable values
			for masterLayer in glyphMasterLayers:
				if side == 'left':
					masterLayer.append(masterLayer[1].LSB)
				elif side == 'right':
					masterLayer.append(masterLayer[1].RSB)
			drawValuesInInterpolationSpace(font, display, sbArea, glyphMasterLayers, glyphSide = glyphSide, activeLayer = activeLayer)
			areaCache[key] = {
				'compareString': compareString,
				'area': sbArea,
			}
		else:
			sbArea = areaCache[key]['area']
	return sbArea

def addValues(plugin, action, layers, layersWithoutDeviations, masterValues, display, glyph, sideOfGlyph, glyphSideOnDisplay, mode, title = None, activeLayer = None, bgColor = None):
	sbArea = Area(AREASTANDARDWIDTH, AREASTANDARDHEIGHT, title, titleAlign = sideOfGlyph or 'center', bgColor = bgColor)
	font = glyph.parent
	if mode == 'masters':
		glyphMasterLayers = glyph.masterLayers
		i = 0
		for master in glyph.parent.masters:
			layer = glyph.layers[master.id]
			if action == 'sidebearings':
				if sideOfGlyph == 'left':
					sbValue = layer.LSB
				elif sideOfGlyph == 'right':
					sbValue = layer.RSB
			elif action == 'width':
				sbValue = layer.width
			elif action == 'bboxw':
				sbValue = layer.bounds.size.width
			elif action == 'bboxh':
				sbValue = layer.bounds.size.height
			elif action == 'bboxt':
				sbValue = layer.bounds.origin.y + layer.bounds.size.height
			elif action == 'bboxb':
				sbValue = layer.bounds.origin.y
			elif action == 'kerning':
				sbValue = layer.bounds.origin.y

			# Empty layer
			if sbValue == 0:
				try:
					# GLYPHS 3
					if not layer.shapes:
						sbValue = None
				except:
					# GLYPHS 2
					if not layer.paths and not layer.components:
						sbValue = None

			# Value is valid
			value = Value(i, sbValue)
			if layer == activeLayer:
				value.size = POINTSIZELARGE
			value.label = sbValue
			sbArea.addValue(value)
			i+=1

	elif mode == 'instances':
		# instanceMasters = [x[0] for x in layers[0][1].sortedInterpolationValues]
		# mastersAdded = []
		for instanceCount, instance, layer in layers:
			sbValue2 = None
			if action == 'sidebearings':
				if sideOfGlyph == 'left':
					sbValue = layer.LSB
					if layersWithoutDeviations:
						sbValue2 = layersWithoutDeviations[instanceCount].LSB
				elif sideOfGlyph == 'right':
					sbValue = layer.RSB
					if layersWithoutDeviations:
						sbValue2 = layersWithoutDeviations[instanceCount].RSB
					# print(sbValue)
			elif action == 'width':
				sbValue = layer.width
				if layersWithoutDeviations:
					sbValue2 = layersWithoutDeviations[instanceCount].width
			elif action == 'bboxw':
				sbValue = layer.bounds.size.width
				if layersWithoutDeviations:
					sbValue2 = layersWithoutDeviations[instanceCount].bounds.size.width
			elif action == 'bboxh':
				sbValue = layer.bounds.size.height
				if layersWithoutDeviations:
					sbValue2 = layersWithoutDeviations[instanceCount].bounds.size.height
			elif action == 'bboxt':
				sbValue = layer.bounds.origin.y + layer.bounds.size.height
				if layersWithoutDeviations:
					sbValue2 = layersWithoutDeviations[instanceCount].bounds.origin.y + layersWithoutDeviations[instanceCount].bounds.size.height
			elif action == 'bboxb':
				sbValue = layer.bounds.origin.y
				if layersWithoutDeviations:
					sbValue2 = layersWithoutDeviations[instanceCount].bounds.origin.y
			# Empty layer
			if sbValue == 0:
				try:
					# GLYPHS 3
					if not layer.shapes:
						sbValue = None
				except:
					# GLYPHS 2
					if not layer.paths and not layer.components:
						sbValue = None

			value = Value(instanceCount, sbValue)

			# Value is valid
			if sbValue != None:
				if instance.active:
					value.color = ACTIVECOLOR
					value.label = int(round(sbValue))
				else:
					value.color = INACTIVECOLOR
					value.label = None

				# Add second value
				if sbValue != None and sbValue2 != None and sbValue != sbValue2 and abs(sbValue - sbValue2) > 1.0:
					value.color = DEVIATIONORIGINALCOLOR
					value.y2 = value.y
					value.y = sbValue2
					# print('Devitation', abs(sbValue - sbValue2))

			# Value is empty
			else:
				value.color = (128, 128, 128)
				value.label = None

			value.associatedObject = instance
			#print(action, value)
			sbArea.addValue(value)

		# Add masters
		sbArea.addMasterValues(masterValues, font, activeLayer, glyphSideOnDisplay)

	return sbArea

def getKerning(master, leftGlyph, rightGlyph):
	font = leftGlyph.parent
	_kerning = font.kerningForPair(master.id, leftGlyph.rightKerningKey, rightGlyph.leftKerningKey)
	kerningExceptionLeft = font.kerningForPair(master.id, leftGlyph.name, rightGlyph.rightKerningKey)
	kerningExceptionRight = font.kerningForPair(master.id, leftGlyph.rightKerningKey, rightGlyph.name)
	kerningExceptionBoth = font.kerningForPair(master.id, leftGlyph.name, rightGlyph.name)
	exception = False
	if _kerning > 1000000000:
		_kerning = 0
	if kerningExceptionLeft < 1000000000:
		_kerning = kerningExceptionLeft
		exception = True
	if kerningExceptionRight < 1000000000:
		_kerning = kerningExceptionRight
		exception = True
	if kerningExceptionBoth < 1000000000:
		_kerning = kerningExceptionBoth
		exception = True
	return (_kerning, exception)

def addKerning(display, plugin, leftGlyph, rightGlyph, mode, masterValues, activeLayer, writingDirection):
	font = leftGlyph.parent
	kerningArea = Area(AREASTANDARDWIDTH, AREASTANDARDHEIGHT, title = 'Kerning', titleAlign = 'center')

	for master in font.masters:
		pairHasKerning = False
		kerning = font.kerningForPair(master.id, leftGlyph.rightKerningKey, rightGlyph.leftKerningKey)
		if kerning != None and kerning > 10000000000:
			kerning = 0
		if kerning != None and kerning != 0:
			pairHasKerning = True
			break

	if pairHasKerning:
		if mode == 'masters':
			for i, master in enumerate(font.masters):
				kerning, exception = getKerning(master, leftGlyph, rightGlyph)
				value = Value(i, kerning)
				value.label = int(kerning)
				kerningArea.addValue(value)
				if master.id == font.selectedFontMaster.id:
					value.size = POINTSIZELARGE
				if exception:
					value.color = (229, 53, 45)
				elif kerning < 0:
					value.color = (0, 158, 224)
				elif kerning > 0:
					value.color = (248, 179, 52)
				else:
					value.color = (128, 128, 128)

		elif mode == 'instances':
			if hasattr(Glyphs, 'buildNumber') and Glyphs.buildNumber < 996:
				kerningArea.infoText = 'Showing kerning for instances is\nsupported only in Glyph version 2.4.2\n(Build 996) or higher.\nPlease update Glyphs to the latest version.'
			else:
				instanceCount = 0
				for instance in font.instances:
					if instance.showInPanel(plugin):
						a = instance.interpolatedFontProxy.glyphForName_(leftGlyph.name)
						b = instance.interpolatedFontProxy.glyphForName_(rightGlyph.name)
						masterID = instance.interpolatedFontProxy.fontMasterAtIndex_(0).valueForKey_("id")
						# print(hasattr(instance.interpolatedFontProxy,) 'kerningForFontMasterID_firstGlyph_secondGlyph_')
						# print(hasattr(instance.interpolatedFontProxy,) 'kerningForFontMasterID_LeftKey_RightKey_direction_')
						# print(hasattr(instance.interpolatedFontProxy,) 'kerningForFontMasterID_firstGlyph_secondGlyph_direction_')
						sbValue = instance.interpolatedFontProxy.kerningForFontMasterID_firstGlyph_secondGlyph_direction_(masterID, a, b, writingDirection)
						# print(sbValue)
						if sbValue > 9999999999999:
							sbValue = 0
						value = Value(instanceCount, sbValue)
						# Value is valid
						if sbValue != None:
							if instance.active:
								if sbValue < 0:
									value.color = (0, 158, 224)
								elif sbValue > 0:
									value.color = (248, 179, 52)
								value.label = int(round(sbValue))
							else:
								value.color = INACTIVECOLOR
								value.label = None
						# Value is empty
						else:
							value.color = (128, 128, 128)
							value.label = None
						instanceCount += 1
						kerningArea.addValue(value)

				# Add masters
				kerningArea.addMasterValues(masterValues, font, activeLayer, None)

	return kerningArea

def addInterpolation(display, font, mode, title):
	instancesArea = Area(AREASTANDARDWIDTH, AREASTANDARDHEIGHT, title, 'center')

	if mode == 'masters':
		for i, master in enumerate(font.masters):
			masterWeightValue = weightValueForMaster(master)
			value = Value(masterWeightValue, masterWeightValue)
			value.label = int(masterWeightValue)
			instancesArea.addValue(value)
			if master.id == font.selectedFontMaster.id:
				value.size = POINTSIZELARGE

	elif mode == 'instances':
		glyphMasterLayers = font.masterLayers
		# extend masters list with interpolatable values
		for masterLayer in glyphMasterLayers:
			masterLayer.append(masterLayer[0]) # masterLayer[1].weightValue ?! masterLayer is list of [weightValue, master]

		# Cache
		compareString = str(font.selectedFontMaster) + str(font.selectedLayers[0]) + str(glyphMasterLayers)
		key = 'interpolation'
		if not key in areaCache or compareString != areaCache[key]['compareString']:
			drawValuesInInterpolationSpace(font, display, instancesArea, glyphMasterLayers, positiveColor = (234, 102, 50))
			areaCache[key] = {
				'compareString': compareString,
				'area': instancesArea,
			}
		else:
			instancesArea = areaCache[key]['area']
	return instancesArea

def weightValueForMaster(master):
	try:
		# GLYPHS 3
		weightAxisID = None
		font = master.font
		for a in font.axes:
			if a.axisTag() == "wght":
				weightAxisID = a.axisId()
				break
		if weightAxisID:
			return master.axisValueValueForId_(weightAxisID)
		else:
			# return the value of the first axis:
			return master.axes[0]
	except:
		# GLYPHS 2
		return master.weightValue

def weightValueForInstance(instance):
	try:
		# GLYPHS 3
		weightAxisID = None
		font = instance.font
		for a in font.axes:
			if a.axisTag() == "wght":
				weightAxisID = a.axisId()
				break
		if weightAxisID:
			return instance.axisValueValueForId_(weightAxisID)
		else:
			# return value of the first axis:
			return instance.coordinateForAxisIndex_(0)
	except:
		# GLYPHS 2
		return instance.weightValue

def foreground(plugin, layer):
	try:
		calcTime = time.time()
		layer = plugin.controller.graphicView().activeLayer()
		if layer:
			font = layer.parent.parent
			# if not 'spaceBarTab' in font.tempData():
			# 	font.tempData()['spaceBarTab'] = font.currentTab
			tab = font.currentTab
			font.tempData()['spaceBarAreas'] = []
			display = Display(plugin)
			# Settings
			mode = plugin.getPreference('mode') # masters or instances
			# Prepare layers cache
			currentTabString = str(font.selectedFontMaster) + ','.join(tab.features) + tab.text
			if plugin.tabString != currentTabString:
				plugin.tabString = currentTabString
				plugin.tabLayers = tab.composedLayers
			textCursor = tab.textCursor
			# print(font#tab, tab.graphicView())
			if font.tool == 'TextTool' or font.tool == 'SelectTool':
				# Prepare values of masters
				activeInstances = font.visibleInstances(plugin)
				fontMastersString = str(font.masters) + str(activeInstances) + str(plugin.getPreference('onlyActiveInstances'))

				if plugin.mastersChangedString != fontMastersString:
					plugin.mastersChangedString = fontMastersString
					plugin.masterValues = []
					mastersAdded = []

					if font.instances:
						instanceMasters = [x[0] for x in font.instances[0].sortedInterpolationValues]
						instanceCount = 0

						for instance in font.instances:
							if instance.showInPanel(plugin):
								for master in font.masters:
									# print("instance.instanceInterpolations", type(instance.instanceInterpolations.keys()), instance.instanceInterpolations.keys())
									if len(instance.instanceInterpolations) == 1 and master.id in instance.instanceInterpolations:
										if weightValueForInstance(activeInstances[0]) <= weightValueForMaster(master) <= weightValueForInstance(activeInstances[-1]):
											mastersAdded.append(master)
											value = Value(instanceCount, 0)
											value.size = UNSELECTEDMASTERSIZE
											value.color = UNSELECTEDMASTERCOLOR
											value.layer = 'background'
											value.associatedObject = master
											plugin.masterValues.append(value)
											# instanceCount += 1

								newInstanceMasters = [x[0] for x in instance.sortedInterpolationValues]
								if not newInstanceMasters[0] in mastersAdded and len(newInstanceMasters) == 2 and instanceMasters != newInstanceMasters:
									if weightValueForInstance(activeInstances[0]) <= weightValueForMaster(newInstanceMasters[0]) <= weightValueForInstance(activeInstances[-1]):
										mastersAdded.append(newInstanceMasters[0])
										x = instanceCount - .5
										y = 0
										instanceMasters = newInstanceMasters
										value = Value(x, y)
										value.size = UNSELECTEDMASTERSIZE
										value.color = UNSELECTEDMASTERCOLOR
										value.layer = 'background'
										value.associatedObject = newInstanceMasters[0]
										plugin.masterValues.append(value)
								instanceCount += 1

				# Add interpolation space panel
				if plugin.getPreference('interpolation'):
					font.tempData()['spaceBarAreas'].append([addInterpolation(display, font, mode, plugin.names['interpolation'])])

				# Prepare glyphs for display
				leftGlyph = None
				rightGlyph = None
				leftLayer = None
				rightLayer = None

				try:
					# GLYPHS 3
					cachedGlyphs = tab.graphicView().layoutManager().cachedLayers()
				except:
					# GLYPHS 2
					cachedGlyphs = tab.graphicView().layoutManager().cachedGlyphs()

				# Catch left and right glyphs
				if tab and tab.textRange == 0 and textCursor > 0 and tab.text[textCursor-1] != '\n' and len(plugin.tabLayers) >= 1 and 'GSGlyph' in plugin.tabLayers[textCursor - 1].parent.__class__.__name__:
					leftGlyph = plugin.tabLayers[textCursor - 1].parent
					leftLayer = cachedGlyphs[textCursor - 1]

				if tab and tab.textRange == 0 and 0 <= textCursor < len(tab.text) and len(plugin.tabLayers) >= 1 and 'GSGlyph' in plugin.tabLayers[textCursor].parent.__class__.__name__:
					rightGlyph = plugin.tabLayers[textCursor].parent
					rightLayer = cachedGlyphs[textCursor]

				# Change order for RTL
				if tab.direction == RTL:
					leftGlyph, rightGlyph = rightGlyph, leftGlyph
					leftLayer, rightLayer = rightLayer, leftLayer

				preferencesString = str([plugin.getPreference(z) for z in plugin.names.keys()])

				# Left Glyph

				# Add brace layers to masters
				if leftGlyph:
					changeString = leftGlyph.changeString + str(leftLayer) + str(rightLayer) + preferencesString + str(font.activeInstances) + str(tab.viewPort.size.width) + str(tab.viewPort.size.height)
					if not 'left' in plugin.glyphChangeStrings or plugin.glyphChangeStrings['left'] != changeString:

						plugin.glyphChangeStrings['left'] = changeString
						plugin.areaCache['left'] = []

						# Prepare interpolated layers
						leftLayers = []
						instanceCount = 0
						for instance in font.instances:

							if instance.showInPanel(plugin):
								if instance.showInPanel(plugin):
									if Glyphs.buildNumber >= 1056:
										try:
											# GLYPHS 3
											layer = instance.interpolatedFontProxy.glyphForName_(leftGlyph.name).layerForId_(instance.interpolatedFontProxy.fontMasterID())
										except:
											# GLYPHS 2
											layer = instance.interpolatedFontProxy.glyphForName_(leftGlyph.name).layerForKey_(instance.interpolatedFontProxy.fontMasterID())
										
									else:
										if hasattr(leftGlyph, 'interpolate_decompose_error_'):
											layer = leftGlyph.interpolate_decompose_error_(instance, True, None)
										elif hasattr(leftGlyph, 'interpolate_keepSmart_error_'):
											layer = leftGlyph.interpolate_keepSmart_error_(instance, True, None)
									leftLayers.append((instanceCount, instance, layer))
									instanceCount += 1

						# Prepare layers without deviations
						leftLayersWithoutDeviations = []
						glyphHasDeviations = False
						for layer in leftGlyph.layers:
							if '[' in layer.name or ']' in layer.name or '{' in layer.name:
								glyphHasDeviations = True
								break
						if glyphHasDeviations:
							glyph = copy.copy(leftGlyph)
							glyph.name = 'test1'
							glyph.parent = font
							for i, layer in enumerate(copy.copy(glyph.layers)):
								if '[' in layer.name or ']' in layer.name or '{' in layer.name:
									del glyph.layers[layer.layerId]
							for layer in glyph.layers:
								layer.decomposeComponents()
							for instance in font.instances:
								if instance.showInPanel(plugin):
									if instance.showInPanel(plugin):
										if hasattr(glyph, 'interpolate_decompose_error_'):
											layer = glyph.interpolate_decompose_error_(instance, True, None)
										elif hasattr(glyph, 'interpolate_keepSmart_error_'):
											layer = glyph.interpolate_keepSmart_error_(instance, True, None)
										leftLayersWithoutDeviations.append(layer)

						masterValues = copy.copy(plugin.masterValues)
						for layer in leftGlyph.layers:
							if '{' in layer.name and '}' in layer.name:
								interpolationValues = map(int, layer.name.split('{')[1].split('}')[0].split(','))

								if len(interpolationValues) == 1:
									for instanceCount, instance, _layer in leftLayers:
										if instanceCount < len(leftLayers) - 1:
											if weightValueForInstance(leftLayers[instanceCount][1]) <= interpolationValues[0] <= weightValueForInstance(leftLayers[instanceCount + 1][1]):
												value = Value(instanceCount + .5, 0)
												value.size = UNSELECTEDMASTERSIZE
												value.color = UNSELECTEDMASTERCOLOR
												value.layer = 'background'
												if leftLayer == layer:
													value.associatedObject = layer
												masterValues.insert(0, value)

								elif len(interpolationValues) == 2:
									for instanceCount, instance, _layer in leftLayers:
										if instanceCount < len(leftLayers) - 1:
											if leftLayers[instanceCount][1].widthValue == interpolationValues[1] and leftLayers[instanceCount + 1][1].widthValue == interpolationValues[1]:
												if weightValueForInstance(leftLayers[instanceCount][1]) < interpolationValues[0] and weightValueForInstance(leftLayers[instanceCount + 1][1]) > interpolationValues[0]:
													value = Value(instanceCount + .5, 0)
													value.size = UNSELECTEDMASTERSIZE
													value.color = UNSELECTEDMASTERCOLOR
													value.layer = 'background'
													if leftLayer == layer:
														value.associatedObject = layer
													masterValues.insert(0, value)

						# Draw
						areas = []

						for action, name, sideOfGlyph in (
							('sidebearings', 'LSB', 'left'),
							('width', 'width', None),
							('bboxw', 'bboxw', None),
							('bboxh', 'bboxh', None),
							('bboxt', 'bboxt', None),
							('bboxb', 'bboxb', None),
							('sidebearings', 'RSB', 'right'),
						):
							if leftGlyph and plugin.getPreference(action):
								leftBgColor = NSColor.windowBackgroundColor().blendedColorWithFraction_ofColor_(0.05, NSColor.blueColor()) # (230, 235, 240)
								areas.append(addValues(plugin, action, leftLayers, leftLayersWithoutDeviations, masterValues, display, leftGlyph, sideOfGlyph, 'left', mode, title = plugin.names[name], activeLayer = leftLayer, bgColor = leftBgColor))
						plugin.areaCache['left'] = areas
					font.tempData()['spaceBarAreas'].append(plugin.areaCache['left'])

				# Kerning
				if leftGlyph and rightGlyph and plugin.getPreference('kerning'):
					font.tempData()['spaceBarAreas'].append([addKerning(display, plugin, leftGlyph, rightGlyph, mode, plugin.masterValues, activeLayer = leftLayer, writingDirection = tab.direction)])

				# Right Glyph
				if rightGlyph:
					changeString = rightGlyph.changeString + str(leftLayer) + str(rightLayer) + preferencesString + str(font.activeInstances) + str(tab.viewPort.size.width) + str(tab.viewPort.size.height)
					if not 'right' in plugin.glyphChangeStrings or plugin.glyphChangeStrings['right'] != changeString:
						plugin.glyphChangeStrings['right'] = changeString
						plugin.areaCache['right'] = []
						# Prepare interpolated layers
						rightLayers = []
						instanceCount = 0
						for instance in font.instances:
							if instance.showInPanel(plugin):
								if instance.showInPanel(plugin):
									if Glyphs.buildNumber >= 1056:
										try:
											# GLYPHS 3
											layer = instance.interpolatedFontProxy.glyphForName_(rightGlyph.name).layerForId_(instance.interpolatedFontProxy.fontMasterID())
										except:
											# GLYPHS 2
											layer = instance.interpolatedFontProxy.glyphForName_(rightGlyph.name).layerForKey_(instance.interpolatedFontProxy.fontMasterID())
									else:
										if hasattr(rightGlyph, 'interpolate_keepSmart_error_'):
											layer = rightGlyph.interpolate_keepSmart_error_(instance, True, None)
										elif hasattr(rightGlyph, 'interpolate_decompose_error_'):
											layer = rightGlyph.interpolate_decompose_error_(instance, True, None)
									rightLayers.append((instanceCount, instance, layer))
									instanceCount += 1

						# Prepare layers without deviations
						rightLayersWithoutDeviations = []
						glyphHasDeviations = False
						for layer in rightGlyph.layers:
							if '[' in layer.name or ']' in layer.name or '{' in layer.name:
								glyphHasDeviations = True
								break
						if glyphHasDeviations:
							glyph = copy.copy(rightGlyph)
							glyph.name = 'test1'
							glyph.parent = font
							for i, layer in enumerate(copy.copy(glyph.layers)):
								if '[' in layer.name or ']' in layer.name or '{' in layer.name:
									del glyph.layers[layer.layerId]
							for layer in glyph.layers:
								layer.decomposeComponents()
							for instance in font.instances:
								if instance.showInPanel(plugin):
									if instance.showInPanel(plugin):
										if hasattr(glyph, 'interpolate_decompose_error_'):
											layer = glyph.interpolate_decompose_error_(instance, True, None)
										elif hasattr(glyph, 'interpolate_keepSmart_error_'):
											layer = glyph.interpolate_keepSmart_error_(instance, True, None)
										rightLayersWithoutDeviations.append(layer)

						# Add brace layers to masters
						masterValues = copy.copy(plugin.masterValues)
						for layer in rightGlyph.layers:
							if '{' in layer.name and '}' in layer.name:
								interpolationValues = map(int, layer.name.split('{')[1].split('}')[0].split(','))

								if len(interpolationValues) == 1:
									for instanceCount, instance, _layer in rightLayers:
										if instanceCount < len(rightLayers) - 1:
											if weightValueForInstance(rightLayers[instanceCount][1]) <= interpolationValues[0] <= weightValueForInstance(rightLayers[instanceCount + 1][1]):
												value = Value(instanceCount + .5, 0)
												value.size = UNSELECTEDMASTERSIZE
												value.color = UNSELECTEDMASTERCOLOR
												value.layer = 'background'
												if rightLayer == layer:
													value.associatedObject = layer
												masterValues.insert(0, value)

								elif len(interpolationValues) == 2:
									for instanceCount, instance, _layer in rightLayers:
										if instanceCount < len(rightLayers) - 1:
											if rightLayers[instanceCount][1].widthValue == interpolationValues[1] and rightLayers[instanceCount + 1][1].widthValue == interpolationValues[1]:
												if weightValueForInstance(rightLayers[instanceCount][1]) < interpolationValues[0] and weightValueForInstance(rightLayers[instanceCount + 1][1]) > interpolationValues[0]:
													value = Value(instanceCount + .5, 0)
													value.size = UNSELECTEDMASTERSIZE
													value.color = UNSELECTEDMASTERCOLOR
													value.layer = 'background'
													if rightLayer == layer:
														value.associatedObject = layer
													masterValues.insert(0, value)

						# Draw
						areas = []
						for action, name, sideOfGlyph in (
							('sidebearings', 'LSB', 'left'),
							('width', 'width', None),
							('bboxw', 'bboxw', None),
							('bboxh', 'bboxh', None),
							('bboxt', 'bboxt', None),
							('bboxb', 'bboxb', None),
							('sidebearings', 'RSB', 'right'),
						):
							if rightGlyph and plugin.getPreference(action):
								rightBgColor = NSColor.windowBackgroundColor().blendedColorWithFraction_ofColor_(0.05, NSColor.redColor()) # (240, 235, 230)
								areas.append(addValues(plugin, action, rightLayers, rightLayersWithoutDeviations, masterValues, display, rightGlyph, sideOfGlyph, 'right', mode, title = plugin.names[name], activeLayer = rightLayer, bgColor = rightBgColor))
						plugin.areaCache['right'] = areas
					font.tempData()['spaceBarAreas'].append(plugin.areaCache['right'])
				calcTime = time.time() - calcTime

			for i, subAreas in enumerate(font.tempData()['spaceBarAreas']):
				for area in subAreas:
					display.addArea(area)
				if i < len(font.tempData()['spaceBarAreas']) - 1:
					display.addArea(Area(10, 0))

			drawTime = time.time()

			display.draw(font)

			if NSHomeDirectory() == '/Users/yanone':
				drawTime = time.time() - drawTime
				left = tab.viewPort.origin.x + PAGEMARGIN
				top = tab.viewPort.origin.y + PAGEMARGIN
				plugin.drawTextAtPoint('Calc: %ss, Draw: %ss, Total: %ss' % (str(calcTime)[:4], str(drawTime)[:4], str(calcTime + drawTime)[:4]), NSPoint(left, top + 10), fontSize = 10 * tab.scale, align = 'left', fontColor=NSColor.textColor())

	except:
		print(traceback.format_exc())

def start(plugin):
	plugin.tabLayers = None
	plugin.tabOtherLayers = None
	plugin.tabString = None
	plugin.mouseActiveObject = None
	plugin.mastersChangedString = None

	# Cache
	plugin.glyphChangeStrings = {}
	plugin.areaCache = {}
	plugin.mastersChangedString = ''

def mouse(plugin, info):
	return
	tab = Glyphs.font.currentTab
	if tab:
		font = Glyphs.font
		tabHeight = tab.previewHeight
		if tabHeight > 0:
			tabHeight += 1

		mousePosition = info.object().locationInWindow()
		mousePosition = NSPoint(mousePosition.x + tab.viewPort.origin.x, mousePosition.y + tab.viewPort.origin.y - tab.bottomToolbarHeight - tabHeight)
		if font and 'spaceBarAreas' in font.tempData():
			for a in font.tempData()['spaceBarAreas']:
				for area in a:
					area.mouseOver(mousePosition)


############ Below imports stay with the main SpacingInvader() class ############

from GlyphsApp.plugins import ReporterPlugin
from AppKit import NSUserDefaults, NSHomeDirectory

class SpacingInvader(ReporterPlugin):

	@objc.python_method
	def settings(self):
		self.menuName = 'Space Bar'
		self.areas = []
		margin = 20
		# innerMargin = 5
		column = 120
		elementHeight = 20
		y = margin / 2.0
		self.modeSettings = (
			( "masters", Glyphs.localize({'en': 'Masters', 'de': 'Master'}) ),
			( "instances", Glyphs.localize({'en': 'Instances', 'de': 'Instanzen'}) ),
		)

		# Default settings:
		justInstalled = False
		if self.getPreference('mode') == None:
			justInstalled = True
			self.setPreference('mode', 'instances')
		if self.getPreference('sidebearings') == None:
			self.setPreference('sidebearings', True)
		if self.getPreference('kerning') == None:
			self.setPreference('kerning', True)
		if self.getPreference('interpolation') == None:
			self.setPreference('interpolation', False)
		if self.getPreference('bboxw') == None:
			self.setPreference('bboxw', False)
		if self.getPreference('bboxh') == None:
			self.setPreference('bboxh', False)
		if self.getPreference('bboxt') == None:
			self.setPreference('bboxt', False)
		if self.getPreference('bboxb') == None:
			self.setPreference('bboxb', False)
		if self.getPreference('width') == None:
			self.setPreference('width', False)
		if self.getPreference('onlyActiveInstances') == None:
			self.setPreference('onlyActiveInstances', False)

		self.names = {
			'mode': 'Modus',
			'show': Glyphs.localize({'en': 'Show', 'de': 'Zeige'}),
			'interpolation': Glyphs.localize({'en': 'Interpolation Space', 'de': 'Interpolationsraum'}),
			'kerning': 'Kerning',
			'bboxw': Glyphs.localize({'en': 'BBox Width', 'de': 'BBox-Breite'}),
			'bboxh': Glyphs.localize({'en': 'BBox Height', 'de': 'BBox-Höhe'}),
			'bboxt': Glyphs.localize({'en': 'BBox Highest Point', 'de': 'BBox Höchster Punkt'}),
			'bboxb': Glyphs.localize({'en': 'BBox Lowest Point', 'de': 'BBox Niedrigster Punkt'}),
			'width': Glyphs.localize({'en': 'Width', 'de': 'Breite'}),
			'sidebearings': Glyphs.localize({'en': 'Sidebearings', 'de': 'Vor/Nachbreite'}),
			'LSB': Glyphs.localize({'en': 'Left Sidebearing', 'de': 'Vorbreite'}),
			'RSB': Glyphs.localize({'en': 'Right Sidebearing', 'de': 'Nachbreite'}),
			'onlyActiveInstances': Glyphs.localize({'en': 'Only active', 'de': 'Nur aktive'}),
		}


		# Define the menu
		self.generalContextMenus = []

		Glyphs.addCallback(self.mouse, MOUSEMOVED)

		# Welcome
		if justInstalled:
			Message(Glyphs.localize({
				'en': 'Welcome to Space Bar %s' % VERSION,
				'de': 'Willkommen zu Space Bar %s' % VERSION,
			}), Glyphs.localize({
				'en': 'Thank you for choosing Space Bar. You’ll find me in the View menu under ‘Show Space Bar’.\n\nEnjoy and make sure to follow @yanone on Twitter.',
				'de': 'Danke zur Wahl von Space Bar. Du findest mich im Ansicht-Menü unter ‘Space Bar anzeigen’.\n\nViel Spaß und wir sehen uns bei @yanone auf Twitter.',
			})
			)

	@objc.python_method
	def conditionalContextMenus(self):
		# Empty list of context menu items
		contextMenus = []

		# Dot Icon
		path = __file__
		Bundle = NSBundle.bundleWithPath_(path[:path.rfind("Contents/Resources/")])
		dot = Bundle.imageForResource_('menudot')
		dot.setTemplate_(True) # Makes the icon blend in with the toolbar.
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
		if self.getPreference('onlyActiveInstances') == True:
			menu.setState_(NSOnState)
		if self.getPreference('mode') == 'masters':
			menu.setAction_(None)
		contextMenus.append({"menu": menu})

		# ---------- Separator
		contextMenus.append({"menu": NSMenuItem.separatorItem()})

		# Show Interpolations Space
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['interpolation'], self.callbackShowInterpolation_, "")
		if self.getPreference('interpolation') == True:
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# Show Kerning
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['kerning'], self.callbackShowKerning_, "")
		if self.getPreference('kerning') == True:
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# ---------- Separator
		contextMenus.append({"menu": NSMenuItem.separatorItem()})

		# Show Width
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['width'], self.callbackShowWidth_, "")
		if self.getPreference('width') == True:
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# Show Sidebearings
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['sidebearings'], self.callbackShowSidebearings_, "")
		if self.getPreference('sidebearings') == True:
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# Show BBox Width
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['bboxw'], self.callbackShowBboxw_, "")
		if self.getPreference('bboxw') == True:
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# Show BBox Height
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['bboxh'], self.callbackShowBboxh_, "")
		if self.getPreference('bboxh') == True:
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# Show BBox Heighest
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['bboxt'], self.callbackShowBboxt_, "")
		if self.getPreference('bboxt') == True:
			menu.setState_(NSOnState)
		contextMenus.append({"menu": menu})

		# Show BBox Lowest
		menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.names['bboxb'], self.callbackShowBboxb_, "")
		if self.getPreference('bboxb') == True:
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


	def callbackBuy_(self, sender):
		NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_('https://yanone.de/buy/software/'))

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
		mouse(self, info)

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

	@objc.python_method
	def getPreference(self, key):
		return NSUserDefaults.standardUserDefaults().objectForKey_("de.yanone.spaceBar.%s" % (key))

	@objc.python_method
	def setPreference(self, key, value):
		NSUserDefaults.standardUserDefaults().setObject_forKey_(value, "de.yanone.spaceBar.%s" % (key))

	@objc.python_method
	def start(self):
		start(self)

	@objc.python_method
	def foregroundInViewCoords(self, layer=None):
		# print("__foregroundInViewCoords")
		if self.allowed():
			if layer is None:
				layer = self.controller.activeLayer
			if layer != None:
				foreground(self, layer)
		# cProfile.runctx('foreground(self, layer)', globals(), locals())

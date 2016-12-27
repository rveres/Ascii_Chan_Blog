import os
import re
import sys
import urllib2
import json
from string import letters
import time
import logging

import jinja2
import webapp2

from google.appengine.api import memcache
from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
								autoescape = True)

class Handler(webapp2.RequestHandler):
	def write(self, *a, **kw):
		self.response.out.write(*a, **kw)

	def render_str(self, template, **params):
		t = jinja_env.get_template(template)
		return t.render(params)

	def render(self, template, **kw):
		self.write(self.render_str(template, **kw))

GMAPS_URL = "http://maps.googleapis.com/maps/api/staticmap?size=380x263&sensor=false&"

def gmaps_img(points):
	markers = '&'.join('markers=%s,%s' % (p.lat, p.lon) for p in points)
	return GMAPS_URL + markers

IP_URL = "http://ip-api.com/json/"

def get_coords(ip):
	# ip = request.remote_addr
	url = IP_URL + ip
	content = None

	try:
		content = urllib2.urlopen(url).read()
	except URLError:
		return

	if content:
		#parse the xml and find the coordinates
		parsed_json = json.loads(content)
		status = parsed_json['status']
		if status == 'success':
			lat = parsed_json['lat']
			lon = parsed_json['lon']
			if lat and lon:
	#			lon, lat = coords[0].childNodes[0].nodeValue.split(',')
				return db.GeoPt(lat, lon)


class Art(db.Model):
	title = db.StringProperty(required = True)
	art = db.TextProperty(required = True)
	created = db.DateTimeProperty(auto_now_add = True)
	coords = db.GeoPtProperty()

def top_arts(update = False):
	key = 'top'
	arts = memcache.get(key)
	if arts is None or update:
		logging.error("DB QUERY")
		arts = db.GqlQuery("SELECT * FROM Art ORDER BY created DESC LIMIT 10")
		arts = list(arts)	#prevent the running of multiple queries
		memcache.set(key, arts)

	return arts

class MainPage(Handler):
	def render_front(self, title="", art="", error=""):
		arts = top_arts()
		
		#find which arts have coords
		points = filter(None, (a.coords for a in arts))

		#if we have any arts with coords, make an image url
		img_url = None
		if points:
			img_url = gmaps_img(points)

		#display the image url

		self.render("front.html", title=title, art=art, error=error, arts=arts, img_url=img_url)

	def get(self):
		self.render_front()

	def post(self):
		title = self.request.get("title")
		art = self.request.get("art")

		if title and art:
			a = Art(title = title, art = art)

			#lookup the user's coordinates from their ip
			coords = get_coords(self.request.remote_addr)

			#if we have coordinates, add them to the art
			if coords:
				a.coords = coords

			a.put()

			time.sleep(0.25)
			# rerun the query and update the cache
			top_arts(True)

			self.redirect("/")
		else:
			error = "we need both a title and some artwork!"
			self.render_front(title, art, error)


app = webapp2.WSGIApplication([('/', MainPage)], debug = True)
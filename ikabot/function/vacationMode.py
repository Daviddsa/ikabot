#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
import sys
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.getJson import getCiudad

t = gettext.translation('vacationMode',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def activarvacationMode(s):
	html = s.get()
	ciudad = getCiudad(html)

	data = {'action': 'Options', 'function': 'activateVacationMode', 'actionRequest': s.token(), 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'templateView': 'options_umod_confirm'}
	s.post(params=data, ignoreExpire=True)

def vacationMode(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()
		print(_('Activate vacation mode? [Y/n]'))
		rta = read(values=['y', 'Y', 'n', 'N', ''])
		if rta.lower() == 'n':
			e.set()
			return

		activarvacationMode(s)

		print(_('Vacation mode has been activated.'))
		enter()
		e.set()
		clear()
		exit()
	except KeyboardInterrupt:
		e.set()
		return

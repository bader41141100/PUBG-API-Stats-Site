from django.shortcuts import render
from django.http import HttpResponse, JsonResponse

import collections

from api.settings import API_HEADER
from api.functions import (
	build_url, build_lifetime_url, make_request, correct_perspective, correct_mode,
	build_player_url, get_player_matches, retrieve_player_season_stats, populate_seasons
)

# populate_seasons()

from api.models import *

import time
from datetime import datetime

## try import orjson, fallback to normal json module upon failure
try:
	import orjson as json
except:
	import json

from threading import Thread, Timer
import multiprocessing

from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def status(request):
	return JsonResponse({
		'status': 'OK'
	})

@csrf_exempt
def search(request):

	if request.method == 'POST':

		body = json.loads(request.body)

		player_name = body.get('player_name', None)

		perspective = body.get('perspective', None)
		game_mode = body.get('game_mode', None)
		platform = body.get('platform', None)

		player_platform_url_cache_key = '{}_{}_platform_url'.format(player_name, platform)
		player_player_url_cache_key = '{}_{}_player_url'.format(player_name, platform)
		player_player_response_cache_key = '{}_{}_player_response'.format(player_name, platform)

		cached_platform_url = cache.get(player_platform_url_cache_key, None)

		if not cached_platform_url:
			platform_url = build_url(platform)
			cache.set(player_platform_url_cache_key, platform_url, 60)
		else:
			platform_url = cached_platform_url

		cached_player_url = cache.get(player_player_url_cache_key, None)

		if not cached_player_url:
			player_url = build_player_url(base_url=platform_url, player_name=player_name)
			cache.set(player_player_url_cache_key, player_url, 60)
		else:
			player_url = cached_player_url

		cached_player_response = cache.get(player_player_response_cache_key, None)
		
		if not cached_player_response:
			player_response = make_request(player_url)
			cache.set(player_player_response_cache_key, player_response, 60)
		else:
			player_response = cached_player_response

		ajax_data = {}

		if 'data' in player_response:

			player_id = player_response['data'][0]['id']

			ajax_data['player_id'] = player_id
			ajax_data['player_name']  = player_name

			perspective = correct_perspective(perspective)
			game_mode = correct_mode(game_mode)

			pool = multiprocessing.Pool(processes=2)
			pool.apply_async(get_player_matches, (platform_url, player_response, perspective, game_mode))
			pool.apply_async(retrieve_player_season_stats, (player_id,  platform))
			pool.close()
			pool.join()

		else:

			error = 'Sorry, looks like this player does not exist.'
			ajax_data['error'] = error

		return JsonResponse(ajax_data)

@csrf_exempt
def retrieve_matches(request):

	start_time = time.time()

	request_again = False
	redo_cache = False

	body = json.loads(request.body)
	
	player_id = body.get('player_id', None)
	perspective = body.get('perspective', None)
	game_mode = body.get('game_mode', None)

	player_cache_key = '{}_match_data'.format(player_id)

	ajax_data = {}

	cached_ajax_data = cache.get(player_cache_key, None)

	current_player = get_object_or_404(Player, api_id=player_id)
	player_names = set(list(Participant.objects.filter(player__api_id=player_id).values_list('player_name', flat=True)))

	if cached_ajax_data:

		cached_perspective = cached_ajax_data.get('perspective', None)
		cached_game_mode = cached_ajax_data.get('game_mode', None)
		cached_data = cached_ajax_data.get('data', None)

		if cached_perspective is None:
			cached_perspective = 'all'

		if cached_game_mode is None:
			cached_game_mode = 'all'

		if cached_perspective and correct_perspective(cached_perspective) != correct_perspective(perspective):
			request_again = True

		if cached_game_mode and correct_mode(cached_game_mode)  != correct_mode(game_mode):
			request_again = True

		if not request_again:

			kwargs = {}

			this_perspective = correct_perspective(perspective)
			this_game_mode = correct_mode(game_mode)

			if this_game_mode and this_perspective:
				mode_fiter = "{}-{}".format(this_game_mode, this_perspective)
				kwargs['rosterparticipant__roster__match__mode__iexact'] = mode_fiter
			elif this_game_mode:
				mode_fiter = this_game_mode
				kwargs['rosterparticipant__roster__match__mode__icontains'] = mode_fiter
			elif this_perspective:
				mode_fiter = this_perspective
				kwargs['rosterparticipant__roster__match__mode__icontains'] = mode_fiter

			kwargs['rosterparticipant__roster__participants__player_name__in'] = player_names
			kwargs['rosterparticipant__roster__match__api_id__icontains'] = player_id

			roster_data = Roster.objects.filter(
				**kwargs
			).order_by('-match__created').distinct()

			test_data = [
				{
					'map': roster.match.map.name if roster.match.map else None,
					'mode': roster.match.mode.upper(),
					'custom_match': 'Yes' if roster.match.is_custom_match else 'No',
					'date_created': datetime.strftime(roster.match.created, '%d/%m/%Y %H:%M'),
					'team_details': ''.join(["{}: {} kill(s) | {} damage<br>".format(x.player_name,x.kills,x.damage)for x in roster.participants.all()]),
					'team_placement': roster.placement
				} for roster in roster_data
			]

			if len(cached_data) != len(test_data):
				request_again = True
			
			if not request_again and cached_ajax_data:
				return JsonResponse(cached_ajax_data, safe=False)

	else:
		request_again = True

	if request_again:
		redo_cache = True

	print('> request_again ', request_again)

	if request_again:

		print('>> player_id = {} perspective = {} and game_mode = {} '.format(player_id, perspective, game_mode))

		if player_id and perspective and game_mode:
			
			roster_data = []
			message =  None

			kwargs = {}

			perspective = correct_perspective(perspective)
			game_mode = correct_mode(game_mode)

			if game_mode and perspective:
				mode_fiter = "{}-{}".format(game_mode, perspective)
				kwargs['rosterparticipant__roster__match__mode__iexact'] = mode_fiter
			elif game_mode:
				mode_fiter = game_mode
				kwargs['rosterparticipant__roster__match__mode__icontains'] = mode_fiter
			elif perspective:
				mode_fiter = perspective
				kwargs['rosterparticipant__roster__match__mode__icontains'] = mode_fiter

			kwargs['rosterparticipant__roster__participants__player_name__in'] = player_names
			kwargs['rosterparticipant__roster__match__api_id__icontains'] = player_id

			roster_data = Roster.objects.filter(**kwargs).order_by('-match__created').distinct()

			print(roster_data.exists())

			if roster_data and roster_data.exists():

				print('>>> roster_data exists')

				if game_mode and perspective:
					message = "<strong>{}</strong> {} {} matches returned in ".format(roster_data.count(), game_mode.upper(), perspective)
				elif game_mode:
					message = "<strong>{}</strong> TPP/FPP {} matches returned in ".format(roster_data.count(), game_mode.upper())
				elif perspective:
					message = "<strong>{}</strong> {} (SOLO, DUO, SQUAD) matches returned in ".format(roster_data.count(), perspective.upper())
				else:
					message = "<strong>{}</strong> TPP/FPP (SOLO, DUO, SQUAD) matches returned in ".format(roster_data.count())

				message = "{}<strong>{}</strong>(s)".format(message, "{0:.2f}".format(time.time() - start_time))

				ajax_data = {
					'perspective': perspective,
					'game_mode': game_mode,
					'message': message,
					'data':[
						{
							'map': roster.match.map.name if roster.match.map else None,
							'mode': roster.match.mode.upper(),
							'custom_match': 'Yes' if roster.match.is_custom_match else 'No',
							'date_created': datetime.strftime(roster.match.created, '%d/%m/%Y %H:%M'),
							'team_details': ''.join(["{}: {} kill(s) | {} damage<br>".format(x.player_name,x.kills,x.damage)for x in roster.participants.all()]),
							'team_placement': roster.placement
						} for roster in roster_data
					],
					'api_id': current_player.api_id
				}

				if cache.has_key(player_cache_key) and redo_cache:
					cache.delete(player_cache_key)

				if redo_cache:
					cache.set(player_cache_key, ajax_data, 60)

			else:

				print('>>> git log')

				if game_mode and perspective:
					message = "It would seem no {} {} matches exist for this user".format(game_mode.upper(), perspective)
				elif game_mode:
					message = "It would seem no TPP/FPP {} matches exist for this user".format(game_mode.upper())
				elif perspective:
					message = "It would seem no {} (SOLO, DUO, SQUAD) matches exist for this user".format(perspective.upper())
				else:
					message = "It would seem no TPP/FPP (SOLO, DUO, SQUAD) matches exist for this user"

				ajax_data = {
					'error': message,
					'api_id': current_player.api_id
				}

				print(ajax_data)

	else:

		ajax_data = cached_ajax_data

	

	return JsonResponse(ajax_data, safe=False)

@csrf_exempt
def retrieve_season_stats(request):
	
	print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
	print(request.body)
	print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')

	body = json.loads(request.body)

	player_id = body.get('player_id', None)
	perspective = body.get('perspective', None)
	platform = body.get('platform', None)

	player = get_object_or_404(Player, api_id=player_id)

	player_cache_key = '{}_season_data'.format(player_id)

	cached_ajax_data = cache.get(player_cache_key, None)

	print('>>> cached_ajax_data ', cached_ajax_data)

	redo = False

	if cached_ajax_data:
		perspective = correct_perspective(perspective)

		for x in cached_ajax_data:
			keys = x.keys() if x.keys() else None

			if keys:
				if perspective and perspective not in keys:
					redo = True
	else:
		redo = True

	print('>>> redo ', redo)
	if redo:
		
		perspective = correct_perspective(perspective)

		kwargs = {}
		exclude = {}

		if perspective and perspective == 'fpp':
			kwargs['mode__icontains'] = perspective
		elif perspective and perspective == 'tpp':
			exclude['mode__icontains'] = 'fpp'

		season_stats = PlayerSeasonStats.objects.filter(
			player=player,
			season__is_current=True,
			season__platform=platform,
			**kwargs
		).exclude(**exclude)

		ajax_data = []

		for x in season_stats:
			this_dict = {}

			mode = x.mode.lower().replace('-', '_')
			season_stat_key = '{}_season_stats'.format(mode)

			this_dict[season_stat_key] = {
				'{}_season_stats'.format(mode): correct_mode(mode.replace('_', ' ')),
				'{}_season_matches'.format(mode): "{} {}".format(x.rounds_played, 'Matches Played'),
				'{}_season_kills__text'.format(mode): 'Kills',
				'{}_season_kills__figure'.format(mode): x.kills,
				'{}_season_damage__text'.format(mode): 'Damage Dealt',
				'{}_season_damage__figure'.format(mode): str(x.damage_dealt),
				'{}_season_longest_kill__text'.format(mode): 'Longest Kill',
				'{}_season_longest_kill__figure'.format(mode): str(x.longest_kill),
				'{}_season_headshots__text'.format(mode): 'Headshot kills',
				'{}_season_headshots__figure'.format(mode): x.headshot_kills
			}

			ajax_data.append(this_dict)

		cache.set(player_cache_key, ajax_data, 60*20)

	else:
		ajax_data = cached_ajax_data

	return JsonResponse(ajax_data, safe=False)
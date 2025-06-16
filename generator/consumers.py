# generator/consumers.py

import json
import asyncio
import time
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.db.models import F
from .models import KahootGame, KahootPlayer

class KahootConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.game_pin = None
        self.game_group_name = None
        self.player = None
        self.start_time = 0
        self.answered_this_round = False

    async def connect(self):
        self.game_pin = self.scope['url_route']['kwargs']['game_pin']
        self.game_group_name = f'kahoot_{self.game_pin}'
        await self.channel_layer.group_add(self.game_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if self.player:
            await self.send_player_list_update()
        await self.channel_layer.group_discard(self.game_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        command = data.get('command')
        if command == 'join_game':
            await self.join_game(data.get('nickname'))
        elif command == 'start_game':
            await self.start_game()
        elif command == 'submit_answer':
            await self.submit_answer(data.get('answer'), data.get('question_index'))

    @sync_to_async
    def get_game(self):
        try:
            return KahootGame.objects.prefetch_related('questoes', 'players').get(pin=self.game_pin)
        except KahootGame.DoesNotExist:
            return None

    @sync_to_async
    def set_game_status(self, game, status):
        game.status = status
        game.save()

    @sync_to_async
    def create_player(self, game, nickname):
        player, created = KahootPlayer.objects.get_or_create(game=game, nickname=nickname)
        self.player = player

    @sync_to_async
    def get_leaderboard_data(self, game):
        players = game.players.order_by('-score').all()
        return [{'nickname': p.nickname, 'score': p.score} for p in players]

    @sync_to_async
    def update_score(self, points):
        # Atualiza a pontuação do jogador no banco de dados
        self.player.score = F('score') + points
        self.player.save()

    async def join_game(self, nickname):
        game = await self.get_game()
        if not game or game.status != 'waiting':
            await self.send_error("Não foi possível entrar no jogo. PIN inválido ou o jogo já começou.")
            return
        await self.create_player(game, nickname)
        await self.send_player_list_update()

    async def start_game(self):
        game = await self.get_game()
        if not game or game.status != 'waiting': return
        await self.set_game_status(game, 'in_progress')
        asyncio.create_task(self.run_game_loop())

    async def run_game_loop(self):
        game = await self.get_game()
        questions = list(game.questoes.all())
        for index, question in enumerate(questions):
            await sync_to_async(lambda: game.players.update())() # Place holder for streak logic
            self.answered_this_round = False
            await self.broadcast_question(question, index)
            await asyncio.sleep(question.tempo_limite)
            await self.broadcast_question_result(question)
            await asyncio.sleep(5)
            leaderboard = await self.get_leaderboard_data(game)
            await self.broadcast_leaderboard(leaderboard)
            await asyncio.sleep(8)
        await self.set_game_status(game, 'finished')
        await self.broadcast_game_over()

    async def submit_answer(self, answer, question_index):
        game = await self.get_game()
        if not self.player or question_index != game.current_question_index or self.answered_this_round:
            return
        self.answered_this_round = True
        question = game.questoes.all()[question_index]
        points = 0
        if answer == question.gabarito_me:
            time_taken = time.time() - self.start_time
            time_limit = question.tempo_limite
            score_reduction = 0.5 * (time_taken / time_limit)
            points = round(1000 * (1 - score_reduction))
            points = max(points, 0)
            await self.update_score(points)
        await self.send_personal_feedback(answer == question.gabarito_me, points)

    async def broadcast_question(self, question, index):
        self.start_time = time.time()
        game = await self.get_game()
        game.current_question_index = index
        await self.channel_layer.group_send(self.game_group_name, {
            'type': 'game.state.question', 'question_text': question.enunciado,
            'index': index, 'time_limit': question.tempo_limite,
        })
        
    async def broadcast_question_result(self, question):
        await self.channel_layer.group_send(self.game_group_name, {
            'type': 'game.state.result', 'correct_answer': question.gabarito_me
        })

    async def broadcast_leaderboard(self, leaderboard):
        await self.channel_layer.group_send(self.game_group_name, {
            'type': 'game.state.leaderboard', 'leaderboard': leaderboard
        })

    async def broadcast_game_over(self):
        leaderboard = await self.get_leaderboard_data(await self.get_game())
        await self.channel_layer.group_send(self.game_group_name, {
            'type': 'game.state.gameover', 'leaderboard': leaderboard
        })

    async def send_player_list_update(self):
        game = await self.get_game()
        players = await sync_to_async(list)(game.players.values_list('nickname', flat=True))
        await self.channel_layer.group_send(self.game_group_name, {
            'type': 'lobby.player.update', 'players': players
        })

    async def send_personal_feedback(self, is_correct, points):
        await self.send(text_data=json.dumps({
            'type': 'player.feedback', 'is_correct': is_correct, 'points_awarded': points
        }))

    async def send_error(self, message):
        await self.send(text_data=json.dumps({'type': 'error', 'message': message}))
    
    async def game_state_question(self, event): await self.send(text_data=json.dumps(event))
    async def game_state_result(self, event): await self.send(text_data=json.dumps(event))
    async def game_state_leaderboard(self, event): await self.send(text_data=json.dumps(event))
    async def game_state_gameover(self, event): await self.send(text_data=json.dumps(event))
    async def lobby_player_update(self, event): await self.send(text_data=json.dumps(event))
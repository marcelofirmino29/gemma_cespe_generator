# generator/consumers.py
import json
import asyncio
import time
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import KahootSession, KahootPlayer, Questao

class KahootConsumer(AsyncWebsocketConsumer):
    """
    Gerencia a lógica em tempo real do jogo Kahoot via WebSockets.
    """
    async def connect(self):
        self.session_code = self.scope['url_route']['kwargs']['session_code']
        self.game_group_name = f'kahoot_game_{self.session_code}'

        await self.channel_layer.group_add(self.game_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Lógica para remover o jogador se ele sair no meio do jogo
        await self.remove_player()
        await self.channel_layer.group_discard(self.game_group_name, self.channel_name)

    async def receive(self, text_data):
        """Recebe e direciona mensagens do frontend."""
        data = json.loads(text_data)
        handler = getattr(self, f"handle_{data.get('type')}", self.handle_unknown)
        await handler(data)

    async def handle_unknown(self, data):
        print(f"Tipo de mensagem desconhecido: {data.get('type')}")

    # --- Handlers de Ações ---

    async def handle_player_join(self, data):
        nickname = data.get('nickname')
        user_id = data.get('user_id') # Pode ser nulo para convidados
        player = await self.create_player(nickname, user_id)
        if player:
            await self.channel_layer.group_send(self.game_group_name, {
                'type': 'broadcast.player.joined',
                'nickname': player.nickname,
                'score': player.score
            })

    async def handle_start_game(self, data):
        await self.set_game_status('in_progress')
        await self.send_next_question()

    async def handle_next_question(self, data):
        await self.send_next_question()

    async def handle_submit_answer(self, data):
        score = await self.calculate_score(data)
        player_nickname = data.get('nickname')
        await self.update_player_score(player_nickname, score)
        await self.channel_layer.group_send(self.game_group_name, {
            'type': 'broadcast.player.answered',
            'nickname': player_nickname
        })

    # --- Lógica Principal do Jogo ---

    async def send_next_question(self):
        game_state = await self.get_game_state()
        if game_state['status'] != 'in_progress': return

        current_order = game_state['current_question_order']
        question_data = await self.get_question_by_order(current_order)

        if question_data:
            await self.channel_layer.group_send(self.game_group_name, {
                'type': 'broadcast.new.question',
                **question_data,
                'question_index': current_order,
                'total_questions': game_state['total_questions']
            })
            asyncio.create_task(self.end_question_period(question_data['id'], question_data['tempo_limite']))
        else:
            await self.end_game()

    async def end_question_period(self, question_id, delay):
        await asyncio.sleep(delay)
        correct_answer = await self.get_correct_answer(question_id)
        ranking = await self.get_ranking()

        await self.channel_layer.group_send(self.game_group_name, {
            'type': 'broadcast.question.result',
            'correct_answer': correct_answer,
            'ranking': ranking
        })
        await self.increment_question_order()

    async def end_game(self):
        await self.set_game_status('finished')
        ranking = await self.get_ranking()
        await self.channel_layer.group_send(self.game_group_name, {
            'type': 'broadcast.game.over',
            'final_ranking': ranking
        })

    # --- Métodos de Broadcast para o Grupo ---
    async def broadcast_player_joined(self, event): await self.send(text_data=json.dumps(event))
    async def broadcast_new_question(self, event): await self.send(text_data=json.dumps(event))
    async def broadcast_player_answered(self, event): await self.send(text_data=json.dumps(event))
    async def broadcast_question_result(self, event): await self.send(text_data=json.dumps(event))
    async def broadcast_game_over(self, event): await self.send(text_data=json.dumps(event))

    # --- Interações com o Banco de Dados (Async) ---
    @database_sync_to_async
    def create_player(self, nickname, user_id=None):
        session = KahootSession.objects.get(session_code=self.session_code)
        user = None
        if user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)

        player, created = KahootPlayer.objects.get_or_create(
            game_session=session, nickname=nickname,
            defaults={'user': user, 'score': 0, 'channel_name': self.channel_name}
        )
        return player if created else None

    @database_sync_to_async
    def remove_player(self):
        KahootPlayer.objects.filter(channel_name=self.channel_name).delete()
        # Adicionar lógica para notificar outros jogadores que alguém saiu

    @database_sync_to_async
    def calculate_score(self, data):
        try:
            question = Questao.objects.get(id=data['question_id'])
            if question.gabarito_ce.upper() == data['answer'].upper():
                time_limit = float(question.tempo_limite)
                time_taken = float(data.get('time_taken', time_limit))
                points = round((1 - (time_taken / (time_limit * 2))) * 1000)
                return max(0, points)
        except Questao.DoesNotExist:
            pass
        return 0

    @database_sync_to_async
    def update_player_score(self, nickname, points):
        try:
            player = KahootPlayer.objects.get(game_session__session_code=self.session_code, nickname=nickname)
            player.score += points
            player.save()
        except KahootPlayer.DoesNotExist:
            pass

    @database_sync_to_async
    def get_game_state(self):
        game = KahootSession.objects.select_related('kahoot_game').get(session_code=self.session_code)
        return {
            'status': game.status,
            'current_question_order': game.current_question_order,
            'total_questions': game.kahoot_game.questoes.count()
        }

    @database_sync_to_async
    def get_question_by_order(self, order):
        from .models import KahootGameQuestion
        try:
            relation = KahootGameQuestion.objects.select_related('questao').get(
                kahoot_game__sessions__session_code=self.session_code,
                order=order
            )
            q = relation.questao
            return {'id': q.id, 'enunciado': q.enunciado, 'tempo_limite': q.tempo_limite}
        except KahootGameQuestion.DoesNotExist:
            return None

    @database_sync_to_async
    def get_correct_answer(self, question_id):
        return Questao.objects.get(id=question_id).gabarito_ce

    @database_sync_to_async
    def get_ranking(self):
        players = KahootPlayer.objects.filter(game_session__session_code=self.session_code).order_by('-score')[:5]
        return [{'nickname': p.nickname, 'score': p.score} for p in players]

    @database_sync_to_async
    def increment_question_order(self):
        session = KahootSession.objects.get(session_code=self.session_code)
        session.current_question_order += 1
        session.save()

    @database_sync_to_async
    def set_game_status(self, status):
        session = KahootSession.objects.get(session_code=self.session_code)
        session.status = status
        session.save()

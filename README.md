
# Gerador de Questões IA (Estilo Cespe/Cebraspe e Discursivas) v1.0

## 📘 Descrição

O **Gerador de Questões IA** é uma aplicação web desenvolvida com Django e Python, projetada para auxiliar estudantes e professores na criação e resolução de questões de múltipla escolha (no formato Certo/Errado, similar ao Cebraspe) e questões discursivas, utilizando a API Google Generative AI (modelos Gemini/Gemma). Usuários cadastrados podem acompanhar seu desempenho via dashboard.

---

## ✅ Funcionalidades Implementadas

- **Geração de Questões Certo/Errado (C/E):**
  - Geração por tópico e dificuldade.
  - Gabarito (C/E) e justificativa automática.

- **Geração de Questões Discursivas:**
  - Com texto motivador, comando e aspectos.
  - Suporte a múltiplos idiomas.

- **Geração de Resposta Modelo (Discursiva):**
  - Dissertação modelo com base nos aspectos e área.

- **Validação de Respostas C/E:**
  - Usuário responde, sistema compara com gabarito.
  - Pontuação líquida ao estilo Cespe (acertos - erros).

- **Avaliação de Respostas Discursivas (Beta):**
  - Avaliação por aspecto, NC, NE e NPD.
  - Feedback textual e parsing automático dos dados.

- **Autenticação de Usuários:**
  - Cadastro, login, logout.
  - Proteção de views com `@login_required`.

- **Persistência de Dados:**
  - Modelos para áreas, questões, tentativas e avaliações.
  - Todas as interações são salvas.

- **Interface e Usabilidade:**
  - Responsivo (Bootstrap 5).
  - Tema claro/escuro automático.
  - Navegação intuitiva e rodapé fixo.

- **Dashboard de Desempenho:**
  - Estatísticas de acertos/erros e últimas tentativas.

---

## 🧱 Arquitetura Resumida (Django MVT)

- **Models:** Definem estrutura dos dados.
- **Views:** Lógica de negócio e integração com templates/API.
- **Templates:** Interface HTML com herança.
- **Forms:** Validação e estrutura dos formulários.
- **URLs:** Roteamento do app e projeto.
- **Services:** Integração com Google Generative AI.
- **Utils:** Funções auxiliares e parsers da IA.
- **Exceptions:** Erros personalizados.
- **Settings:** Configurações do Django, IA e segurança.
- **.env:** Variáveis sensíveis (API key, secret key, etc).

---

## 🛠 Tecnologias Utilizadas

- Python 3.10+
- Django 5.2+
- Google Generative AI SDK (`google-generativeai`)
- Bootstrap 5
- HTML5, CSS3, JavaScript
- SQLite (padrão)
- `python-dotenv`

---

## 📊 Modelagem de Dados

### Diagrama de Classes (Visual)

![Diagrama de Classes - Gerador IA](docs/diagrama_classes.svg)

> 💡 Coloque o arquivo `diagrama_classes.svg` na pasta `docs/` do seu projeto.

---

## 🧩 Casos de Uso Principais

**Ator Principal:** Usuário Cadastrado  
**Ator Secundário:** Serviço de IA (Google Generative AI)

- Gerenciar Conta (Registrar, Login, Logout, Mudar Senha)
- Gerar Questão C/E
- Gerar Questão Discursiva
- Gerar Resposta Modelo Discursiva
- Responder Questão C/E
- Validar Respostas C/E
- Responder Questão Discursiva
- Avaliar Resposta Discursiva
- Visualizar Desempenho (Dashboard)
- Selecionar Tema da Interface

---

## ⚙️ Instalação Local

### Pré-requisitos
- Python 3.10+
- Pip

### Passos

```bash
# Clonar o projeto
git clone [URL_DO_REPO]
cd [PASTA_DO_PROJETO]

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
. venv\Scripts\activate   # Windows

# Instalar dependências
pip install -r requirements.txt
```

### Criar `.env`

```env
GOOGLE_API_KEY=SUA_CHAVE_API_VALIDA_DO_GOOGLE_AI
DJANGO_SECRET_KEY=SUA_CHAVE_SECRETA_LONGA_E_ALEATORIA_PARA_DJANGO
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
```

### Migrate + Superusuário

```bash
python manage.py makemigrations generator
python manage.py migrate
python manage.py createsuperuser
```

### Executar

```bash
python manage.py runserver
```

Acesse: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## 🚀 Uso Básico

1. Acesse a aplicação.
2. Cadastre-se ou faça Login.
3. Gere questões (discursiva ou C/E).
4. Responda e envie para validação/avaliação.
5. Veja seu desempenho no dashboard.
6. Troque o tema se desejar.

---

## 🔐 Configurações Chave

- `.env`: `GOOGLE_API_KEY`, `DJANGO_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- `settings.py`: modelos IA, `LOGIN_REDIRECT_URL`, segurança, logging
- `services.py`: prompts e interações com IA
- `utils.py`: parsing da resposta da IA

---

## 🧨 Tratamento de Erros

- Exceções personalizadas em `exceptions.py`
- Try/catch nas views e serviços
- Logs configurados em `settings.py` com detalhamento

---

## ☁️ Deployment (Produção)

- Use Gunicorn/uWSGI com Nginx
- `DEBUG = False`
- `SECRET_KEY` única e segura
- Configurar `ALLOWED_HOSTS` corretamente
- Executar `collectstatic`
- Preferencialmente use PostgreSQL
- Habilitar HTTPS

---

## 📌 Próximos Passos / Melhorias Futuras

- Refinar parsers de resposta
- Adicionar gráficos e filtros ao dashboard
- Paginação do histórico
- Favoritar questões
- Melhorar mensagens de erro
- Configurar painel admin do Django
- Adicionar testes automatizados

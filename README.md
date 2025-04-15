# Gerador de Questões Certo/Errado (Estilo Cebraspe) com IA Generativa

![Screenshot da Aplicação](image_fb989a.png)
*(Substitua 'image_fb989a.png' pelo caminho correto se você adicionar a imagem ao repositório)*

## Descrição

Este é um projeto Django que utiliza a API Google Generative AI (com modelos como Gemini/Gemma) para gerar questões de múltipla escolha no estilo Certo/Errado, similar às aplicadas pela banca Cebraspe (anteriormente Cespe). O usuário fornece um tópico e o número de questões desejado, a IA gera as afirmações e seus respectivos gabaritos (Certo ou Errado). A aplicação permite ao usuário responder às questões geradas e verifica imediatamente as respostas, mostrando o resultado.

## Funcionalidades

* Geração de questões Certo/Errado baseadas em um tópico fornecido pelo usuário.
* Definição do número de questões a serem geradas (com limite configurável).
* Interface web para inserir o tópico e responder às questões geradas.
* Validação automática das respostas do usuário contra o gabarito gerado pela IA.
* Exibição clara dos resultados (acertos e erros).

## Tecnologias Utilizadas

* **Backend:** Python, Django
* **IA Generativa:** Google Generative AI API (Gemini/Gemma) - via biblioteca `google-generativeai`
* **Frontend:** HTML, CSS (Bootstrap 5), JavaScript (básico)
* **Ambiente:** Python Virtual Environment (`venv`)

## Pré-requisitos

* Python 3.10 ou superior
* Git
* Uma chave de API do Google AI Studio (anteriormente MakerSuite). Você pode obter uma em [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

## Instalação e Configuração

1.  **Clone o repositório:**
    ```bash
    git clone <URL_DO_SEU_REPOSITORIO_GITHUB>
    cd <NOME_DA_PASTA_DO_PROJETO> # Ex: gemma-cespe-generator
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv venv
    # Linux/Mac:
    source venv/bin/activate
    # Windows:
    # venv\Scripts\activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure a Chave da API (IMPORTANTE):**
    O projeto precisa da sua chave da API do Google AI para funcionar. **Não coloque sua chave diretamente no código que vai para o GitHub.** A melhor forma é usar variáveis de ambiente:
    * **Método 1 (Recomendado - Variável de Ambiente):**
        Defina uma variável de ambiente chamada `GOOGLE_API_KEY` com o valor da sua chave.
        * No Linux/Mac (temporário, para a sessão atual do terminal):
            ```bash
            export GOOGLE_API_KEY='SUA_CHAVE_API_AQUI'
            ```
        * No Windows (temporário, para a sessão atual do cmd):
            ```bash
            set GOOGLE_API_KEY=SUA_CHAVE_API_AQUI
            ```
        * No Windows (PowerShell):
            ```bash
            $env:GOOGLE_API_KEY="SUA_CHAVE_API_AQUI"
            ```
        * Para definir permanentemente, consulte a documentação do seu sistema operacional.
        * **Certifique-se que seu `settings.py` (ou `services.py`) está lendo a chave da variável de ambiente.** Exemplo em `settings.py`:
            ```python
            import os
            GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
            ```
            *Se seu código atual (services.py) lê `settings.GOOGLE_API_KEY`, então a linha acima deve estar no seu `settings.py`.*

    * **Método 2 (Arquivo .env):**
        * Instale `python-dotenv`: `pip install python-dotenv`
        * Crie um arquivo chamado `.env` na raiz do projeto (mesmo nível do `manage.py`).
        * Adicione a seguinte linha ao arquivo `.env`:
            ```dotenv
            GOOGLE_API_KEY=SUA_CHAVE_API_AQUI
            ```
        * **Certifique-se que o arquivo `.env` está listado no seu `.gitignore`!** (Já deve estar se você usou o exemplo anterior).
        * No topo do seu `settings.py`, adicione:
            ```python
            from dotenv import load_dotenv
            import os
            load_dotenv() # Carrega variáveis do .env
            GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
            ```

5.  **Execute as Migrações do Django (se houver modelos):**
    (Este projeto pode não ter modelos próprios, mas é uma boa prática)
    ```bash
    python manage.py migrate
    ```

6.  **Execute o Servidor de Desenvolvimento:**
    ```bash
    python manage.py runserver
    ```

## Uso

1.  Abra seu navegador e acesse `http://127.0.0.1:8000/` (ou a porta que o `runserver` indicar).
2.  Digite o Tópico/Assunto sobre o qual deseja gerar questões.
3.  Selecione o Número de Questões.
4.  Clique em "Gerar Questões".
5.  Aguarde a IA gerar as afirmações.
6.  Responda cada item marcando "Certo" ou "Errado".
7.  Clique em "Verificar Respostas".
8.  Veja o resultado da correção na própria página.

## Configurações Adicionais (settings.py)

Você pode ajustar alguns parâmetros da IA e da aplicação no arquivo `settings.py`:

* `GOOGLE_API_KEY`: Configurada via variável de ambiente (recomendado).
* `AI_MODEL_NAME`: Modelo do Google AI a ser usado (ex: `'gemini-1.5-flash-latest'`).
* `AI_GENERATION_TEMPERATURE`: Controla a "criatividade" da IA (0.0 a 1.0).
* `AI_MAX_QUESTIONS_PER_REQUEST`: Limite máximo de questões por pedido no formulário.
* `GOOGLE_AI_SAFETY_SETTINGS`: Configurações de segurança para a API (veja a documentação do Google AI).

## Contato

Marcelo Firmino - [seu-email@exemplo.com](mailto:seu-email@exemplo.com) *(Opcional)*

Link do Projeto: [https://github.com/seu-usuario/seu-repositorio](https://github.com/seu-usuario/seu-repositorio) *(Opcional)*

---

console.log("DEBUG: ce_validator.js está sendo executado NESTA PÁGINA!");
document.addEventListener('DOMContentLoaded', function() {
    const validateForm = document.getElementById('validate-form');
    // Pega a URL da view AJAX do atributo data-* do formulário
    const validateSingleUrl = validateForm ? validateForm.dataset.validateSingleUrl : null;
    // Pega o token CSRF do input hidden gerado pela tag {% csrf_token %}
    const csrfToken = validateForm ? validateForm.querySelector('input[name="csrfmiddlewaretoken"]')?.value : null;

    if (!validateForm || !validateSingleUrl || !csrfToken) {
        console.error("Formulário de validação, URL AJAX ou Token CSRF não encontrados.");
        return; // Sai se elementos essenciais não existem
    }

    // Adiciona listener para TODOS os botões "Verificar Item" dentro do formulário
    validateForm.addEventListener('click', function(event) {
        // Verifica se o elemento clicado é um botão de verificação individual
        if (event.target.classList.contains('verify-ce-btn')) {
            event.preventDefault(); // Impede qualquer ação padrão do botão
            const button = event.target;
            const questaoId = button.dataset.questaoId;
            const itemContainer = document.getElementById(`question-item-${questaoId}`); // Encontra o container do item
            const feedbackDiv = document.getElementById(`result-feedback-${questaoId}`); // Encontra a div de feedback

            if (!itemContainer || !feedbackDiv) {
                console.error(`Elementos não encontrados para questao_id ${questaoId}`);
                return;
            }

            // Encontra qual radio button está selecionado DENTRO do container do item
            const selectedRadio = itemContainer.querySelector(`input[name="resposta_q${questaoId}"]:checked`);

            if (!selectedRadio) {
                feedbackDiv.innerHTML = `<span class="text-warning">Por favor, selecione 'Certo' ou 'Errado' primeiro.</span>`;
                return; // Sai se nada foi selecionado
            }

            const userAnswer = selectedRadio.value;

            // Desabilita botão enquanto verifica
            button.disabled = true;
            button.innerHTML = `
                <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                Verificando...`;
            feedbackDiv.innerHTML = ''; // Limpa feedback anterior

            // Prepara dados para enviar como JSON
            const dataToSend = {
                questao_id: questaoId,
                user_answer: userAnswer
            };

            // Faz a requisição AJAX (Fetch API)
            fetch(validateSingleUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken, // Inclui o token CSRF no header
                    'X-Requested-With': 'XMLHttpRequest' // Header comum para identificar AJAX no Django
                },
                body: JSON.stringify(dataToSend) // Converte dados para string JSON
            })
            .then(response => {
                if (!response.ok) {
                    // Se a resposta não for OK (ex: 404, 500, 400), lança um erro
                    return response.json().then(errData => {
                         throw new Error(errData.error || `Erro HTTP: ${response.status}`);
                    });
                }
                return response.json(); // Decodifica a resposta JSON se OK
            })
            .then(result => {
                // Processa o resultado JSON recebido do backend
                let feedbackHtml = '';
                if (result.correct) {
                    feedbackHtml = `<span class="text-success fw-bold"><i class="bi bi-check-circle-fill"></i> Correto!</span>`;
                } else {
                    feedbackHtml = `<span class="text-danger fw-bold"><i class="bi bi-x-circle-fill"></i> Errado!</span> <span class="text-muted">(Gabarito: ${result.gabarito || '?'})</span>`;
                }

                if (result.justification) {
                    // Usa textContent para inserir a justificativa para evitar XSS
                    const justifP = document.createElement('p');
                    justifP.className = 'text-muted small mt-1 mb-0'; // Estilo similar ao da validação geral
                    justifP.textContent = `Justificativa: ${result.justification}`;
                    feedbackHtml += justifP.outerHTML; // Adiciona o HTML do parágrafo
                }

                feedbackDiv.innerHTML = feedbackHtml;

                // Desabilita radios e botão após verificar com sucesso
                itemContainer.querySelectorAll('input[type="radio"]').forEach(radio => radio.disabled = true);
                button.textContent = 'Verificado'; // Muda texto do botão (já está desabilitado)
                // Remove a classe original e adiciona uma classe indicando que foi verificado (opcional)
                button.classList.remove('btn-outline-primary');
                button.classList.add('btn-outline-secondary', 'disabled');


            })
            .catch(error => {
                console.error('Erro na validação AJAX:', error);
                feedbackDiv.innerHTML = `<span class="text-danger">Erro ao verificar: ${error.message || 'Tente novamente.'}</span>`;
                // Reabilita o botão em caso de erro para permitir nova tentativa? Ou deixa desabilitado?
                button.disabled = false; // Reabilita em caso de erro de comunicação/processamento
                button.innerHTML = 'Verificar Item';
            });
        }
    });

});
document.addEventListener('DOMContentLoaded', function () {
    console.log("[favorite_handler.js] DOM Carregado. Configurando listeners para FAVORITAR...");

    const allFavoriteForms = document.querySelectorAll('.toggle-favorite-form');
    // Log inicial para verificar se os formulários foram encontrados
    console.log(`[FAV_INIT] Encontrados ${allFavoriteForms.length} formulários com a classe '.toggle-favorite-form' na página.`);

    if (allFavoriteForms.length === 0) {
        console.warn("[FAV_INIT] ALERTA: NENHUM formulário '.toggle-favorite-form' foi encontrado. A funcionalidade de favoritar não será ativada. Verifique a classe nos seus formulários HTML e se o seletor está correto.");
    }

    allFavoriteForms.forEach((formElement, index) => {
        // Verifica se o elemento encontrado é realmente um formulário HTML
        if (!(formElement instanceof HTMLFormElement)) {
            console.error(`[FAV_INIT] ERRO: Elemento #${index} com classe '.toggle-favorite-form' NÃO é um HTMLFormElement. O listener não será anexado a este elemento. Elemento:`, formElement);
            return; // Pula para o próximo item do forEach
        }

        const formAction = formElement.action;
        const buttonInForm = formElement.querySelector('.favorite-btn'); // Busca o botão DENTRO do formElement atual
        
        if (!buttonInForm) {
            console.error(`[FAV_INIT][ERRO GRAVE] Formulário #${index} (Action: ${formAction}) NÃO POSSUI um botão com a classe '.favorite-btn'. O listener de 'submit' NÃO será anexado a este formulário, ou pode falhar.`);
            // Mesmo sem o botão, ainda tentamos anexar ao formulário, mas o clique pode não ter o efeito esperado se o botão for essencial para a lógica.
        }
        
        const questaoIdFromButton = buttonInForm ? buttonInForm.dataset.questaoId : 'ID NÃO ENCONTRADO (botão .favorite-btn ausente ou sem data-questao-id)';
        console.log(`[FAV_INIT] Tentando anexar listener SUBMIT ao Formulário #${index} para Questão ID [${questaoIdFromButton}], Action URL: ${formAction}`);

        formElement.addEventListener('submit', function(event) {
            // 1. Prevenir o comportamento padrão do formulário IMEDIATAMENTE
            event.preventDefault();
            console.log(`----------------------------------------------------`);
            console.log(`[FAV_CLICK] SUBMIT CAPTURADO! Formulário Action: ${this.action}. Default PREVENIDO.`);

            const currentForm = this; // 'this' é o formulário que disparou o evento 'submit'
            const url = currentForm.action;
            const formData = new FormData(currentForm);
            
            // Re-seleciona os elementos DENTRO do formulário atual para garantir o escopo correto
            const button = currentForm.querySelector('.favorite-btn');
            const icon = button ? button.querySelector('i.bi') : null; // Assumindo Bootstrap Icons
            const textSpan = button ? button.querySelector('.favorite-text') : null;
            const countSpan = button ? button.querySelector('.favorite-count') : null;
            const localQuestaoId = button ? button.dataset.questaoId : 'ID INDISPONÍVEL (botão não encontrado no submit)';

            console.log(`[FAV_CLICK] Iniciando FETCH para: ${url} (Questao ID do botão: ${localQuestaoId})`);
            
            // Verifica se todos os elementos da UI do botão foram encontrados
            if (!button || !icon || !textSpan || !countSpan) {
                console.error(`[FAV_CLICK][ERRO NO SCRIPT] Não foi possível encontrar todos os elementos visuais do botão de favoritar (ícone, texto, contagem) DENTRO do formulário para Questao ID ${localQuestaoId}. Formulário problemático:`, currentForm);
                // Não necessariamente impede o fetch, mas a UI não será atualizada corretamente.
                // Você pode decidir se quer parar aqui com um 'return;' ou continuar.
            } else {
                console.log(`[FAV_CLICK] Elementos visuais do botão para Questao ID ${localQuestaoId} encontrados.`);
            }

            fetch(url, {
                method: 'POST',
                body: formData,
                headers: { 
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken') // Pega o token do input hidden no formulário
                }
            })
            .then(response => {
                console.log(`[FAV_CLICK] Resposta FETCH para ${localQuestaoId} - Status: ${response.status}`);
                if (!response.ok) {
                    // Tenta extrair uma mensagem de erro mais detalhada do corpo da resposta
                    return response.text().then(text => {
                        try {
                            const errData = JSON.parse(text); // Tenta parsear como JSON
                            console.error(`[FAV_CLICK] Erro FETCH (JSON) para ${localQuestaoId}: ${response.statusText}. Detalhes:`, errData);
                            throw new Error(errData.error || errData.detail || `Erro HTTP: ${response.status}`);
                        } catch (e) {
                            console.error(`[FAV_CLICK] Erro FETCH (Texto) para ${localQuestaoId}: ${response.statusText}. Detalhes: ${text}`);
                            throw new Error(`Erro na requisição: ${response.statusText}. Resposta do servidor: ${text}`);
                        }
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log(`[FAV_CLICK] Dados JSON para ${localQuestaoId}:`, data);
                
                // Somente tenta atualizar a UI se os elementos do botão foram encontrados
                if (button && icon && textSpan && countSpan) {
                    if (data.is_favorited) {
                        button.classList.remove('btn-outline-warning'); 
                        button.classList.add('btn-warning');
                        icon.classList.remove('bi-star'); 
                        icon.classList.add('bi-star-fill');
                        if(textSpan) textSpan.textContent = 'Desfavoritar';
                    } else {
                        button.classList.remove('btn-warning'); 
                        button.classList.add('btn-outline-warning');
                        icon.classList.remove('bi-star-fill'); 
                        icon.classList.add('bi-star');
                        if(textSpan) textSpan.textContent = 'Favoritar';
                    }
                    if(countSpan) countSpan.textContent = data.count;
                    console.log(`[FAV_CLICK] UI atualizada para ${localQuestaoId}.`);
                } else {
                    console.warn(`[FAV_CLICK] Elementos da UI do botão para ${localQuestaoId} não foram completamente encontrados. A UI pode não ter sido atualizada.`);
                }
            })
            .catch(error => {
                console.error(`[FAV_CLICK] Erro CATCH no Fetch ou processamento para ${localQuestaoId}:`, error);
                alert('Ocorreu um erro ao tentar favoritar/desfavoritar. Veja o console para detalhes.');
            });
        });
        // Log para confirmar que o listener foi anexado
        console.log(`[FAV_INIT] Listener SUBMIT ANEXADO com sucesso ao Formulário #${index} para Questão ID [${questaoIdFromButton}]`);
    });

    if (allFavoriteForms.length > 0) {
        console.log("[FAV_INIT] Todos os listeners para favoritar foram configurados (ou tentativas foram feitas).");
    }
});

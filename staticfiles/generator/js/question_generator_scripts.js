// static/generator/js/question_generator_scripts.js

// Espera o DOM carregar completamente
document.addEventListener('DOMContentLoaded', function() {

    // Lógica do botão de Loading para o formulário de GERAÇÃO
    const genForm = document.getElementById('generator-form');
    const genSubmitButton = document.getElementById('submit-button');
    const genLoadingSpinner = document.getElementById('loading-spinner');
    const genButtonText = document.getElementById('button-text');
    // Pega o estado inicial do botão (se foi desabilitado pelo Django via contexto)
    const genButtonInitiallyDisabled = genSubmitButton ? genSubmitButton.disabled : true;

    if (genForm && genSubmitButton && genLoadingSpinner && genButtonText && !genButtonInitiallyDisabled) {
        genForm.addEventListener('submit', function(event) {
            // Opcional: Adicionar validação JS aqui se a validação HTML5 não for suficiente
            // if (!genForm.checkValidity()) {
            //     event.preventDefault(); // Impede envio
            //     // Adicionar feedback visual de erro
            //     return;
            // }
            // Desabilita botão e mostra spinner ao enviar
            genSubmitButton.disabled = true;
            genLoadingSpinner.style.display = 'inline-block';
            genButtonText.textContent = ' Gerando...';
        });
    }

    // Reseta o botão de GERAÇÃO se o usuário voltar usando o histórico do navegador
    window.addEventListener('pageshow', function (event) {
        // Só reabilita se ele não estava desabilitado inicialmente (serviço inativo)
        if (event.persisted && genSubmitButton && !genButtonInitiallyDisabled) {
             genSubmitButton.disabled = false;
             genLoadingSpinner.style.display = 'none';
             genButtonText.textContent = 'Gerar Questões';
        }
    });

    // Lógica para o botão "Verificar Respostas" (se precisar de spinner nele também)
    // Se o formulário de validação tiver um ID, podemos adicionar aqui. Ex: id="validate-form"
    const validateForm = document.querySelector('form[action*="validate_answers"]'); // Encontra pelo action
    if (validateForm) {
        const validateSubmitButton = validateForm.querySelector('button[type="submit"]');
        if (validateSubmitButton) {
             // Simplesmente desabilita ao clicar para evitar duplo clique
             validateForm.addEventListener('submit', function() {
                 setTimeout(() => { validateSubmitButton.disabled = true; }, 10); // Pequeno delay
                 // Poderia adicionar um spinner aqui também se a validação demorar
             });
        }
    }

}); // Fim do DOMContentLoaded
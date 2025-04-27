// Script loading button (Gerar Questão)
// Precisa garantir que serviceInitialized seja acessível globalmente ou passado de outra forma
// Se não for, remover a dependência ou usar um data attribute no botão.
// Assumindo que serviceInitialized pode não estar disponível aqui diretamente:
document.addEventListener('DOMContentLoaded', function() { // Garante que o DOM carregou

    const examForm = document.getElementById('discursive-exam-form');
    const examSubmitButton = document.getElementById('submit-discursive-exam');
    const examLoadingSpinner = document.getElementById('loading-spinner-discursive-exam');
    const examButtonText = document.getElementById('button-text-discursive-exam');
    // Tentativa de ler do contexto global (menos ideal) ou de um atributo data-*
    // const serviceInitialized = window.serviceInitialized || true; // Default true se não definido
    // Melhor: verificar apenas se o botão *deve* estar desabilitado pelo Django no HTML
    const initiallyDisabled = examSubmitButton ? examSubmitButton.disabled : true;


    if (examForm && examSubmitButton && examLoadingSpinner && examButtonText && !initiallyDisabled) {
        examForm.addEventListener('submit', function(event) {
            // Validação HTML5 básica pode ser adicionada aqui se necessário
            examSubmitButton.disabled = true;
            examLoadingSpinner.style.display = 'inline-block';
            examButtonText.textContent = ' Gerando Questão...';
        });
    }

    // Reseta botão ao voltar com histórico do navegador (se não estiver desabilitado inicialmente)
     window.addEventListener('pageshow', function (event) {
        if (event.persisted && examSubmitButton && !initiallyDisabled) {
             examSubmitButton.disabled = false;
             examLoadingSpinner.style.display = 'none';
             examButtonText.textContent = 'Gerar Questão Discursiva';
        }
    });

    // Função para copiar texto
    // Tornando global ou encapsulando de forma acessível ao `onclick`
    window.copyToClipboard = function() { // Anexa ao objeto window para ficar acessível
        const content = document.getElementById('markdown-content');
        if (content) {
            navigator.clipboard.writeText(content.innerText)
                .then(() => { alert('Texto da questão copiado!'); })
                .catch(err => { console.error('Erro ao copiar: ', err); alert('Erro ao copiar.'); });
        }
    }

    // Script Contagem de Palavras e Linhas
    const textArea = document.getElementById('user_answer_text');
    const wordCountFeedback = document.getElementById('word-count-feedback');
    const lineCountInput = document.getElementById('line_count_input');

    if (textArea && wordCountFeedback && lineCountInput) {
        textArea.addEventListener('input', function() {
            const text = textArea.value;
            const trimmedText = text.trim();
            const words = trimmedText === '' ? 0 : trimmedText.split(/\s+/).length;
            const lines = text === '' ? 0 : (text.match(/\n/g) || []).length + 1;

            wordCountFeedback.textContent = `Contagem de palavras: ${words}`;
            lineCountInput.value = lines; // Atualiza valor do input hidden
        });
        // Dispara contagem inicial se houver texto pré-carregado
         if(textArea.value) {
             textArea.dispatchEvent(new Event('input'));
         }
    }

    // Código para renderizar Markdown (se usar Marked.js) - Opcional
    // const markdownContent = document.getElementById('markdown-content');
    // if (markdownContent && typeof marked !== 'undefined') {
    //     const rawMarkdown = markdownContent.textContent || markdownContent.innerText;
    //     // Atenção: isso pode ter implicações de segurança (XSS) se o markdown vier de fonte não confiável
    //     // Use DOMPurify ou configuração segura do Marked.js se necessário
    //     markdownContent.innerHTML = marked.parse(rawMarkdown);
    // }

}); // Fim do DOMContentLoaded
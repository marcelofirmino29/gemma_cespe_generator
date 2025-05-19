// Função de copiar texto (mantida do seu original)
function copyRenderedText(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        let textToCopy = element.innerText || element.textContent;
        navigator.clipboard.writeText(textToCopy.trim())
        .then(() => {
            alert('Texto da questão copiado para a área de transferência!');
        })
        .catch(err => {
            console.error('Erro ao copiar texto: ', err);
            alert('Falha ao copiar o texto.');
        });
    } else {
        console.error(`Elemento com ID '${elementId}' não encontrado para cópia.`);
        alert('Erro: Não foi possível encontrar o texto para copiar.');
    }
}

document.addEventListener('DOMContentLoaded', function() {
    console.log("PÁGINA CONFIGURAR SIMULADO: DOM Carregado.");

    const configForm = document.getElementById('config-simulado-form');

});
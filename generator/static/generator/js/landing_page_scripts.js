// static/generator/js/landing_page_scripts.js

document.addEventListener('DOMContentLoaded', function() {
    const wordsDataElement = document.getElementById('word-cloud-data');
    let words = [];
    if (wordsDataElement) {
        try { words = JSON.parse(wordsDataElement.textContent); } catch (e) {
            console.error("Erro ao analisar os dados da nuvem de palavras:", e);
            words = ["Erro", "nos", "dados"]; // Fallback
        }
    } else {
        console.warn("Elemento 'word-cloud-data' não encontrado.");
        words = ["Dados", "não", "encontrados"]; // Fallback
    }

    if (!Array.isArray(words)) {
        console.warn("Os dados da nuvem de palavras não são um array:", words);
        words = []; // Fallback para array vazio
    }

    const colors = ['text-primary', 'text-secondary', 'text-success', 'text-danger', 'text-warning', 'text-info', 'text-dark', 'text-primary-emphasis', 'text-success-emphasis', 'text-info-emphasis'];
    const fontSizes = ['wc-size-1', 'wc-size-2', 'wc-size-3', 'wc-size-4', 'wc-size-5', 'wc-size-6'];
    const container = document.getElementById('wordCloudContainer');

    if (!container) {
        console.error("Container da nuvem de palavras ('wordCloudContainer') não encontrado!");
        return;
    }
    container.innerHTML = ''; // Limpa a mensagem "Carregando palavras..."

    function getRandomElement(arr) {
        if (!arr || arr.length === 0) return '';
        return arr[Math.floor(Math.random() * arr.length)];
    }

    // Embaralha as palavras para uma aparência mais aleatória a cada carregamento
    if (words.length > 0) {
        words.sort(() => Math.random() - 0.5);
    }

    words.forEach((wordText, index) => {
        if (typeof wordText !== 'string' || wordText.trim() === '') {
            console.warn(`Item inválido ou vazio nos dados da nuvem na posição ${index}:`, wordText);
            return; // Pula itens inválidos
        }
        const wordElement = document.createElement('span');
        const randomColor = getRandomElement(colors);
        const randomSize = getRandomElement(fontSizes);

        wordElement.classList.add('word-cloud-item');
        if (randomColor) wordElement.classList.add(randomColor);
        if (randomSize) wordElement.classList.add(randomSize);
        wordElement.classList.add('fw-medium'); // Bootstrap 5 font weight

        const cleanWordText = wordText.trim();
        wordElement.textContent = cleanWordText;

        const randomDelay = Math.random() * 5; // Atraso aleatório para a animação
        wordElement.style.animationDelay = `${randomDelay}s`;

        wordElement.addEventListener('click', function() {
            const question = `Defina ${cleanWordText} no contexto de Tecnologia da Informação`;
            const encodedQuestion = encodeURIComponent(question);

            // Verifica se askAiBaseUrl está definida (deve ser definida no HTML)
            if (typeof askAiBaseUrl !== 'undefined' && askAiBaseUrl) {
                const targetUrl = `${askAiBaseUrl}?question=${encodedQuestion}`;
                window.location.href = targetUrl;
            } else {
                console.error("A variável 'askAiBaseUrl' não está definida. Certifique-se de que ela está definida no HTML antes deste script.");
            }
        });
        container.appendChild(wordElement);
    });

    // Mensagem de fallback se nenhuma palavra for renderizada
    if (container.childElementCount === 0) {
        let fallbackMessage = 'Nenhum tópico em destaque disponível no momento.';
        if (wordsDataElement === null || (wordsDataElement && !Array.isArray(JSON.parse(wordsDataElement.textContent || '[]')))) {
             fallbackMessage = 'Erro ao carregar os tópicos em destaque ou dados inválidos.';
        }
        container.textContent = fallbackMessage;
        container.classList.add('text-muted', 'text-center', 'fst-italic', 'p-4');
    }
});
document.addEventListener('DOMContentLoaded', function() {
    console.log("PÁGINA UPLOAD PDF: DOM carregado.");

    // Tenta obter o ID do elemento de forma segura, caso 'form' ou 'pdf_file' não existam
    // Isso é um pouco complexo porque o ID é gerado pelo Django.
    // Uma forma mais robusta no JS seria passar o ID do Django para o JavaScript.
    // Por ora, vamos assumir que você consegue obter o ID no template e, se não, terá que ajustá-lo.
    // A forma mais segura é passar o ID para o JavaScript através de um atributo de dados ou uma variável global.
    // No entanto, para manter simples e direto da sua estrutura atual:

    // IMPORTANTE: A linha abaixo depende de como 'form.pdf_file.id_for_label' é renderizado no HTML.
    // Se o template não renderizar essa variável específica no escopo global do JS,
    // você precisará de uma abordagem diferente para obter o ID do input, como:
    // const pdfFileInput = document.querySelector('input[type="file"][name="{{ form.pdf_file.name }}"]');
    // ou adicionar um ID fixo ao elemento no template se `id_for_label` for problemático.

    // Para este exemplo, vamos assumir que o ID do seu template é 'id_pdf_file' se o id_for_label não for encontrado
    // Isso pode precisar ser ajustado baseado no HTML renderizado final.
    const pdfFileInputId = document.querySelector('input[name="{{ form.pdf_file.html_name }}"]')?.id || 'id_pdf_file';
    const pdfFileInput = document.getElementById(pdfFileInputId);


    if (pdfFileInput) {
        pdfFileInput.addEventListener('change', function(event) {
            if (event.target.files.length > 0) {
                console.log("PÁGINA UPLOAD PDF: Arquivo selecionado:", event.target.files[0].name);
            } else {
                console.log("PÁGINA UPLOAD PDF: Seleção de arquivo removida.");
            }
        });
    } else {
        // Se o seletor acima não funcionar devido à renderização do Django, você pode tentar um seletor mais genérico
        // ou garantir que o ID seja previsível ou passado para o JS.
        // Por exemplo, se o campo sempre tem um nome específico:
        // const pdfFileInputByName = document.querySelector('input[name="pdf_file"]'); // Ajuste o 'name' se for diferente
        // if (pdfFileInputByName) { /* ... adicionar event listener ... */ } else {
        // console.warn(`PÁGINA UPLOAD PDF: Campo de input PDF ('${pdfFileInputId}') não encontrado. Verifique o ID/seletor no HTML.`);
        // }
        console.warn("PÁGINA UPLOAD PDF: Campo de input PDF não encontrado. Verifique o seletor.");
    }

    const validationForm = document.getElementById('validate-form');
    if (validationForm) {
        console.log("PÁGINA UPLOAD PDF: Formulário '#validate-form' (para itens C/E) encontrado.");

        const radioButtons = validationForm.querySelectorAll('.question-radio');
        if (radioButtons.length > 0) {
            console.log("PÁGINA UPLOAD PDF: " + radioButtons.length + " radio buttons (.question-radio) encontrados.");
            radioButtons.forEach(function(radio) {
                radio.addEventListener('click', function(e) {
                    console.log('DEBUG (UPLOAD PAGE): Radio button clicado:', e.target.id, 'Valor:', e.target.value, 'Name:', e.target.name, 'Checked:', e.target.checked);
                });
            });
        } else {
            console.warn("PÁGINA UPLOAD PDF: NENHUM radio button (.question-radio) encontrado dentro do #validate-form.");
        }

        const verifyButtons = validationForm.querySelectorAll('.verify-ce-btn');
        if (verifyButtons.length > 0) {
            console.log("PÁGINA UPLOAD PDF: " + verifyButtons.length + " botão(ões) '.verify-ce-btn' encontrado(s) DENTRO do #validate-form.");
        } else {
            console.warn("PÁGINA UPLOAD PDF: Formulário '#validate-form' encontrado, mas NENHUM botão '.verify-ce-btn'.");
        }
    } else if (document.querySelector('.verify-ce-btn')) {
         console.warn("PÁGINA UPLOAD PDF: Botões '.verify-ce-btn' encontrados, mas o formulário com id '#validate-form' NÃO foi encontrado. ce_validator.js provavelmente falhará.");
    } else {
        console.log("PÁGINA UPLOAD PDF: Formulário '#validate-form' (para itens C/E) NÃO encontrado. Isso é esperado se nenhuma questão C/E foi gerada ainda.");
    }

    // Lembre-se de adicionar console.log DENTRO do seu arquivo ce_validator.js
    // para depurar o fluxo interno dele, como sugerido anteriormente.
});
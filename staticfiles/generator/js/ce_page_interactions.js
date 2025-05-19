document.addEventListener('DOMContentLoaded', function() {
    console.log("PÁGINA GERADOR C/E (JS externo): DOM Carregado.");

    const generatorForm = document.getElementById('generator-form');
    // Use os IDs que você espera que sejam renderizados (provavelmente os valores 'default' do template)
    const topicTextarea = document.getElementById('id_topic');
    const pdfUploadInput = document.getElementById('id_pdf_contexto_ce_page');
    const topicLabel = document.getElementById('label_for_topic_ce_page');
    const helpTextForTopic = document.getElementById('help_text_for_topic_ce_page');
    const helpTextForPdf = document.getElementById('help_text_for_pdf_ce_page');
    // Assumindo que o ID do campo de área é 'id_area' (do default no template)
    const areaGeneratorField = document.getElementById('id_area');


    function updateInputRequirements() {
        if (!topicTextarea || !pdfUploadInput || !topicLabel || !helpTextForTopic || !helpTextForPdf) {
            console.warn("Gerador C/E: Elementos para obrigatoriedade condicional (Tópico/PDF) não encontrados.");
            return;
        }

        const isPdfSelected = pdfUploadInput.files && pdfUploadInput.files.length > 0;
        const isTopicFilled = topicTextarea.value.trim() !== "";

        // Ler textos de ajuda dos atributos data-*
        const helpTopicOptional = helpTextForTopic.dataset.helpOptional || "Contexto textual opcional quando um PDF é enviado.";
        const helpTopicEditing = helpTextForTopic.dataset.helpEditing || "Continue editando seu contexto textual.";
        const helpTopicRequired = helpTextForTopic.dataset.helpRequired || "Digite ou cole o texto base. Obrigatório se nenhum PDF for enviado.";

        const helpPdfSelected = helpTextForPdf.dataset.pdfSelected || "PDF selecionado. O Tópico textual é opcional.";
        const helpPdfOptional = helpTextForPdf.dataset.pdfOptional || "Se preferir, envie um PDF. (O Tópico textual é obrigatório se nenhum PDF for fornecido).";


        if (isPdfSelected) {
            topicTextarea.required = false;
            topicLabel.classList.remove('required');
            helpTextForTopic.textContent = helpTopicOptional;
            helpTextForPdf.textContent = helpPdfSelected;
        } else {
            topicTextarea.required = true;
            if (isTopicFilled) {
                topicLabel.classList.remove('required');
                helpTextForTopic.textContent = helpTopicEditing;
            } else {
                topicLabel.classList.add('required');
                helpTextForTopic.textContent = helpTopicRequired;
            }
            helpTextForPdf.textContent = helpPdfOptional;
        }
    }

    if (pdfUploadInput) {
        pdfUploadInput.addEventListener('change', updateInputRequirements);
    }
    if (topicTextarea) {
        topicTextarea.addEventListener('input', updateInputRequirements);
    }

    // Assegura que o estado inicial da classe 'required' no label e o required do textarea estejam corretos
    if (topicLabel && topicTextarea && pdfUploadInput) { // Adicionado pdfUploadInput para evitar erro se não existir
        if (!(pdfUploadInput.files && pdfUploadInput.files.length > 0) && topicTextarea.value.trim() === '') {
            topicLabel.classList.add('required');
            topicTextarea.required = true;
        } else {
            topicTextarea.required = !(pdfUploadInput.files && pdfUploadInput.files.length > 0);
            if (!topicTextarea.required) {
                topicLabel.classList.remove('required');
            }
        }
    }
    // Chamada inicial para configurar o estado correto, mas apenas se os elementos existirem
    if (topicTextarea && pdfUploadInput && topicLabel && helpTextForTopic && helpTextForPdf) {
        updateInputRequirements();
    }


    const submitButton = document.getElementById('submit-button');
    const loadingSpinner = document.getElementById('loading-spinner');
    const buttonTextSpan = document.getElementById('button-text'); // Renomeado para evitar confusão com a variável buttonText

    if (generatorForm && submitButton && loadingSpinner && buttonTextSpan) {
        generatorForm.addEventListener('submit', function(event) {
            // Validar novamente se os elementos existem antes de acessar 'files' ou 'value'
            const isPdfSelected = pdfUploadInput && pdfUploadInput.files && pdfUploadInput.files.length > 0;
            const isTopicFilled = topicTextarea && topicTextarea.value.trim() !== "";

            if (!isPdfSelected && !isTopicFilled) {
                alert("Por favor, forneça um Tópico/Contexto Textual ou envie um arquivo PDF para gerar questões.");
                event.preventDefault();
                return;
            }
            if (areaGeneratorField && areaGeneratorField.value === "") {
                alert("Por favor, selecione uma Área de Conhecimento para as novas questões.");
                event.preventDefault();
                return;
            }
            submitButton.disabled = true;
            loadingSpinner.classList.remove('d-none');
            buttonTextSpan.textContent = ' Gerando...'; // Atualiza o texto dentro do span 'button-text'
        });
    }
    
    // O restante do seu JavaScript (Search DB, validação, etc.) iria aqui,
    // também ajustado para não usar tags de template Django diretamente.
    // Por exemplo, o script do botão "Buscar no Banco":
    const searchDbButton = document.getElementById('search-db-button');
    // Assumindo que os IDs para os campos de busca são 'id_topic' e 'id_area'
    const areaSelectForSearch = document.getElementById('id_area');
    const topicInputForSearch = document.getElementById('id_topic');


    if (searchDbButton && topicInputForSearch && areaSelectForSearch) {
        searchDbButton.addEventListener('click', function(event) {
            event.preventDefault();
            const topicValue = topicInputForSearch.value.trim();
            const areaValue = areaSelectForSearch.value;

            const baseUrl = searchDbButton.href.split('?')[0]; // searchDbButton.href já terá a URL resolvida pelo Django
            const params = new URLSearchParams();
            if (topicValue) { params.append('q', topicValue); }
            if (areaValue) { params.append('area', areaValue); }
            let finalUrl = baseUrl;
            const queryString = params.toString();
            if (queryString) { finalUrl += '?' + queryString; }
            console.log('Redirecionando para busca no banco com filtros do Gerador C/E:', finalUrl);
            window.location.href = finalUrl;
        });
    } else {
        console.warn("Elementos para 'Buscar no Banco' não encontrados. Verifique os IDs: #search-db-button, id_topic, id_area");
    }

    // Depuração para botões 'Verificar Item' (se esta lógica estiver neste arquivo)
    // const validationFormResults = document.getElementById('validate-form');
    // if(validationFormResults){
    //     // ...
    // }
});
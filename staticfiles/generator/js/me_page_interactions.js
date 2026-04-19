document.addEventListener('DOMContentLoaded', function() {
    console.log("PÁGINA GERADOR ME (JS externo): DOM Carregado.");

    const generatorForm = document.getElementById('generator-form-me');
    const topicTextarea = document.getElementById('id_topic');
    const pdfUploadInput = document.getElementById('id_pdf_contexto_me_page');
    const topicLabel = document.getElementById('label_for_topic_me_page');
    const helpTextForTopic = document.getElementById('help_text_for_topic_me_page');
    const helpTextForPdf = document.getElementById('help_text_for_pdf_me_page');
    const areaGeneratorField = document.getElementById('id_area');

    function updateInputRequirements() {
        if (!topicTextarea || !pdfUploadInput || !topicLabel || !helpTextForTopic || !helpTextForPdf) {
            console.warn("Gerador ME: Elementos para obrigatoriedade condicional (Tópico/PDF) não encontrados.");
            return;
        }

        const isPdfSelected = pdfUploadInput.files && pdfUploadInput.files.length > 0;
        const isTopicFilled = topicTextarea.value.trim() !== "";

        const helpTopicOptional = helpTextForTopic.dataset.helpOptional || "Contexto textual opcional quando um PDF é enviado.";
        const helpTopicEditing = helpTextForTopic.dataset.helpEditing || "Continue editando seu contexto textual.";
        const helpTopicRequired = helpTextForTopic.dataset.helpRequired || "Digite ou cole o texto base. Obrigatório se nenhum PDF for enviado.";

        const helpPdfSelected = helpTextForPdf.dataset.pdfSelected || "PDF selecionado. O Tópico textual é opcional.";
        const helpPdfOptional = helpTextForPdf.dataset.pdfOptional || "Se preferir, envie um PDF. (O Tópico textual é obrigatório se nenhum PDF for fornecido).";

        if (isPdfSelected) {
            // PDF presente => tópico opcional
            topicTextarea.required = false;
            topicLabel.classList.remove('required');
            helpTextForTopic.textContent = helpTopicOptional;
            helpTextForPdf.textContent = helpPdfSelected;
        } else {
            // Sem PDF => tópico obrigatório
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

    // Estado inicial
    if (topicLabel && topicTextarea && pdfUploadInput) {
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

    if (topicTextarea && pdfUploadInput && topicLabel && helpTextForTopic && helpTextForPdf) {
        updateInputRequirements();
    }

    const submitButton = document.getElementById('submit-button-me');
    const loadingSpinner = document.getElementById('loading-spinner-me');
    const buttonTextSpan = document.getElementById('button-text-me');

    if (generatorForm && submitButton && loadingSpinner && buttonTextSpan) {
        generatorForm.addEventListener('submit', function(event) {
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
            buttonTextSpan.textContent = ' Gerando...';
        });
    }
});
document.addEventListener('DOMContentLoaded', function() {
    console.log("PÁGINA GERADOR ME: DOM carregado.");

    const generatorForm = document.getElementById('generator-form-me');
    const topicTextarea = document.getElementById('id_topic');
    const pdfUploadInput = document.getElementById('id_pdf_contexto_me_page');
    const topicLabel = document.getElementById('label_for_topic_me_page');
    const helpTextForTopic = document.getElementById('help_text_for_topic_me_page');
    const helpTextForPdf = document.getElementById('help_text_for_pdf_me_page');
    const areaGeneratorField = document.getElementById('id_area');

    function updateInputRequirements() {
        if (!topicTextarea || !pdfUploadInput || !topicLabel || !helpTextForTopic || !helpTextForPdf) {
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
    updateInputRequirements();

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

    function getCsrfToken() {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const c = cookies[i].trim();
            if (c.startsWith('csrftoken=')) {
                return c.substring('csrftoken='.length, c.length);
            }
        }
        return null;
    }

    const csrfToken = getCsrfToken();

    function sendMeAnswerAjax(questaoId, alternativa, btn) {
        if (!csrfToken) {
            console.warn("CSRF token não encontrado. AJAX ME não será enviado.");
            return;
        }

        const url = window.URL_VALIDATE_ME || '/validate-single-me/';

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                questao_id: questaoId,
                user_answer: alternativa
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.warn("Erro retorno ME:", data.error);
                if (btn) btn.disabled = false;
                return;
            }

            const card = document.getElementById(`question-item-me-${questaoId}`);
            if (card) {
                card.classList.remove('border-success', 'border-danger');
                card.classList.add(data.correct ? 'border-success' : 'border-danger');
            }

            const feedbackContainer = document.getElementById(`feedback-me-${questaoId}`);
            const badge = document.getElementById(`badge-me-${questaoId}`);
            const justificativaP = document.getElementById(`justificativa-me-${questaoId}`);

            if (badge && feedbackContainer) {
                badge.className = 'badge ' + (data.correct ? 'bg-success' : 'bg-danger');
                badge.textContent = data.correct
                    ? `Acertou! Gabarito: ${data.gabarito}`
                    : `Errou. Gabarito: ${data.gabarito}`;
                feedbackContainer.classList.remove('d-none');
            }

            if (justificativaP) {
                justificativaP.textContent = data.justification || '';
                justificativaP.classList.remove('d-none');
            }

            const radios = document.querySelectorAll(`input[name="resposta_q${questaoId}"]`);
            radios.forEach(r => r.disabled = true);
            if (btn) btn.disabled = true;
        })
        .catch(err => {
            console.error("Falha AJAX ME:", err);
            if (btn) btn.disabled = false;
        });
    }

    document.addEventListener('change', function(ev) {
        const target = ev.target;
        if (!target.classList.contains('form-check-input')) return;
        if (target.type !== 'radio') return;

        const name = target.name;
        if (!name || !name.startsWith('resposta_q')) return;

        const questaoId = name.replace('resposta_q', '');
        const btn = document.getElementById(`btn-responder-${questaoId}`);
        if (btn) {
            btn.disabled = false;
        }
    });

    document.addEventListener('click', function(ev) {
        const btn = ev.target.closest('button[id^="btn-responder-"]');
        if (!btn) return;

        const questaoId = btn.dataset.questaoId;
        if (!questaoId) return;

        const radios = document.querySelectorAll(`input[name="resposta_q${questaoId}"]`);
        let alternativa = null;
        radios.forEach(r => {
            if (r.checked) alternativa = r.value;
        });

        if (!alternativa) {
            alert('Selecione uma alternativa antes de responder.');
            return;
        }

        btn.disabled = true;
        sendMeAnswerAjax(questaoId, alternativa, btn);
    });
});
function copyRenderedText(event, elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        let textToCopy = element.innerText || element.textContent;
        navigator.clipboard.writeText(textToCopy.trim())
        .then(() => {
            const copyButton = event.target.closest('button');
            if (copyButton) {
                const originalButtonText = copyButton.innerHTML;
                copyButton.innerHTML = '<i class="bi bi-check-lg me-1"></i>Copiado!';
                copyButton.disabled = true;
                setTimeout(() => {
                    copyButton.innerHTML = originalButtonText;
                    copyButton.disabled = false;
                }, 2000);
            }
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
    const form = document.getElementById('discursive-exam-form');
    const submitButton = document.getElementById('submit-discursive-exam');
    const spinner = document.getElementById('loading-spinner-discursive-exam');
    const buttonText = document.getElementById('button-text-discursive-exam');
    const resetButton = document.getElementById('reset-discursive-form');
    const printButton = document.getElementById('printDiscursiveQuestionBtn');

    if (form && submitButton && spinner && buttonText) {
        form.addEventListener('submit', function() {
            // Verifica se os campos obrigatórios (ou pelo menos um deles) estão preenchidos
            const topicTextarea = document.getElementById('id_base_topic_discursive'); // Use o ID real do seu textarea
            const pdfInput = document.getElementById('id_pdf_file_discursive'); // Use o ID real do seu input de PDF

            let topicValue = topicTextarea ? topicTextarea.value.trim() : '';
            let pdfFile = pdfInput ? pdfInput.files.length > 0 : false;

            if (topicValue === '' && !pdfFile) {
                // alert('Por favor, forneça um tópico ou envie um arquivo PDF.');
                // Você pode optar por não desabilitar o botão ou mostrar uma mensagem de erro mais integrada
                // Em vez de um alert, você poderia adicionar uma mensagem de erro no formulário.
                // Por agora, vamos permitir o envio para que a validação do Django ocorra.
            } else {
                spinner.classList.remove('d-none');
                buttonText.classList.add('d-none');
                submitButton.disabled = true;
            }
        });
    }
    if(resetButton) {
        resetButton.addEventListener('click', function() {
            if(form) {
                form.reset(); // Reseta a maioria dos campos

                // Limpeza específica para campos que o form.reset() pode não limpar bem ou para UI
                const pdfInput = document.getElementById('id_pdf_file_discursive');
                if(pdfInput) pdfInput.value = null;

                const baseTopicTextarea = document.getElementById('id_base_topic_discursive'); // Use o ID real
                if(baseTopicTextarea) baseTopicTextarea.value = '';
            }

            const generatedContentContainer = document.querySelector('.generated-exam-container');
            if(generatedContentContainer) generatedContentContainer.style.display = 'none';

            // Ocultar mensagens de erro/sucesso
            const alerts = document.querySelectorAll('.alert.alert-dismissible');
             alerts.forEach(alertEl => {
                 const bsAlert = bootstrap.Alert.getInstance(alertEl);
                 if (bsAlert) {
                     bsAlert.close();
                 } else {
                     // Fallback se a instância do Alert não for encontrada (ex: se já foi removido do DOM por outro script)
                     // ou se você não quer depender da instância do Alert para fechar.
                     // alertEl.style.display = 'none'; // Simplesmente oculta
                     alertEl.remove(); // Remove do DOM
                 }
             });
        });
    }

    if (printButton) {
        printButton.addEventListener('click', function() {
            window.print();
        });
    }
});
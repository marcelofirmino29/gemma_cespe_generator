document.addEventListener('DOMContentLoaded', function () {
    const realSelect = document.getElementById('search-area');
    const customDropdownBtn = document.getElementById('custom-area-filter-btn');

    if (!realSelect || !customDropdownBtn) {
        return;
    }

    const dropdownMenu = customDropdownBtn.nextElementSibling;
    if (!dropdownMenu) {
        return;
    }

    const customDropdownBtnText = customDropdownBtn.querySelector('.btn-text');
    const areaCheckboxContainers = dropdownMenu.querySelectorAll('.dropdown-item-text');

    function updateDropdownButtonText() {
        if (!customDropdownBtnText) return;

        const selectedOptions = Array.from(realSelect.options).filter(option => option.selected);
        if (selectedOptions.length === 0) {
            customDropdownBtnText.textContent = 'Selecione área(s)';
        } else if (selectedOptions.length === 1) {
            customDropdownBtnText.textContent = selectedOptions[0].text;
        } else {
            customDropdownBtnText.textContent = selectedOptions.length + ' áreas selecionadas';
        }
    }

    areaCheckboxContainers.forEach(function (container) {
        const checkbox = container.querySelector('.area-checkbox');
        if (!checkbox) return;

        checkbox.addEventListener('change', function () {
            const value = this.value;
            const correspondingOption = realSelect.querySelector('option[value="' + value + '"]');
            if (correspondingOption) {
                correspondingOption.selected = this.checked;
            }
            updateDropdownButtonText();
        });

        container.addEventListener('click', function (e) {
            if (e.target !== checkbox) {
                checkbox.checked = !checkbox.checked;
                const event = new Event('change', { bubbles: true });
                checkbox.dispatchEvent(event);
            }
        });
    });

    updateDropdownButtonText();

    const printButton = document.getElementById('printQuestionsBtn');
    if (printButton) {
        printButton.addEventListener('click', function () {
            window.print();
        });
    }

    const validateForm = document.getElementById('validate-form');
    const validateUrl = validateForm ? validateForm.dataset.validateSingleUrl : null;
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    const csrfToken = csrfInput ? csrfInput.value : '';

    document.querySelectorAll('.verify-me-btn').forEach(function (button) {
        button.addEventListener('click', async function () {
            const questaoId = this.dataset.questaoId;
            const questionContainer = document.getElementById('question-item-' + questaoId);
            const feedbackDiv = document.getElementById('result-feedback-' + questaoId);

            if (!questionContainer || !feedbackDiv || !validateUrl) {
                return;
            }

            const selectedAnswer = questionContainer.querySelector('input[name="resposta_q' + questaoId + '"]:checked');

            if (!selectedAnswer) {
                feedbackDiv.className = 'me-result-feedback mt-2 small text-warning';
                feedbackDiv.textContent = 'Selecione uma alternativa antes de verificar.';
                return;
            }

            const originalButtonHtml = this.innerHTML;
            this.disabled = true;
            this.innerHTML = '<i class="bi bi-hourglass-split"></i> Verificando...';

            try {
                const response = await fetch(validateUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({
                        questao_id: questaoId,
                        user_answer: selectedAnswer.value
                    })
                });

                const data = await response.json();

                if (!response.ok || data.error) {
                    feedbackDiv.className = 'me-result-feedback mt-2 small text-danger';
                    feedbackDiv.textContent = data.error || 'Erro ao validar a questão.';
                    return;
                }

                if (data.correct) {
                    feedbackDiv.className = 'me-result-feedback mt-2 small text-success fw-bold';
                    feedbackDiv.innerHTML = '✓ Resposta correta!';
                } else {
                    feedbackDiv.className = 'me-result-feedback mt-2 small text-danger fw-bold';
                    feedbackDiv.innerHTML = '✗ Errou. Gabarito: ' + data.gabarito;
                }

                if (data.justification) {
                    feedbackDiv.innerHTML += '<br><span class="fw-normal text-light">' + data.justification + '</span>';
                }

            } catch (error) {
                feedbackDiv.className = 'me-result-feedback mt-2 small text-danger';
                feedbackDiv.textContent = 'Falha de comunicação com o servidor.';
                console.error('Erro ao validar item ME:', error);
            } finally {
                this.disabled = false;
                this.innerHTML = originalButtonHtml;
            }
        });
    });
});
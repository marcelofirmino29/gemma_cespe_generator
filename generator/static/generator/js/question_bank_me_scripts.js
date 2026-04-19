document.addEventListener('DOMContentLoaded', function () {
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const csrftoken =
        document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
        getCookie('csrftoken') ||
        '';

    const realSelect = document.getElementById('search-area');
    const customDropdownBtn = document.getElementById('custom-area-filter-btn');

    if (realSelect && customDropdownBtn) {
        const dropdownMenu = customDropdownBtn.nextElementSibling;
        const customDropdownBtnText = customDropdownBtn.querySelector('.btn-text');
        const areaCheckboxContainers = dropdownMenu ? dropdownMenu.querySelectorAll('.dropdown-item-text') : [];

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
                const correspondingOption = realSelect.querySelector(`option[value="${value}"]`);
                if (correspondingOption) {
                    correspondingOption.selected = this.checked;
                }
                updateDropdownButtonText();
            });

            container.addEventListener('click', function (e) {
                if (e.target !== checkbox) {
                    checkbox.checked = !checkbox.checked;
                    checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
        });

        updateDropdownButtonText();
    }

    const printButton = document.getElementById('printQuestionsBtn');
    if (printButton) {
        printButton.addEventListener('click', function () {
            window.print();
        });
    }

    const validateForm = document.getElementById('validate-form');
    const validateUrl = validateForm ? validateForm.dataset.validateSingleUrl : null;

    document.querySelectorAll('.verify-me-btn').forEach(function (button) {
        button.addEventListener('click', async function () {
            const questaoId = this.dataset.questaoId;
            const container = document.getElementById(`question-item-${questaoId}`);
            const feedback = document.getElementById(`result-feedback-${questaoId}`);

            if (!container || !feedback || !validateUrl) {
                return;
            }

            const selected = container.querySelector(`input[name="resposta_q${questaoId}"]:checked`);
            if (!selected) {
                feedback.className = 'me-result-feedback mt-2 small text-warning';
                feedback.textContent = 'Selecione uma alternativa antes de verificar.';
                return;
            }

            this.disabled = true;
            const originalText = this.innerHTML;
            this.innerHTML = '<i class="bi bi-hourglass-split"></i> Verificando...';

            try {
                const response = await fetch(validateUrl, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrftoken,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({
                        questao_id: questaoId,
                        user_answer: selected.value
                    })
                });

                const data = await response.json();

                if (!response.ok || data.error) {
                    feedback.className = 'me-result-feedback mt-2 small text-danger';
                    feedback.textContent = data.error || 'Erro ao validar a questão.';
                    return;
                }

                feedback.className = data.correct
                    ? 'me-result-feedback mt-2 small text-success fw-bold'
                    : 'me-result-feedback mt-2 small text-danger fw-bold';

                feedback.textContent = data.correct
                    ? '✔ Resposta correta!'
                    : `✘ Errou. Gabarito: ${data.gabarito}`;

                let justificationBox = container.querySelector('.me-justification-box');

                if (!justificationBox) {
                    justificationBox = document.createElement('div');
                    justificationBox.className = 'me-justification-box mt-2 small text-light';
                    feedback.insertAdjacentElement('afterend', justificationBox);
                }

                if (data.justification && data.justification.trim() !== '') {
                    justificationBox.textContent = data.justification;
                    justificationBox.style.display = 'block';
                } else {
                    justificationBox.textContent = '';
                    justificationBox.style.display = 'none';
                }

            } catch (error) {
                feedback.className = 'me-result-feedback mt-2 small text-danger';
                feedback.textContent = 'Falha de comunicação com o servidor.';
                console.error('Erro ao validar questão ME:', error);
            } finally {
                this.disabled = false;
                this.innerHTML = originalText;
            }
        });
    });
});
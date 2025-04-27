// Espera o DOM carregar completamente
document.addEventListener('DOMContentLoaded', function() {

    // Encontra o elemento canvas do gráfico
    const chartCanvas = document.getElementById('acertosErrosChart');

    // Só executa se o canvas existir na página
    if (chartCanvas) {
        // Lê os dados dos atributos data-*
        // dataset lê 'data-acertos' como 'acertos' (camelCase implícito)
        const acertosData = chartCanvas.dataset.acertos; 
        const errosData = chartCanvas.dataset.erros;

        // Converte os dados para números inteiros (importante!)
        const acertos = parseInt(acertosData) || 0; // Usa 0 se a conversão falhar
        const erros = parseInt(errosData) || 0;

        // Verifica se temos dados válidos para exibir
        if (acertos >= 0 && erros >= 0 && (acertos + erros > 0) ) {
            
            const ctx = chartCanvas.getContext('2d');

            // Configuração do Gráfico de Rosca (Doughnut) - Mesma de antes
            const acertosErrosChart = new Chart(ctx, {
                type: 'doughnut', 
                data: {
                    labels: [
                        'Acertos',
                        'Erros'
                    ],
                    datasets: [{
                        label: 'Distribuição C/E',
                        data: [acertos, erros],
                        backgroundColor: [
                            'rgba(25, 135, 84, 0.7)',  // Verde (Bootstrap Success com alpha)
                            'rgba(220, 53, 69, 0.7)'   // Vermelho (Bootstrap Danger com alpha)
                        ],
                        borderColor: [
                            'rgba(25, 135, 84, 1)',
                            'rgba(220, 53, 69, 1)'
                        ],
                        borderWidth: 1,
                        hoverOffset: 4 
                    }]
                },
                options: {
                    responsive: true, 
                    maintainAspectRatio: false, 
                    plugins: {
                        legend: {
                            position: 'bottom', 
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    let label = context.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.parsed !== null) {
                                        // Calcula percentual
                                        const total = context.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                                        const value = context.parsed;
                                        const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                        label += `${value} (${percentage}%)`;
                                    }
                                    return label;
                                }
                            }
                        }
                    }
                }
            });
        } else {
            // Opcional: Mostrar uma mensagem se não há dados, mesmo que o canvas exista
            console.log("Não há dados suficientes (acertos/erros > 0) para exibir o gráfico.");
        }
    } else {
        // Opcional: Log se o canvas não for encontrado
        console.log("Elemento canvas 'acertosErrosChart' não encontrado.");
    }
});
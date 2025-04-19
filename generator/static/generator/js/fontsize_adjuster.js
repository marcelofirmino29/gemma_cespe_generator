// static/generator/js/fontsize_adjuster.js
document.addEventListener('DOMContentLoaded', function() {
     const decreaseButton = document.getElementById('decrease-font');
     const resetButton = document.getElementById('reset-font');
     const increaseButton = document.getElementById('increase-font');
     const bodyElement = document.body; // Ou document.documentElement se preferir mudar o root
 
     const baseFontSize = 16; // Defina o tamanho base em pixels (ou pegue do CSS inicial)
     let currentMultiplier = 1; // Multiplicador inicial (1 = 100%)
     const step = 0.1; // Quanto aumentar/diminuir a cada clique (10%)
     const minMultiplier = 0.8; // Mínimo (ex: 80%)
     const maxMultiplier = 1.5; // Máximo (ex: 150%)
     const storageKey = 'fontSizeMultiplier';
 
     // Função para aplicar o tamanho da fonte
     const applyFontSize = (multiplier) => {
         const newSize = baseFontSize * multiplier;
         bodyElement.style.fontSize = `${newSize}px`;
         // Opcional: Ajustar line-height proporcionalmente
         // bodyElement.style.lineHeight = (1.5 * multiplier); // Exemplo
         console.log(`Font size set to ${newSize}px (Multiplier: ${multiplier})`);
     };
 
     // Função para salvar a preferência
     const savePreference = (multiplier) => {
         try {
             localStorage.setItem(storageKey, multiplier);
         } catch (e) {
             console.error("Could not save font size preference:", e);
         }
     };
 
     // Função para carregar a preferência
     const loadPreference = () => {
         try {
             const savedMultiplier = localStorage.getItem(storageKey);
             if (savedMultiplier !== null) {
                 currentMultiplier = parseFloat(savedMultiplier);
                 // Garante que o multiplicador carregado esteja dentro dos limites
                 currentMultiplier = Math.max(minMultiplier, Math.min(maxMultiplier, currentMultiplier));
             }
         } catch (e) {
             console.error("Could not load font size preference:", e);
         }
         applyFontSize(currentMultiplier); // Aplica ao carregar
     };
 
     // Adiciona listeners aos botões
     if (decreaseButton) {
         decreaseButton.addEventListener('click', () => {
             if (currentMultiplier > minMultiplier) {
                 currentMultiplier = Math.max(minMultiplier, currentMultiplier - step);
                 applyFontSize(currentMultiplier);
                 savePreference(currentMultiplier);
             }
         });
     }
 
     if (resetButton) {
         resetButton.addEventListener('click', () => {
             currentMultiplier = 1; // Reseta para 100%
             applyFontSize(currentMultiplier);
             savePreference(currentMultiplier);
         });
     }
 
     if (increaseButton) {
         increaseButton.addEventListener('click', () => {
             if (currentMultiplier < maxMultiplier) {
                 currentMultiplier = Math.min(maxMultiplier, currentMultiplier + step);
                 applyFontSize(currentMultiplier);
                 savePreference(currentMultiplier);
             }
         });
     }
 
     // Carrega a preferência salva quando a página carrega
     loadPreference();
 });
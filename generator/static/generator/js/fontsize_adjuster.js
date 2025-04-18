(() => {
    'use strict';
    console.log("Inicializando script de ajuste de fonte (fontsize_adjuster.js)...");
  
    const storageKey = 'fontSizePreference';
    const htmlElement = document.documentElement;
    const fontSizes = [0.8, 0.9, 1.0, 1.1, 1.2];
    const defaultSizeIndex = fontSizes.indexOf(1.0);
  
    const applyFontSize = (index) => {
      console.log(`applyFontSize chamado com índice: ${index}`);
      const safeIndex = Math.max(0, Math.min(index, fontSizes.length - 1));
      console.log(`Índice seguro calculado: ${safeIndex}`);
      const multiplier = fontSizes[safeIndex];
      const newStyle = `${multiplier * 100}%`;
      console.log(`Aplicando estilo: font-size: ${newStyle}`);
      try { htmlElement.style.fontSize = newStyle; console.log("Estilo aplicado com sucesso ao <html>."); }
      catch (e) { console.error("Erro ao aplicar estilo fontSize:", e); }
      try { localStorage.setItem(storageKey, safeIndex); console.log(`Índice ${safeIndex} salvo no localStorage.`); }
      catch (e) { console.error("Erro ao salvar no localStorage:", e); }
      const decreaseBtn = document.getElementById('decrease-font');
      const increaseBtn = document.getElementById('increase-font');
      if (decreaseBtn) decreaseBtn.disabled = (safeIndex === 0);
      if (increaseBtn) increaseBtn.disabled = (safeIndex === fontSizes.length - 1);
    };
  
    const getCurrentSizeIndex = () => {
        const storedIndex = localStorage.getItem(storageKey);
        console.log(`Índice lido do localStorage: ${storedIndex}`);
        if (storedIndex !== null && !isNaN(parseInt(storedIndex)) && parseInt(storedIndex) >= 0 && parseInt(storedIndex) < fontSizes.length) {
             const parsedIdx = parseInt(storedIndex); console.log(`Retornando índice do localStorage: ${parsedIdx}`); return parsedIdx;
        }
        console.log(`Retornando índice padrão: ${defaultSizeIndex}`); return defaultSizeIndex;
    };
  
    document.addEventListener('DOMContentLoaded', () => {
         console.log("DOM carregado (fontsize_adjuster.js). Configurando listeners...");
         const decreaseButton = document.getElementById('decrease-font');
         const resetButton = document.getElementById('reset-font');
         const increaseButton = document.getElementById('increase-font');
         if (!decreaseButton || !resetButton || !increaseButton) { console.error("ERRO: Botões de fonte não encontrados!"); return; }
         console.log("Botões de fonte encontrados.");
         let currentSizeIndex = getCurrentSizeIndex();
         console.log(`Aplicando tamanho inicial (DOM ready) para índice: ${currentSizeIndex}`);
         applyFontSize(currentSizeIndex);
         decreaseButton.addEventListener('click', () => { console.log("Botão A- clicado!"); currentSizeIndex = getCurrentSizeIndex(); applyFontSize(currentSizeIndex - 1); });
         resetButton.addEventListener('click', () => { console.log("Botão A clicado!"); applyFontSize(defaultSizeIndex); });
         increaseButton.addEventListener('click', () => { console.log("Botão A+ clicado!"); currentSizeIndex = getCurrentSizeIndex(); applyFontSize(currentSizeIndex + 1); });
         console.log("Listeners de ajuste de fonte adicionados.");
    });
  
  })();
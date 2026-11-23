# Roteiro de 5 minutos

**0:00–0:45 — Problema (Mecânica).** "Uma moto com escapamento adulterado passando de madrugada na Sete de Setembro acorda o quarteirão inteiro. Para o sono, cada pico conta. A OMS recomenda menos de 45 dB à noite. Hoje a fiscalização depende de um agente com decibelímetro, e quando passam duas motos ninguém sabe qual foi."

**0:45–1:30 — Solução e física (Mecânica → Elétrica).** Mostrar a arquitetura: microfones + câmera no poste → MQTT → painel → agente. Explicar a física: soma de fontes (90 + 90 = 93 dB) e −6 dB por dobro de distância. Por isso o nível é corrigido para 7,5 m. Hardware: 16 microfones MEMS sincronizados numa barra de 90 cm.

**1:30–3:30 — Demonstração ao vivo (Computação).** Rodar `streamlit run app.py`.
1. Cena "Duas motos em faixas diferentes": arrastar o slider de quadros e mostrar que o feixe quente **segue a Moto A**. Ela recebe AUTUAÇÃO SUGERIDA com 94 dB, e a Moto B fica OK.
2. Cena "lado a lado (corredor)": o caso vai para REVISÃO HUMANA. "Na dúvida, não autua."
3. Aba Eventos: mostrar o JSON e clicar em Publicar MQTT (ou mostrar `eventos.jsonl`).

**3:30–4:30 — Resultados (Computação + Mecânica).** Teste com 100 cenas aleatórias: 0% de multa errada e 0% de infrator perdido. Os casos duvidosos (cerca de metade) vão para revisão humana. Antes x depois: o número de picos por noite cai 60% e o Lnight cai cerca de 4 dB.

**4:30–5:00 — Limitações e futuro.** Tudo é simulado. Os próximos passos são calibração real, um conjunto 2D, OCR de placas e homologação pelo INMETRO.

---
## "E se tiver duas motos na foto?"
"O microfone não ouve só *quanto* barulho tem, ele ouve **de onde** o barulho vem. O som chega a cada microfone com microssegundos de diferença, e pela diferença de tempo calculamos a direção. Essa direção é desenhada sobre a imagem da câmera, como um mapa de calor.
Depois, conferimos três coisas:
1. **Direção:** o feixe quente cai em cima de qual moto.
2. **Movimento:** em 8 quadros, o ponto quente precisa **acompanhar a mesma moto**. Se ele seguir outra trajetória, não vale.
3. **Separação:** se as duas motos estiverem na mesma direção, lado a lado no corredor, o sistema **não escolhe**. O caso vai para revisão humana com foto e áudio.
Na simulação com duas motos aleatórias, nenhuma moto inocente foi multada."

**Perguntas prováveis**
- *Por que não usar um decibelímetro só?* Ele mede o nível, mas não diz de quem é o som.
- *Mede dB(A)?* A banda de 300 a 3000 Hz aproxima a ponderação A. A calibração real fica como trabalho futuro.
- *Carro ruidoso?* O mesmo sistema funciona. O limite é por nível, e o espectro ajuda a classificar.

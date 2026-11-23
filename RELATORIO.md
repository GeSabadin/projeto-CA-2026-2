# Radar de Ruído para Motos com Escapamento Adulterado — Curitiba

**Disciplina:** Ciências do Ambiente — UTFPR · **Equipe:** Computação, Elétrica/Automação, Mecânica
**Poluição combatida:** sonora (foco em saúde, sono e qualidade de vida)

## 1. Problema
Em vias com muito movimento noturno, como a Av. Sete de Setembro e a Av. Batel, motos com escapamento adulterado produzem **picos de ruído** que acordam moradores. Para o sono, o **número de picos** pesa tanto quanto o nível médio. A OMS (Environmental Noise Guidelines, 2018) recomenda, para o tráfego rodoviário, Lnight < 45 dB.
A fiscalização atual depende do agente de trânsito com decibelímetro, ou seja, é pontual e rara. Além disso, quando passam duas motos juntas, o decibelímetro não diz **qual delas** fez o barulho.

**Base normativa** (os números precisam ser conferidos na fonte antes da entrega):
- ABNT NBR 10151:2019: avaliação do ruído em áreas habitadas, com limites diurno e noturno por tipo de área.
- CTB, art. 230, XI: proíbe conduzir veículo com descarga livre ou com silenciador defeituoso, deficiente ou inoperante.
- Resoluções do CONAMA sobre limites de ruído de veículos e lei municipal de ruído de Curitiba (Lei 10.625/2002).

## 2. Solução
Um radar de ruído instalado num poste, formado por um **conjunto linear de 16 microfones MEMS** (0,9 m de abertura) e uma **câmera**:
1. **Detecta** passagens com nível acima do limite (padrão: 80 dB a 7,5 m, ajustável).
2. **Localiza a fonte** por beamforming (delay-and-sum calculado a partir da correlação cruzada GCC entre os 120 pares de microfones). O resultado é um mapa de calor sobreposto à cena, a chamada câmera acústica. Paris testa um sistema desse tipo (Méduse).
3. **Atribui o som a um veículo:** o feixe é apontado para cada veículo detectado pela câmera. Uma deconvolução no estilo DAMAS (mínimos quadrados não negativos) separa a parte do som de cada um e remove o "vazamento" da moto barulhenta para a vizinha.
4. **Confirma pelo movimento:** o pico acústico precisa acompanhar o veículo ao longo de vários quadros (8 quadros em 1,05 s).
5. **Na dúvida, não autua.** Os casos ambíguos vão para revisão humana. O sistema só *sugere* a autuação, e quem decide é o agente de trânsito.
6. **Publica o evento por MQTT** (JSON) no tópico `cwb/radar-ruido/{radar_id}/eventos` para o painel da fiscalização.

**Regras de decisão:**

| Situação | Decisão |
|---|---|
| Nível < limite − margem | OK |
| Outro veículo dentro da largura do feixe em todos os quadros | REVISÃO HUMANA (fonte ambígua) |
| Veículo sem pico acústico próprio, ao lado de outro bem mais ruidoso | OK (o som é do vizinho) |
| Menos de 3 quadros válidos, ou pico que não acompanha o veículo | REVISÃO HUMANA |
| Nível dentro da margem de incerteza | REVISÃO HUMANA |
| Nível > limite + margem, com rastreamento consistente | AUTUAÇÃO SUGERIDA |

## 3. Especialidades
- **Computação:** simulação acústica em Python (numpy/scipy), localização da fonte (GCC + beamforming), classificação por nível e espectro (fração de energia entre 1,5 e 3 kHz e estouros), rastreamento, MQTT e painel em Streamlit.
- **Elétrica/Automação:** hardware (16 MEMS I2S + Raspberry Pi/ESP32 + câmera), sincronização dos microfones (a simulação mostra o efeito do erro de sincronismo) e posicionamento no poste. Protótipo no Wokwi.
- **Mecânica:** física da acústica (nível de pressão sonora, soma de fontes em dB, −6 dB por dobro de distância), estimativa do Lnight na fachada e da população afetada.

## 4. Marcos (CDIO)
- **M1 — Conceber:** problema, normas e arquitetura (radar → MQTT → painel → agente).
- **M2 — Desenhar:** cenário noturno estimado na via. Projeto do conjunto de microfones: 16 microfones com espaçamento de 6 cm, sem aliasing espacial até cerca de 2,9 kHz, e largura de feixe de cerca de 17° a 1,5 kHz.
- **M3 — Implementar:** `radar_core.py` (simulação e decisão), `visual.py`, `app.py` (painel) e `mqtt_pub.py`.
- **M4 — Operar:** demonstração com duas motos na cena, acurácia por Monte Carlo e impacto antes x depois.

## 5. Resultados (simulação)
**Cenas de demonstração:**
- Duas motos em faixas diferentes: a moto adulterada (94 dB) recebe **AUTUAÇÃO SUGERIDA** e a normal fica **OK**.
- Duas motos lado a lado no corredor: a barulhenta vai para **REVISÃO HUMANA**, porque as duas estão na mesma direção e não dá para ter certeza.
- Moto adulterada + carro + moto normal: só a moto adulterada é autuada.
- Só motos normais: nenhum evento.

**Monte Carlo** (100 cenas aleatórias com 2 motos, uma adulterada e uma normal, cerca de 1/3 delas no corredor):

| Configuração | Acerto | Revisão humana | Infrator perdido | Multa errada |
|---|---|---|---|---|
| 16 microfones | 51% | 49% | 0% | **0%** |
| 8 microfones (50 cenas) | 54% | 46% | 0% | **0%** |

A conclusão é que o sistema **não multou nenhuma moto inocente** e não deixou nenhum infrator passar. A alta taxa de revisão é o preço da regra "na dúvida, não autua": ela acontece quando as duas motos estão na mesma direção, por exemplo lado a lado no corredor.

**Impacto (aba "Avaliação e impacto", cenário ilustrativo):** fundo de 55 dB, 80 passagens adulteradas por noite a 88 dB na fachada, 4 s cada. Com redução de 60% das passagens (efeito educativo + multas), o Lnight cai de 68,2 dB para 64,5 dB e o número de picos cai de 80 para 32 por noite.

## 6. Limitações
- Tudo é simulado: sons sintéticos, cena em 2D (sem altura), sem Doppler e sem reflexões nas fachadas.
- O nível é medido na banda de 300 a 3000 Hz (aproxima o dB(A)), sem calibração real.
- A detecção pela câmera e a leitura da placa (OCR) são simuladas: as posições dos veículos são conhecidas.
- Um conjunto linear dá bem a **direção**, mas mal a distância. A distância vem da câmera.
- Os números de impacto são parâmetros de cenário, não medições.

## 7. Trabalhos futuros
- Medições reais com decibelímetro classe 1 e calibração do conjunto de microfones.
- Conjunto 2D (em cruz ou espiral) para estimar também a altura e a distância.
- Detecção de veículos e OCR de placas reais (YOLO + ALPR).
- Homologação metrológica (INMETRO) e regulamentação junto ao CONTRAN para validade da autuação.
- Piloto com a Prefeitura e mapa de ruído noturno dos bairros.

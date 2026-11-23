# Radar de Ruído — Curitiba (simulação)

```
pip install -r requirements.txt
streamlit run app.py          # painel (demonstração)
python demo.py                # figuras em saida/ + evento_exemplo.json
python demo.py --avaliar 100  # acurácia (Monte Carlo)
python mqtt_pub.py localhost  # assinante MQTT (lado da fiscalização)
python gerar_pdf.py           # gera Radar_de_Ruido_Como_Funciona.pdf
```
MQTT: é preciso um broker (Mosquitto local) ou digitar `test.mosquitto.org` no painel. Sem broker, os eventos ficam salvos em `eventos.jsonl`.

Arquivos: `radar_core.py` (física, localização, decisão, JSON), `visual.py` (gráficos), `app.py` (painel), `mqtt_pub.py`, `RELATORIO.md`, `ROTEIRO_APRESENTACAO.md`.

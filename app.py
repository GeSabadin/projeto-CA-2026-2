"""Painel da fiscalização - Radar de Ruído (Curitiba).   Rodar:  python -m streamlit run app.py"""
import json
import time
from pathlib import Path

import streamlit as st

import radar_core as rc
import visual as vz

st.set_page_config(page_title="Radar de Ruído · Curitiba", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1250px;}
.passo {border-top:3px solid #2a78d6; padding:10px 2px 0 0; height:100%;}
.passo .n {font-size:.8rem; font-weight:700; color:#2a78d6; letter-spacing:.06em;}
.passo h4 {margin:2px 0 4px 0; font-size:1rem; color:#ecebe6;}
.passo p {margin:0; color:#a3a29b; font-size:.92rem; line-height:1.35;}
.veredito {border-left:6px solid; background:#171a21; border-radius:4px; padding:14px 20px; margin:4px 0 14px 0; color:#ecebe6;}
.veredito .t {font-size:1.25rem; font-weight:700;}
.veredito .s {font-size:.95rem; color:#a3a29b; margin-top:4px;}
.cartao {border-radius:4px; padding:12px 16px; margin-bottom:8px; border:1px solid #2c2f38; background:#141820;}
.badge {display:inline-block; border-radius:3px; padding:1px 8px; font-weight:700; font-size:.78rem; letter-spacing:.04em;}
.sub {color:#a3a29b; font-size:.95rem;}
</style>
""", unsafe_allow_html=True)

DESCRICAO = {
    "Duas motos em faixas diferentes": "Uma moto adulterada e uma normal, em faixas diferentes. O sistema precisa apontar a culpada.",
    "Duas motos lado a lado (corredor)": "Duas motos coladas no corredor, na mesma direção. Não dá para ter certeza: vai para revisão humana.",
    "Moto adulterada + carro + moto normal": "Três veículos na cena. Só a moto adulterada deve ser apontada.",
    "Somente motos normais": "Ninguém acima do limite. O radar não deve gerar nenhum evento.",
}

# ---------------------------------------------------------------- barra lateral
with st.sidebar:
    st.markdown("## Escolha a cena")
    nome = st.radio("Cena", rc.CENARIOS, label_visibility="collapsed")
    st.info(DESCRICAO[nome])
    radar = st.selectbox("Radar", rc.RADARES, format_func=lambda r: f"{r['radar_id']} · {r['via']}")
    with st.expander("Ajustes avançados"):
        limite = st.slider("Limite (dB a 7,5 m)", 70.0, 95.0, 80.0, 0.5)
        margem = st.slider("Margem de erro (dB)", 0.0, 5.0, 2.0, 0.5)
        n_mics = st.select_slider("Número de microfones", [4, 8, 12, 16], 16)
        abertura = st.slider("Tamanho da barra de microfones (m)", 0.3, 1.5, 0.9, 0.05)
        jitter = st.slider("Erro de sincronização (µs)", 0, 50, 0)
        fundo = st.slider("Ruído de fundo da cidade (dB)", 45, 70, 60)
        seed = st.number_input("Semente aleatória", 0, 9999, 1)
    with st.expander("Envio MQTT"):
        host = st.text_input("Broker", "test.mosquitto.org", help="test.mosquitto.org (público) ou localhost (Mosquitto)")
        porta = st.number_input("Porta", 1, 65535, 1883)

cfg = rc.ConfigArray(n_mics=n_mics, espacamento=abertura / (n_mics - 1), jitter_us=jitter)
params = (nome, int(seed), limite, margem, n_mics, cfg.espacamento, jitter, fundo)


@st.cache_data(show_spinner="Simulando a cena...")
def rodar(nome, seed, limite, margem, n_mics, esp, jitter, fundo):
    c = rc.ConfigArray(n_mics=n_mics, espacamento=esp, jitter_us=jitter)
    return rc.analisar_cena(rc.cenario(nome), c, limite=limite, margem=margem, fundo_db=fundo, seed=seed)


@st.cache_data(show_spinner=False)
def quadro_png(params, k):
    return vz.png(vz.desenhar_cena(rodar(*params), k))


res = rodar(*params)
eventos = rc.gerar_eventos(res, radar)
K = len(res.tempos)

# ---------------------------------------------------------------- cabeçalho
st.markdown("# Radar de Ruído · Curitiba")
st.markdown('<div class="sub">Painel de fiscalização · identificação de veículos com escapamento adulterado '
            'por localização acústica (simulação)</div>',
            unsafe_allow_html=True)
st.write("")
passos = [("ETAPA 1", "Captação", "16 microfones no poste captam o som da rua."),
          ("ETAPA 2", "Direção do som", "O som chega a cada microfone em um instante diferente. Daí sai a <b>direção</b> do barulho."),
          ("ETAPA 3", "Confirmação", "A câmera mostra qual veículo está naquela direção e se o barulho <b>acompanha</b> ele."),
          ("ETAPA 4", "Envio", "Envia o evento à fiscalização. <b>Na dúvida, não multa</b>: vai para uma pessoa revisar.")]
for col, (ic, tit, txt) in zip(st.columns(4), passos):
    col.markdown(f'<div class="passo"><div class="n">{ic}</div><h4>{tit}</h4><p>{txt}</p></div>', unsafe_allow_html=True)
st.write("")

aba1, aba2, aba3, aba4 = st.tabs(["Demonstração", "Eventos enviados", "Radares na cidade", "Resultados e impacto"])

# ---------------------------------------------------------------- aba 1: demonstração
with aba1:
    culpados = [d for d in res.decisoes if d["status"] == rc.STATUS_AUTUA]
    duvidas = [d for d in res.decisoes if d["status"] == rc.STATUS_REVISAO]
    if culpados:
        cor, txt = vz.VERMELHO, "white"
        titulo = "Moto barulhenta identificada: " + ", ".join(f"{d['veiculo']} (placa {d['placa']})" for d in culpados)
        sub = " · ".join(f"{d['veiculo']}: {d['L75']:.0f} dB, {d['L75'] - limite:+.0f} dB acima do limite" for d in culpados)
    elif duvidas:
        cor, txt = vz.AMARELO, "#0b0b0b"
        titulo = "Caso em dúvida: enviado para revisão humana"
        sub = vz.explicar(duvidas[0]) + " Na dúvida, o sistema não multa."
    else:
        cor, txt = vz.VERDE, "white"
        titulo = "Nenhuma infração nesta passagem"
        sub = "Todos os veículos ficaram abaixo do limite."
    st.markdown(f'<div class="veredito" style="border-color:{cor}"><div class="t">{titulo}</div>'
                f'<div class="s">{sub}</div></div>', unsafe_allow_html=True)

    c_play, c_slider = st.columns([1, 5])
    tocar = c_play.button("Reproduzir passagem", width="stretch")
    k = c_slider.slider("Momento da passagem", 1, K, K // 2 + 1, label_visibility="collapsed") - 1
    tela = st.empty()
    if tocar:
        for kk in range(K):
            tela.image(quadro_png(params, kk), width="stretch")
            time.sleep(0.45)
    else:
        tela.image(quadro_png(params, k), width="stretch")

    with st.expander("Como ler esta imagem", expanded=False):
        st.markdown("""
- É a avenida **vista de cima**. O círculo azul na calçada é o **radar**.
- O **facho amarelo/laranja** é a direção de onde está vindo o barulho, como a luz de uma lanterna.
- A moto que fica **dentro do facho** é a fonte do barulho. Clique em **Reproduzir passagem** e veja o facho **seguir a moto** enquanto ela anda.
- Cores: vermelho = infração, amarelo = dúvida (revisão humana), verde = OK. A linha pontilhada é o caminho que o veículo já percorreu.
""")

    st.markdown("#### Resultado por veículo")
    for d, v in zip(res.decisoes, res.veiculos):
        s = vz.STATUS[d["status"]]
        st.markdown(
            f'<div class="cartao"><span class="badge" style="background:{s["cor"]};color:{s["txt_cor"]}">'
            f'{s["texto"]}</span> &nbsp; <b>{v.nome}</b> · placa {v.placa} · '
            f'{"moto" if v.tipo == "moto" else "carro"} a {v.v * 3.6:.0f} km/h &nbsp;·&nbsp; '
            f'<b>{vz.nivel_texto(d, limite)}</b><br><span class="sub">{vz.explicar(d)}</span></div>',
            unsafe_allow_html=True)

    g1, g2 = st.columns(2)
    with g1:
        st.image(vz.png(vz.grafico_db(res)), width="stretch")
        st.caption("Cada linha é um veículo. Acima da linha vermelha tracejada = acima do limite.")
    with g2:
        st.image(vz.png(vz.grafico_perfil(res, k)), width="stretch")
        st.caption("O pico da curva azul mostra de que direção vem o barulho. As linhas verticais são os veículos.")

    with st.expander("Detalhes técnicos"):
        st.dataframe([{
            "veículo": d["veiculo"], "decisão": d["status"], "dB estimado": d["L75"],
            "verdade da simulação": f"{v.L75:.0f} dB · {'ADULTERADA' if v.adulterado else 'normal'}",
            "agudos (1,5–3 kHz)": d["hf"], "quadros válidos": d["quadros_validos"],
            "quadros ambíguos": d["quadros_ambiguos"], "rastreado": d["fracao_rastreada"],
            "confiança": d["confianca"]} for d, v in zip(res.decisoes, res.veiculos)], width="stretch")
        st.markdown(f"Barra com **{n_mics} microfones** e {abertura:.2f} m · beamforming *delay-and-sum* "
                    f"via correlação cruzada (GCC) entre os pares · banda de 300 a 3000 Hz (≈ dB(A)) · "
                    f"{K} quadros de 128 ms · cena 2D simulada.")

# ---------------------------------------------------------------- aba 2: eventos
with aba2:
    if not eventos:
        st.success("Nenhum evento: nada é enviado à fiscalização quando todos estão dentro do limite.")
    for ev in eventos:
        s = vz.STATUS[ev["status"]]
        st.markdown(
            f'<div class="cartao"><span class="badge" style="background:{s["cor"]};color:{s["txt_cor"]}">'
            f'{s["nome"].upper()}</span> &nbsp; <b>Placa {ev["veiculo"]["placa"]}</b> · '
            f'{ev["local"]["via"]} · {ev["timestamp"][11:19]}<br>'
            f'<span style="font-size:1.6rem;font-weight:700">{ev["nivel_db_7m5"]:.0f} dB</span> '
            f'<span class="sub">(limite {ev["limite_db"]:.0f} dB · {ev["excesso_db"]:+.0f} dB) · '
            f'direção {ev["direcao_graus"]:.0f}° · confiança {ev["confianca"]:.0%}</span></div>',
            unsafe_allow_html=True)
    if eventos:
        with st.expander("Mensagem MQTT (JSON) que chega no painel da fiscalização"):
            st.code(f"tópico: cwb/radar-ruido/{radar['radar_id']}/eventos", language="text")
            st.json(eventos[0])
        if st.button("Enviar eventos agora (MQTT)", type="primary"):
            try:
                import mqtt_pub
                Path("evidencias").mkdir(exist_ok=True)
                for ev in eventos:
                    Path(ev["evidencias"]["foto"]).write_bytes(quadro_png(params, K // 2))
                with open("eventos.jsonl", "a", encoding="utf-8") as f:
                    for ev in eventos:
                        f.write(json.dumps(ev, ensure_ascii=False) + "\n")
                n = mqtt_pub.publicar(eventos, host, int(porta))
                st.success(f"{n} evento(s) enviados para {host}.")
            except Exception as e:
                st.warning(f"Não consegui conectar ao broker ({e}). Os eventos foram salvos em eventos.jsonl.")

# ---------------------------------------------------------------- aba 3: mapa
with aba3:
    st.markdown("Vias com muito movimento noturno onde os radares seriam instalados *(posições ilustrativas)*.")
    st.map([{"lat": r["lat"], "lon": r["lon"]} for r in rc.RADARES], zoom=13, color="#d03b3b", size=60)
    for r in rc.RADARES:
        st.markdown(f"**{r['radar_id']}** · {r['via']}")

# ---------------------------------------------------------------- aba 4: resultados
with aba4:
    st.markdown("### O sistema acerta?")
    st.markdown("Testamos **100 cenas aleatórias** com duas motos (uma adulterada e uma normal, às vezes lado a lado).")
    pad = dict(acerto=51, revisao=49, perdido=0, falso_positivo=0)
    n_c = 100
    if st.button("Rodar o teste de novo (≈30 s)"):
        barra = st.progress(0.0)
        n_c = 40
        pad = rc.avaliar(n_c, cfg=cfg, limite=limite, margem=margem, progresso=barra.progress)
    c = st.columns(4)
    c[0].metric("Apontou a moto certa", f"{100 * pad['acerto'] / n_c:.0f}%")
    c[1].metric("Mandou para revisão", f"{100 * pad['revisao'] / n_c:.0f}%")
    c[2].metric("Deixou o infrator passar", f"{100 * pad['perdido'] / n_c:.0f}%")
    c[3].metric("Multou um inocente", f"{100 * pad['falso_positivo'] / n_c:.0f}%")
    st.caption("Nenhum inocente foi multado. Quando há dúvida (motos na mesma direção), o caso vai para uma pessoa revisar.")

    st.divider()
    st.markdown("### Antes x depois: o sono de quem mora na avenida")
    c1, c2 = st.columns([1, 1])
    with c1:
        n_ev = st.slider("Motos adulteradas passando por noite (hoje)", 0, 300, 80)
        red = st.slider("Redução esperada com o radar (multas + efeito educativo) %", 0, 100, 60)
        with st.expander("Mais parâmetros"):
            L_fundo = st.slider("Ruído de fundo noturno na fachada (dB)", 45, 65, 55)
            L_ev = st.slider("Barulho de uma passagem na fachada (dB)", 75, 100, 88)
            dur = st.slider("Duração de cada passagem (s)", 1, 10, 4)
    antes = rc.lnight(L_fundo, n_ev, L_ev, dur)
    depois = rc.lnight(L_fundo, n_ev * (1 - red / 100), L_ev, dur)
    with c2:
        st.image(vz.png(vz.grafico_antes_depois(n_ev, n_ev * (1 - red / 100))), width="stretch")
        m1, m2 = st.columns(2)
        m1.metric("Ruído médio da noite (Lnight)", f"{depois:.1f} dB", f"{depois - antes:.1f} dB", delta_color="inverse")
        m2.metric("Picos evitados por noite", f"{n_ev * red / 100:.0f}")
    st.caption("Valores de entrada ilustrativos (cenário). A OMS (2018) recomenda Lnight abaixo de 45 dB para o "
               "tráfego. Para o sono, cada pico que acorda conta, não só a média.")

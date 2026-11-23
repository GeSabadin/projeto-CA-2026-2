"""Desenhos do painel: cena da rua com o 'facho' de barulho, gráficos e textos explicativos."""
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch, Patch, Rectangle

import radar_core as rc

# cores de status (sempre acompanhadas de texto, nunca só a cor)
VERDE, AMARELO, VERMELHO = "#0ca30c", "#fab219", "#d03b3b"
STATUS = {
    rc.STATUS_OK: dict(cor=VERDE, texto="OK", txt_cor="white", emoji="", nome="Dentro do limite"),
    rc.STATUS_REVISAO: dict(cor=AMARELO, texto="DÚVIDA", txt_cor="#0b0b0b", emoji="", nome="Revisão humana"),
    rc.STATUS_AUTUA: dict(cor=VERMELHO, texto="INFRAÇÃO", txt_cor="white", emoji="", nome="Infração"),
}
FUNDO = "#0e1117"
TINTA, TINTA2, GRADE = "#ecebe6", "#a3a29b", "#2c2c2a"

# facho: transparente -> laranja -> amarelo claro
FACHO = LinearSegmentedColormap.from_list(
    "facho", [(1, 0.55, 0.0, 0.0), (1, 0.55, 0.0, 0.45), (1, 0.85, 0.2, 0.75), (1, 1, 0.75, 0.9)])

plt.rcParams.update({"font.size": 11, "axes.edgecolor": "#383835", "figure.facecolor": FUNDO,
                     "axes.facecolor": FUNDO, "text.color": TINTA, "axes.titlecolor": TINTA,
                     "savefig.facecolor": FUNDO, "axes.labelcolor": TINTA2,
                     "xtick.color": TINTA2, "ytick.color": TINTA2, "axes.titleweight": "bold",
                     "axes.titlesize": 13, "axes.titlelocation": "left"})


def som_do_vizinho(d):
    return d["motivo"].startswith("sem pico")


def explicar(d):
    m = d["motivo"]
    if m.startswith("nivel abaixo"):
        return "Barulho abaixo do limite."
    if m.startswith("fonte ambigua"):
        return "Havia outra moto na mesma direção o tempo todo: não dá para saber qual das duas fez o barulho."
    if m.startswith("sem pico"):
        return "O barulho que chegava desta direção vinha da moto vizinha, não desta."
    if m.startswith("poucos quadros"):
        return "Ficou pouco tempo separada dos outros veículos: dados insuficientes."
    if m.startswith("pico acustico"):
        return "O ponto de barulho não acompanhou o movimento desta moto."
    if m.startswith("nivel dentro"):
        return "Barulho muito perto do limite (dentro da margem de erro)."
    return "Barulho acima do limite, e o ponto de barulho acompanhou a moto durante toda a passagem."


def nivel_texto(d, limite):
    if som_do_vizinho(d) or d["status"] == rc.STATUS_OK and d["L75"] < limite:
        return f"abaixo de {limite:.0f} dB"
    return f"{d['L75']:.0f} dB"


def desenhar_cena(res: rc.Resultado, k: int, faixa_db=12.0):
    loc = rc.get_localizador(res.cfg)
    fig, ax = plt.subplots(figsize=(12, 5.4), facecolor=FUNDO)
    # prédios / calçadas / pista
    ax.add_patch(Rectangle((-15, 9.0), 30, 1.6, color="#16181d", zorder=0))
    for x in np.arange(-14.5, 15, 2.4):
        ax.add_patch(Rectangle((x, 9.3), 1.6, 1.0, color="#262930", zorder=0))
        ax.add_patch(Rectangle((x + 0.3, 9.75), 0.35, 0.35, color="#f7e7a1", zorder=0))
        ax.add_patch(Rectangle((x + 0.95, 9.75), 0.35, 0.35, color="#f7e7a1", zorder=0))
    ax.text(14.8, 10.45, "moradores tentando dormir", ha="right", va="top", fontsize=9, color=TINTA2)
    ax.add_patch(Rectangle((-15, 0), 30, 1.75, color="#3d3e44", zorder=0))
    ax.add_patch(Rectangle((-15, 8.75), 30, 0.25, color="#3d3e44", zorder=0))
    ax.add_patch(Rectangle((-15, 1.75), 30, 7.0, color="#25262b", zorder=0))
    ax.plot([-15, 15], [5.25, 5.25], ls=(0, (5, 5)), color="white", lw=2, zorder=1)
    ax.text(-14.7, 0.6, "calçada", fontsize=9, color=TINTA2)
    ax.text(-14.7, 2.0, "faixa 1  →", fontsize=9, color="#8a8983")
    ax.text(-14.7, 5.5, "faixa 2  →", fontsize=9, color="#8a8983")

    # facho de barulho (mapa de calor acústico)
    if res.mapas:
        m = res.mapas[k].copy()
        norm = np.clip((m - (m.max() - faixa_db)) / faixa_db, 0, 1)
        norm[loc.gy > 8.75, :] = 0
        ax.imshow(norm, extent=[loc.gx[0], loc.gx[-1], loc.gy[0], loc.gy[-1]], origin="lower",
                  cmap=FACHO, vmin=0, vmax=1, aspect="auto", zorder=2, interpolation="bilinear")

    # veículos vistos pela câmera
    t = res.tempos[k]
    for n, v in enumerate(res.veiculos):
        d = res.decisoes[n]
        s = STATUS[d["status"]]
        p = v.pos(t)
        w, h = (2.0, 0.9) if v.tipo == "moto" else (4.4, 1.8)
        rastro = np.array([v.pos(tt) for tt in res.tempos[:k + 1]])
        ax.plot(rastro[:, 0], rastro[:, 1], ls=":", color=s["cor"], lw=2, zorder=3)
        ax.add_patch(FancyBboxPatch((p[0] - w / 2, p[1] - h / 2), w, h, boxstyle="round,pad=0.05,rounding_size=0.3",
                                    fc=s["cor"], ec="white", lw=2, alpha=0.95, zorder=4))
        ax.text(p[0], p[1], v.nome.split()[-1], ha="center", va="center", color=s["txt_cor"],
                fontsize=10, fontweight="bold", zorder=5)
        ax.text(p[0], p[1] + h / 2 + 0.25, f"{v.nome}  ·  {s['texto']}", ha="center", va="bottom",
                fontsize=9.5, fontweight="bold", color=s["txt_cor"], zorder=6,
                bbox=dict(boxstyle="round,pad=0.3", fc=s["cor"], ec="none"))

    # radar no poste
    ax.plot(0, 0.75, "o", ms=16, color="#2a78d6", mec="white", mew=2, zorder=7)
    ax.text(0.7, 0.75, "RADAR  (16 microfones + câmera)", va="center", fontsize=9.5,
            color="#6aa8f0", fontweight="bold", zorder=7)

    ax.set_xlim(-15, 15)
    ax.set_ylim(0, 10.6)
    ax.set_yticks([])
    ax.set_xlabel("metros ao longo da avenida")
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.set_title(f"Quadro {k + 1} de {len(res.tempos)}   ·   t = {t:.2f} s".replace(".", ","))
    leg = [Patch(color=(1, 0.8, 0.2), label="facho = de onde vem o barulho")] + \
          [Patch(color=STATUS[s]["cor"], label=f"{STATUS[s]['texto']}: {STATUS[s]['nome']}")
           for s in (rc.STATUS_AUTUA, rc.STATUS_REVISAO, rc.STATUS_OK)]
    ax.legend(handles=leg, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=4, frameon=False, fontsize=9.5)
    fig.tight_layout()
    return fig


def grafico_db(res: rc.Resultado):
    fig, ax = plt.subplots(figsize=(6.2, 3.4), facecolor=FUNDO)
    ax.axhspan(res.limite - res.margem, res.limite + res.margem, color=AMARELO, alpha=0.15, lw=0)
    ax.axhline(res.limite, color=VERMELHO, ls="--", lw=1.5)
    ax.text(res.tempos[0], res.limite + res.margem + 0.4, f"limite {res.limite:.0f} dB", color=VERMELHO, fontsize=9)
    for n, v in enumerate(res.veiculos):
        d = res.decisoes[n]
        viz = som_do_vizinho(d)
        cor = "#a8a7a0" if viz else STATUS[d["status"]]["cor"]
        ax.plot(res.tempos, res.L75_est[:, n], "-o" if not viz else "--", color=cor, lw=2, ms=5)
        rot = f"{v.nome}" + (" (era o vizinho)" if viz else "")
        ax.text(res.tempos[-1] + 0.03, res.L75_est[-1, n], rot, color=TINTA, fontsize=9, va="center")
    ax.set_xlim(res.tempos[0] - 0.02, res.tempos[-1] + 0.45)
    ax.set_ylim(res.limite - 15, max(res.L75_est.max(), res.limite) + 4)
    ax.set_xlabel("tempo (s)")
    ax.set_ylabel("dB (a 7,5 m)")
    ax.set_title("Quanto barulho cada veículo fez")
    ax.grid(axis="y", color=GRADE, lw=0.8)
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    fig.tight_layout()
    return fig


def grafico_perfil(res: rc.Resultado, k: int):
    loc = rc.get_localizador(res.cfg)
    fig, ax = plt.subplots(figsize=(6.2, 3.4), facecolor=FUNDO)
    ax.plot(loc.ang, res.perfis[k], color="#2a78d6", lw=2)
    for n, v in enumerate(res.veiculos):
        cor = STATUS[res.decisoes[n]["status"]]["cor"]
        ax.axvline(res.ang_veic[k, n], color=cor, lw=2, alpha=0.8)
        ax.text(res.ang_veic[k, n], ax.get_ylim()[1], v.nome, color=TINTA, fontsize=8.5, ha="center", va="bottom")
    ax.set_xlabel("direção (graus)  ←  esquerda  ·  direita  →")
    ax.set_ylabel("dB")
    ax.set_title("Varredura: o radar 'olha' para cada direção", pad=16)
    ax.invert_xaxis()
    ax.grid(axis="y", color=GRADE, lw=0.8)
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    fig.tight_layout()
    return fig


def grafico_antes_depois(antes, depois):
    fig, ax = plt.subplots(figsize=(5, 2.6), facecolor=FUNDO)
    ax.barh([1, 0], [antes, depois], color=["#5c5b56", "#2a78d6"], height=0.55)
    for y, val in ((1, antes), (0, depois)):
        ax.text(val + max(antes, 1) * 0.02, y, f"{val:.0f}", va="center", fontsize=11, fontweight="bold", color=TINTA)
    ax.set_yticks([1, 0], ["Antes do radar", "Com o radar"])
    ax.set_xlim(0, max(antes, 1) * 1.18)
    ax.set_title("Picos de barulho por noite")
    ax.set_xticks([])
    for s_ in ("top", "right", "bottom"):
        ax.spines[s_].set_visible(False)
    fig.tight_layout()
    return fig


def png(fig, dpi=110):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=FUNDO)
    plt.close(fig)
    return buf.getvalue()

import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch, Circle

PROJ = Path(r"C:\UTFPR\CA\PROJETO")
OUT = PROJ / "saida" / "fig_pdf"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(PROJ))

AZUL, VERM, AMAR, VERDE, CINZA, TINTA = "#2a78d6", "#d03b3b", "#fab219", "#0ca30c", "#6b6a64", "#1f1f1e"


# ---------------------------------------------------------------- figura 1: arquitetura
def caixa(ax, x, y, w, h, titulo, texto, cor):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc="white", ec=cor, lw=2))
    ax.add_patch(FancyBboxPatch((x, y + h - 0.32), w, 0.32, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=cor, ec=cor, lw=2))
    ax.text(x + w / 2, y + h - 0.16, titulo, ha="center", va="center", color="white", fontsize=10, fontweight="bold")
    ax.text(x + w / 2, y + (h - 0.32) / 2, texto, ha="center", va="center", color=TINTA, fontsize=8.5, linespacing=1.4)


def seta(ax, x1, x2, y, txt=""):
    ax.annotate("", (x2, y), (x1, y), arrowprops=dict(arrowstyle="-|>", color=CINZA, lw=1.8))
    if txt:
        ax.text((x1 + x2) / 2, y + 0.12, txt, ha="center", va="bottom", fontsize=7.5, color=CINZA)


fig, ax = plt.subplots(figsize=(10, 2.6))
W, H, Y = 1.75, 1.6, 0.2
xs = [0.0, 2.25, 4.5, 6.75, 9.0]
caixa(ax, xs[0], Y, W, H, "1. Sensores", "16 microfones\nem uma barra\n+ 1 câmera\n(no poste)", AZUL)
caixa(ax, xs[1], Y, W, H, "2. Processamento", "computador local\n(Raspberry Pi)\ncalcula direção,\nnível e decisão", AZUL)
caixa(ax, xs[2], Y, W, H, "3. Comunicação", "mensagem JSON\nvia MQTT\n(internet / 4G)", AZUL)
caixa(ax, xs[3], Y, W, H, "4. Painel", "fiscalização vê\nos eventos, mapa\ne evidências", AZUL)
caixa(ax, xs[4], Y, W, H, "5. Pessoa", "agente de trânsito\nconfirma ou\ndescarta", VERDE)
for a, b, t in zip(xs[:-1], xs[1:], ["som + imagem", "evento", "tempo real", "revisão"]):
    seta(ax, a + W + 0.05, b - 0.05, Y + H / 2, t)
ax.set_xlim(-0.1, 10.85); ax.set_ylim(0, 2); ax.axis("off")
fig.tight_layout(); fig.savefig(OUT / "arquitetura.png", dpi=200); plt.close(fig)

# ---------------------------------------------------------------- figura 2: princípio da direção
fig, ax = plt.subplots(figsize=(9, 4.0))
mics = np.linspace(-2, 2, 9)
fonte = np.array([-3.2, 4.2])
for r in np.arange(0.8, 8, 0.8):
    ax.add_patch(Circle(fonte, r, fill=False, ec=AMAR, lw=1.4, alpha=0.9 - r * 0.09))
ax.plot(mics, np.zeros_like(mics), "s", color=AZUL, ms=9)
ax.plot([-2.2, 2.2], [-0.25, -0.25], color=CINZA, lw=6, solid_capstyle="round")
ax.text(0, -0.7, "barra de microfones (no poste)", ha="center", fontsize=9, color=TINTA)
ax.add_patch(FancyBboxPatch((fonte[0] - 0.55, fonte[1] - 0.25), 1.1, 0.5, boxstyle="round,pad=0.05",
                            fc=VERM, ec="white"))
ax.text(*fonte, "moto", ha="center", va="center", color="white", fontweight="bold", fontsize=9)
d = np.hypot(mics - fonte[0], fonte[1])
for xm, dd in ((mics[0], d[0]), (mics[-1], d[-1])):
    ax.plot([fonte[0], xm], [fonte[1], 0], ls="--", color=CINZA, lw=1)
ax.annotate("o som chega\nPRIMEIRO aqui", (mics[0], 0.15), (-4.6, 1.2), fontsize=9, color=TINTA,
            arrowprops=dict(arrowstyle="->", color=TINTA))
ax.annotate(f"... e {1e3 * (d[-1] - d[0]) / 343:.1f} milésimos de\nsegundo DEPOIS aqui", (mics[-1], 0.15), (2.6, 1.6),
            fontsize=9, color=TINTA, arrowprops=dict(arrowstyle="->", color=TINTA))
ax.text(3.0, 3.6, "A diferença de tempo entre\nos microfones revela a\nDIREÇÃO de onde veio o som.",
        fontsize=10, color=AZUL, fontweight="bold")
ax.set_xlim(-5.2, 6.2); ax.set_ylim(-1.0, 5.0); ax.set_aspect("equal"); ax.axis("off")
fig.tight_layout(); fig.savefig(OUT / "principio.png", dpi=200); plt.close(fig)

# ---------------------------------------------------------------- figura 3: cena do painel
import radar_core as rc  # noqa: E402
import visual as vz  # noqa: E402

res = rc.analisar_cena(rc.cenario(rc.CENARIOS[0]), seed=1)
(OUT / "cena.png").write_bytes(vz.png(vz.desenhar_cena(res, 4), dpi=170))
res2 = rc.analisar_cena(rc.cenario(rc.CENARIOS[1]), seed=1)
(OUT / "cena_corredor.png").write_bytes(vz.png(vz.desenhar_cena(res2, 4), dpi=170))

# ---------------------------------------------------------------- PDF
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_JUSTIFY  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,  # noqa: E402
                                Spacer, Table, TableStyle)

fdir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("DV", str(fdir / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", str(fdir / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DVI", str(fdir / "DejaVuSans-Oblique.ttf")))
from reportlab.pdfbase.pdfmetrics import registerFontFamily  # noqa: E402
registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVB")

AZ = colors.HexColor(AZUL)
corpo = ParagraphStyle("corpo", fontName="DV", fontSize=10.2, leading=15, alignment=TA_JUSTIFY,
                       textColor=colors.HexColor("#222222"), spaceAfter=7)
titulo = ParagraphStyle("tit", fontName="DVB", fontSize=22, leading=27, textColor=colors.HexColor("#111111"))
subt = ParagraphStyle("sub", fontName="DV", fontSize=11.5, leading=16, textColor=colors.HexColor("#555555"))
h1 = ParagraphStyle("h1", fontName="DVB", fontSize=14, leading=18, textColor=AZ, spaceBefore=12, spaceAfter=6)
h2 = ParagraphStyle("h2", fontName="DVB", fontSize=11, leading=15, textColor=colors.HexColor("#222222"),
                    spaceBefore=6, spaceAfter=3)
leg = ParagraphStyle("leg", fontName="DVI", fontSize=8.5, leading=11, textColor=colors.HexColor("#666666"),
                     spaceAfter=10)
destaque = ParagraphStyle("dest", parent=corpo, fontName="DV", fontSize=10.5, leading=15.5,
                          backColor=colors.HexColor("#eef4fc"), borderPadding=(8, 10, 8, 10),
                          borderColor=AZ, borderWidth=0, spaceBefore=8, spaceAfter=14)
cel = ParagraphStyle("cel", fontName="DV", fontSize=9, leading=12)
celb = ParagraphStyle("celb", fontName="DVB", fontSize=9, leading=12, textColor=colors.white)

P = lambda t, s=corpo: Paragraph(t, s)  # noqa: E731
LW = A4[0] - 4 * cm


def img(nome, largura=LW):
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(str(OUT / nome)).getSize()
    return Image(str(OUT / nome), width=largura, height=largura * ih / iw)


def tabela(linhas, larguras, cab=AZ):
    t = Table([[P(c, celb if i == 0 else cel) for c in l] for i, l in enumerate(linhas)], colWidths=larguras)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), cab),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f6f8")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d5d7dd")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


s = []
s += [P("Radar de Ruído", titulo), Spacer(1, 4),
      P("Como o sistema funciona: visão geral", subt), Spacer(1, 2),
      P("Ciências do Ambiente · UTFPR · Curitiba", subt), Spacer(1, 14)]

s += [P("A ideia em uma frase", h1),
      P("Um equipamento instalado num poste <b>escuta</b> a rua, descobre <b>de que direção</b> vem cada barulho, "
        "usa uma câmera para ver <b>qual veículo</b> está naquela direção e, se o barulho passar do limite, avisa a "
        "fiscalização. Se houver qualquer dúvida sobre quem fez o barulho, <b>ninguém é multado</b> "
        "automaticamente: uma pessoa revisa o caso.", destaque)]

s += [P("1. O problema", h1),
      P("Em avenidas com movimento noturno, como a Sete de Setembro e a Av. Batel, motos com escapamento "
        "adulterado produzem picos de barulho muito acima do resto do trânsito. Cada pico pode acordar "
        "centenas de moradores. Dormir mal de forma repetida está ligado a estresse, problemas cardiovasculares, "
        "queda de rendimento e pior qualidade de vida. Por isso a Organização Mundial da Saúde recomenda que o ruído "
        "noturno do tráfego fique abaixo de 45 dB."),
      P("Hoje a fiscalização depende de um agente de trânsito com um decibelímetro na mão. Isso tem dois limites:"),
      P("• <b>É raro:</b> o agente não está lá às 2h da manhã, quando o barulho mais incomoda."),
      P("• <b>Não diz quem foi:</b> o decibelímetro mede <i>quanto</i> barulho há, mas não <i>de onde</i> ele vem. "
        "Com duas motos passando juntas, é impossível apontar a culpada só com o número de decibéis.")]

s += [P("2. A solução: uma \"câmera acústica\"", h1),
      P("O sistema junta duas coisas que, sozinhas, não resolvem o problema:"),
      P("• <b>Microfones</b> sabem que houve barulho, mas não sabem qual veículo o fez."),
      P("• <b>Câmeras</b> sabem quais veículos estão na rua, mas não ouvem nada."),
      P("Juntos, eles formam uma <b>câmera acústica</b>: uma imagem da rua em que o barulho aparece como uma mancha "
        "de calor em cima do veículo que o produziu. Paris já testa equipamentos desse tipo nas ruas."),
      Spacer(1, 4), img("arquitetura.png"),
      P("Figura 1 - Visão geral: do som captado na rua até a decisão de uma pessoa.", leg)]

s += [PageBreak(), P("3. Como o radar descobre a direção do som", h1),
      P("O som viaja pelo ar a cerca de 343 metros por segundo. É rápido, mas não é instantâneo. O radar tem "
        "<b>16 microfones enfileirados</b> numa barra de 90 cm. Quando uma moto faz barulho, a onda sonora chega "
        "primeiro ao microfone mais próximo dela e, frações de milissegundo depois, aos outros."),
      img("principio.png", LW * 0.9),
      P("Figura 2 - O mesmo som chega a cada microfone num instante ligeiramente diferente.", leg),
      P("O computador compara os sinais de todos os pares de microfones (120 pares) e procura esses pequenos "
        "atrasos. Depois ele faz uma \"varredura\": testa todas as direções possíveis e verifica em qual delas os "
        "atrasos se encaixam. Essa direção é a de onde o barulho veio. É o mesmo princípio que usamos sem perceber: "
        "nosso cérebro descobre de onde vem um som comparando o que chega ao ouvido esquerdo e ao direito. O radar "
        "faz isso com 16 \"ouvidos\" em vez de 2, e por isso é muito mais preciso."),
      P("O resultado da varredura é desenhado sobre a imagem da rua como um <b>facho</b>, parecido com a luz de uma "
        "lanterna saindo do radar. O veículo que fica dentro do facho é a fonte do barulho.")]

s += [P("4. Como ele aponta a moto culpada", h1),
      img("cena.png"),
      P("Figura 3 - Tela do painel (simulação). O facho amarelo sai do radar e cai sobre a Moto A, marcada como "
        "infração. A Moto B, em outra faixa, está dentro do limite.", leg),
      P("A decisão passa por quatro verificações, e todas precisam concordar:"),
      tabela([
          ["Verificação", "Pergunta que responde"],
          ["<b>Nível</b>", "O barulho passou do limite? O nível é corrigido para uma distância padrão de 7,5 m, "
                           "para que uma moto perto do poste não seja prejudicada."],
          ["<b>Direção</b>", "O facho de barulho cai em cima de qual veículo visto pela câmera?"],
          ["<b>Movimento</b>", "Ao longo de vários instantes, o facho acompanha a mesma moto enquanto ela anda? "
                               "Se o barulho fosse de outro veículo, o facho seguiria outra trajetória."],
          ["<b>Separação</b>", "Existe outro veículo na mesma direção, que não daria para distinguir?"],
      ], [3.2 * cm, LW - 3.2 * cm])]

s += [P("5. E se houver duas motos na mesma cena?", h1),
      P("Esse é o caso mais importante, e o sistema trata de três formas:"),
      P("• <b>Motos em lugares diferentes:</b> cada uma está numa direção diferente em relação ao radar. O facho cai só "
        "sobre a barulhenta, e ela é identificada."),
      P("• <b>Uma moto barulhenta \"vazando\" para a vizinha:</b> parte do som forte de uma moto sempre aparece na "
        "direção das outras. O sistema calcula quanto do barulho pertence a cada veículo e descarta esse vazamento. "
        "Assim, a moto silenciosa não leva a culpa."),
      P("• <b>Motos lado a lado, na mesma direção</b> (por exemplo, no corredor): o radar não consegue ter certeza de "
        "qual das duas fez o barulho. Nesse caso <b>ele não escolhe</b>: o caso vai para revisão humana, com foto e "
        "áudio."),
      img("cena_corredor.png"),
      P("Figura 4 - Duas motos lado a lado: o barulho existe, mas não dá para separar as duas. O caso é marcado "
        "como DÚVIDA e vai para uma pessoa.", leg),
      P("O princípio que guia o projeto é: <b>na dúvida, não multa</b>. É melhor deixar um caso para revisão do que "
        "multar uma pessoa inocente.", destaque)]

s += [P("6. O que acontece depois da detecção", h1),
      P("Quando há uma infração ou um caso duvidoso, o radar monta uma pequena mensagem (um \"evento\") com o horário, "
        "o local, o nível de barulho, quanto passou do limite, a direção, a placa e as evidências (foto e áudio)."),
      P("Essa mensagem é enviada pela internet usando <b>MQTT</b>, um sistema de mensagens leve, feito para aparelhos "
        "de Internet das Coisas. Funciona como um grupo de mensagens: o radar \"publica\" no grupo e o painel da "
        "fiscalização, que está \"inscrito\", recebe na hora. Com vários radares na cidade, todos publicam no mesmo "
        "sistema e o painel recebe de todos."),
      P("No <b>painel</b>, a fiscalização vê a lista de eventos, o mapa dos radares e a imagem da câmera acústica. "
        "O sistema só <i>sugere</i> a autuação: <b>quem decide é o agente de trânsito</b>."),
      tabela([
          ["Situação", "O que o sistema faz"],
          ["Barulho abaixo do limite", "Nada. Nenhum dado é enviado."],
          ["Acima do limite e culpado claro", "Envia o evento como <b>autuação sugerida</b> para o agente confirmar."],
          ["Acima do limite, mas com dúvida", "Envia como <b>revisão humana</b>, com foto e áudio."],
      ], [5.2 * cm, LW - 5.2 * cm])]

s += [P("7. Quem faz o quê no projeto", h1),
      tabela([
          ["Área", "Responsabilidade"],
          ["<b>Mecânica</b>", "A física do som: como o barulho se espalha e enfraquece com a distância, como se somam "
                              "duas fontes em decibéis e quanto o ruído noturno na fachada dos prédios pode cair."],
          ["<b>Elétrica / Automação</b>", "O equipamento: microfones, computador embarcado, câmera, sincronização "
                                          "dos microfones (eles precisam gravar exatamente ao mesmo tempo) e "
                                          "instalação no poste."],
          ["<b>Computação</b>", "O \"cérebro\": simulação, cálculo da direção, separação do som de cada veículo, "
                                "regras de decisão, envio por MQTT e painel da fiscalização."],
      ], [4.2 * cm, LW - 4.2 * cm])]

s += [P("8. O que foi demonstrado", h1),
      P("Como o grupo não tem equipamento de medição, tudo foi <b>simulado em computador</b>: sons sintéticos de motos "
        "normais e adulteradas, a propagação até os microfones e o ruído de fundo da cidade. Os principais "
        "resultados foram:"),
      P("• Nas cenas de demonstração, o sistema apontou corretamente a moto barulhenta e não acusou motos normais "
        "nem carros."),
      P("• Num teste com <b>100 cenas aleatórias</b> com duas motos, <b>nenhuma moto inocente foi multada</b> e "
        "<b>nenhum infrator passou despercebido</b>. Cerca de metade dos casos foi para revisão humana, quase sempre "
        "quando as duas motos estavam na mesma direção."),
      P("• Num cenário ilustrativo, reduzir em 60% as passagens de motos adulteradas (pelo efeito das multas e "
        "pelo efeito educativo) elimina dezenas de picos de barulho por noite em cada avenida.")]

s += [KeepTogether([P("9. Limitações e próximos passos", h1),
      P("Por ser uma simulação, o projeto tem limites que precisam ser resolvidos antes de ir para a rua:"),
      tabela([
          ["Limitação hoje", "Próximo passo"],
          ["Sons e cena simulados", "Medir em campo e calibrar com um decibelímetro profissional."],
          ["Barra de microfones dá só a direção, não a distância", "Usar microfones em cruz ou espiral."],
          ["Leitura da placa simulada", "Reconhecimento automático de placas real."],
          ["Sem validade legal", "Homologação do equipamento (INMETRO) e regulamentação pelos órgãos de trânsito."],
      ], [6.5 * cm, LW - 6.5 * cm])]),
      Spacer(1, 12),
      P("Em resumo: o radar <b>ouve</b>, descobre <b>de onde</b> veio o barulho, <b>confirma</b> com a câmera e "
        "com o movimento do veículo, e <b>avisa</b> a fiscalização. Tudo isso protegendo o sono de quem mora "
        "nas avenidas e sem multar inocentes.", destaque)]


def rodape(c, doc):
    c.saveState()
    c.setFont("DV", 8)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawString(2 * cm, 1.2 * cm, "Radar de Ruído · visão geral do funcionamento")
    c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(doc.page))
    c.restoreState()


destino = PROJ / "Radar_de_Ruido_Como_Funciona.pdf"
SimpleDocTemplate(str(destino), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                  bottomMargin=2 * cm, title="Radar de Ruído - Como funciona",
                  author="Equipe Ciências do Ambiente - UTFPR").build(s, onFirstPage=rodape, onLaterPages=rodape)
print(destino)

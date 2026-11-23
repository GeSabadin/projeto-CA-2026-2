"""
radar_core.py - Nucleo da simulacao do Radar de Ruido (camera acustica).

Pipeline (por quadro de 128 ms):
  1. Sintetiza o som de cada veiculo (moto adulterada / normal / carro) + ruido de fundo.
  2. Propaga ate cada microfone do conjunto linear (atraso r/c e atenuacao 1/r).
  3. Calcula correlacoes cruzadas entre todos os pares de microfones (GCC).
  4. Beamforming (delay-and-sum) em uma grade da via -> mapa de calor acustico.
  5. Mede o nivel de cada veiculo detectado pela camera "apontando" o feixe para ele.
Depois de N quadros: rastreamento + regras de decisao ("na duvida, nao autua").

Simplificacoes (declaradas no relatorio): cena 2D (sem altura), sem Doppler,
sem reflexoes nas fachadas, niveis medidos na banda 300-3000 Hz (aprox. dB(A)).
"""
from __future__ import annotations


import datetime as dt
import uuid
from dataclasses import dataclass, field

import numpy as np
from numpy.fft import irfft, rfft, rfftfreq
from scipy.signal import butter, find_peaks, sosfiltfilt

# ------------------------------------------------------------------ constantes
C_SOM = 343.0          # m/s
FS = 16_000            # Hz
N_QUADRO = 2048        # amostras por quadro (128 ms)
NFFT = 2 * N_QUADRO    # zero-padding -> correlacao linear
UP = 4                 # sobreamostragem da correlacao (resolucao de atraso)
P_REF = 20e-6          # Pa
BANDA = (300.0, 3000.0)
D_REF = 7.5            # m (distancia de referencia, como no ensaio de passagem ISO 362)

STATUS_OK = "OK"
STATUS_REVISAO = "REVISAO_HUMANA"
STATUS_AUTUA = "AUTUACAO_SUGERIDA"

_SOS_BANDA = butter(4, BANDA, btype="bandpass", fs=FS, output="sos")


# ------------------------------------------------------------------ acustica basica
def db_para_pa(L):
    return P_REF * 10 ** (np.asarray(L, float) / 20)


def pa_para_db(p):
    return 20 * np.log10(np.maximum(np.asarray(p, float), 1e-12) / P_REF)


def soma_db(niveis):
    """Soma energetica de fontes: 90 dB + 90 dB = 93 dB."""
    return 10 * np.log10(np.sum(10 ** (np.asarray(niveis, float) / 10)))


def nivel_na_distancia(L_ref, d_ref, d):
    """Divergencia esferica: -6 dB a cada dobro de distancia."""
    return L_ref - 20 * np.log10(np.asarray(d, float) / d_ref)


# ------------------------------------------------------------------ cena
@dataclass
class Veiculo:
    nome: str
    placa: str
    tipo: str            # "moto" | "carro"
    x0: float            # m, posicao ao longo da via no instante t=0
    y: float             # m, distancia ate o radar (faixa)
    v: float             # m/s
    L75: float           # dB (banda) a 7,5 m - "verdade" da simulacao
    adulterado: bool = False
    rpm: float = 6000.0

    def pos(self, t):
        return np.array([self.x0 + self.v * t, self.y])


@dataclass
class ConfigArray:
    n_mics: int = 16
    espacamento: float = 0.06    # m -> abertura 0,90 m; sem aliasing espacial ate ~2,9 kHz
    jitter_us: float = 0.0       # erro de sincronizacao entre microfones (desvio-padrao)

    def posicoes(self):
        x = (np.arange(self.n_mics) - (self.n_mics - 1) / 2) * self.espacamento
        return np.column_stack([x, np.zeros(self.n_mics)])

    def pesos(self):
        return np.hamming(self.n_mics) if self.n_mics > 3 else np.ones(self.n_mics)

    @property
    def abertura(self):
        return (self.n_mics - 1) * self.espacamento

    def largura_feixe_deg(self, theta_deg, f=1500.0):
        """Largura aproximada do lobulo principal (Hamming alarga ~1,3x)."""
        lam = C_SOM / f
        s = max(np.sin(np.radians(theta_deg)), 0.3)
        return float(np.degrees(1.3 * 0.886 * lam / (self.abertura * s)))


# ------------------------------------------------------------------ sintese do som
def sinal_veiculo(veic: Veiculo, n: int, rng: np.random.Generator) -> np.ndarray:
    """Som sintetico normalizado (RMS = 1 na banda de analise)."""
    t = np.arange(n) / FS
    cil = 1 if veic.tipo == "moto" else 4
    f0 = veic.rpm / 120 * cil * rng.uniform(0.95, 1.05)       # frequencia de explosao
    k = np.arange(1, int(5000 / f0) + 1)
    expo = 0.8 if veic.adulterado else 1.6                    # adulterada: harmonicos fortes
    amp = 1.0 / k ** expo
    fase = rng.uniform(0, 2 * np.pi, k.size)
    harm = (amp[:, None] * np.sin(2 * np.pi * f0 * k[:, None] * t[None, :] + fase[:, None])).sum(0)
    harm /= np.std(harm) + 1e-12

    ruido = rng.standard_normal(n)
    if veic.adulterado:
        s = 0.7 * harm + 1.0 * ruido
        # "estouros" de escapamento: rajadas impulsivas
        for p in rng.integers(0, n - 200, rng.poisson(10 * n / FS) + 1):
            m = min(200, n - p)
            s[p:p + m] += 6 * np.exp(-np.arange(m) / (0.002 * FS)) * rng.standard_normal(m)
    else:
        corte = 1200 if veic.tipo == "moto" else 800           # silenciador abafa os agudos
        ruido = sosfiltfilt(butter(4, corte, fs=FS, output="sos"), ruido)
        s = 1.0 * harm + 0.5 * ruido / (np.std(ruido) + 1e-12)
    return s / (np.std(sosfiltfilt(_SOS_BANDA, s)) + 1e-12)


def _sinal_fundo(n, rng):
    r = sosfiltfilt(butter(2, 1000, fs=FS, output="sos"), rng.standard_normal(n))
    return r / (np.std(sosfiltfilt(_SOS_BANDA, r)) + 1e-12)


def simular_quadro(veiculos, t, cfg: ConfigArray, rng, fundo_db=60.0, erro_sinc=None):
    """Sinais dos M microfones (Pa) durante um quadro que comeca no instante t."""
    mics = cfg.posicoes()
    M = len(mics)
    pad = 1024                                   # > maior atraso (evita "volta" circular)
    ntot = N_QUADRO + pad
    f = rfftfreq(ntot, 1 / FS)
    e = np.zeros(M) if erro_sinc is None else erro_sinc
    X = np.zeros((M, f.size), complex)

    fontes = [(v.pos(t), v.L75, sinal_veiculo(v, ntot, rng)) for v in veiculos]
    # transito distante: 3 fontes a 40-80 m que somam ~fundo_db no radar
    for _ in range(3):
        ang, dist = rng.uniform(0.2, np.pi - 0.2), rng.uniform(40, 80)
        L_arr = fundo_db - 10 * np.log10(3)
        fontes.append((np.array([dist * np.cos(ang), dist * np.sin(ang)]),
                       L_arr + 20 * np.log10(dist / D_REF), _sinal_fundo(ntot, rng)))

    for pos, L75, s in fontes:
        r = np.linalg.norm(mics - pos, axis=1)
        amp = db_para_pa(L75) * D_REF / r
        tau = r / C_SOM + e
        X += amp[:, None] * rfft(s)[None, :] * np.exp(-2j * np.pi * f[None, :] * tau[:, None])
    x = irfft(X, n=ntot, axis=1)[:, pad:pad + N_QUADRO]
    x += db_para_pa(30.0) * rng.standard_normal(x.shape)       # ruido eletrico do MEMS
    return x


# ------------------------------------------------------------------ localizacao
class Localizador:
    """Beamforming delay-and-sum calculado a partir das correlacoes cruzadas (GCC)."""

    def __init__(self, cfg: ConfigArray):
        self.cfg = cfg
        self.mics = cfg.posicoes()
        M = len(self.mics)
        self.i, self.j = np.triu_indices(M, 0)               # inclui i == j (autocorrelacao)
        w = cfg.pesos()
        self.coef = w[self.i] * w[self.j] * np.where(self.i == self.j, 1.0, 2.0) / w.sum() ** 2
        f = rfftfreq(NFFT, 1 / FS)
        self.f = f
        self.mask = (f >= BANDA[0]) & (f <= BANDA[1])
        self.L = NFFT * UP
        # grades fixas
        self.gx = np.arange(-15, 15.01, 0.25)
        self.gy = np.arange(1.0, 11.01, 0.25)
        GX, GY = np.meshgrid(self.gx, self.gy)
        self._idx_cart = self._indices(np.column_stack([GX.ravel(), GY.ravel()]))
        self.ang = np.arange(0, 181, 1.0)
        self.raios = np.arange(2.0, 16.01, 0.5)
        A, Rr = np.meshgrid(np.radians(self.ang), self.raios, indexing="ij")
        self._idx_polar = self._indices(np.column_stack([(Rr * np.cos(A)).ravel(), (Rr * np.sin(A)).ravel()]))

    def _indices(self, pts):
        r = np.linalg.norm(pts[:, None, :] - self.mics[None, :, :], axis=2)
        lag = (r[:, self.i] - r[:, self.j]) / C_SOM * FS * UP
        return np.round(lag).astype(np.int64) % self.L

    def correlacoes(self, x, phat=False):
        X = rfft(x, n=NFFT, axis=1)
        cross = X[self.i] * np.conj(X[self.j]) * self.mask
        if phat:
            cross = cross / (np.abs(cross) + 1e-20)
        return irfft(cross, n=self.L, axis=1) * UP / N_QUADRO

    def _pot(self, R, idx):
        return (R[np.arange(R.shape[0])[None, :], idx] * self.coef[None, :]).sum(1)

    def potencia_pontos(self, R, pts):
        return self._pot(R, self._indices(np.atleast_2d(pts)))

    def mapa_cartesiano_db(self, R):
        p = self._pot(R, self._idx_cart).reshape(len(self.gy), len(self.gx))
        return 10 * np.log10(np.maximum(p, 1e-20) / P_REF ** 2)

    def perfil_angular_db(self, R):
        p = self._pot(R, self._idx_polar).reshape(len(self.ang), len(self.raios)).max(1)
        return 10 * np.log10(np.maximum(p, 1e-20) / P_REF ** 2)

    def potencia_deconvoluida(self, x, pts):
        """Separa a potencia de cada veiculo (estilo DAMAS): P_feixe = A @ p_fontes, resolvido com NNLS.
        Remove o 'vazamento' de uma moto barulhenta para o feixe apontado para a vizinha."""
        from scipy.optimize import nnls
        X = rfft(x, n=NFFT, axis=1)[:, self.mask]
        fb = self.f[self.mask]
        Pf = (np.abs(X) ** 2).mean(0)
        wf = Pf / Pf.sum()
        w = self.cfg.pesos()
        r = np.linalg.norm(np.atleast_2d(pts)[:, None, :] - self.mics[None], axis=2)           # V,M
        dr = r[:, None, :] - r[None, :, :]                                                   # V,U,M
        resp = (w[None, None, :, None] * np.exp(2j * np.pi * fb * dr[..., None] / C_SOM)).sum(2) / w.sum()
        A = (np.abs(resp) ** 2 * wf).sum(-1)                                                 # V,U
        A = np.column_stack([A, np.full(len(A), (w ** 2).sum() / w.sum() ** 2)])           # + ruido difuso
        b = self._pot(self.correlacoes(x), self._indices(np.atleast_2d(pts)))
        p, _ = nnls(A, b)
        return np.maximum(p[:-1], P_REF ** 2 * 10 ** 3)                                     # piso de 30 dB

    def espectro_feixe(self, x, pos):
        """Espectro do sinal 'focado' em pos (delay-and-sum no dominio da frequencia)."""
        X = rfft(x, n=NFFT, axis=1)
        r = np.linalg.norm(self.mics - pos, axis=1)
        w = self.cfg.pesos()
        Y = (w[:, None] * X * np.exp(2j * np.pi * self.f[None, :] * r[:, None] / C_SOM)).sum(0) / w.sum()
        return np.abs(Y) ** 2


_CACHE_LOC: dict = {}


def get_localizador(cfg: ConfigArray) -> Localizador:
    chave = (cfg.n_mics, cfg.espacamento)
    if chave not in _CACHE_LOC:
        _CACHE_LOC[chave] = Localizador(cfg)
    return _CACHE_LOC[chave]


# ------------------------------------------------------------------ analise da cena
@dataclass
class Resultado:
    veiculos: list
    cfg: ConfigArray
    tempos: np.ndarray
    limite: float
    margem: float
    perfis: list = field(default_factory=list)       # perfil angular (dB) por quadro
    picos: list = field(default_factory=list)        # angulos dos picos por quadro
    mapas: list = field(default_factory=list)        # mapa cartesiano (dB) por quadro
    L75_est: np.ndarray = None                       # [quadro, veiculo]
    ang_veic: np.ndarray = None                      # [quadro, veiculo]
    hf: np.ndarray = None                            # fracao de energia 1,5-3 kHz
    decisoes: list = field(default_factory=list)


def angulo(pos):
    return float(np.degrees(np.arctan2(pos[1], pos[0])))


def analisar_cena(veiculos, cfg=None, n_quadros=8, dt_q=0.15, limite=80.0, margem=2.0,
                  fundo_db=60.0, seed=0, gerar_mapas=True) -> Resultado:
    cfg = cfg or ConfigArray()
    rng = np.random.default_rng(seed)
    loc = get_localizador(cfg)
    erro = rng.normal(0, cfg.jitter_us * 1e-6, cfg.n_mics)
    tempos = np.arange(n_quadros) * dt_q
    nv = len(veiculos)
    res = Resultado(veiculos, cfg, tempos, limite, margem,
                    L75_est=np.zeros((n_quadros, nv)), ang_veic=np.zeros((n_quadros, nv)),
                    hf=np.zeros((n_quadros, nv)))
    banda_alta = (loc.f >= 1500) & (loc.f <= BANDA[1])
    for k, t in enumerate(tempos):
        x = simular_quadro(veiculos, t, cfg, rng, fundo_db, erro)
        R = loc.correlacoes(x)
        perfil = loc.perfil_angular_db(R)
        pk, _ = find_peaks(np.r_[-np.inf, perfil, -np.inf], prominence=2.0, height=perfil.max() - 20)
        res.perfis.append(perfil)
        res.picos.append(loc.ang[pk - 1])
        if gerar_mapas:
            res.mapas.append(loc.mapa_cartesiano_db(R))
        pts = np.array([v.pos(t) for v in veiculos])
        L_arr = 10 * np.log10(loc.potencia_deconvoluida(x, pts) / P_REF ** 2)
        dist = np.linalg.norm(pts, axis=1)
        res.L75_est[k] = L_arr + 20 * np.log10(dist / D_REF)
        res.ang_veic[k] = [angulo(p) for p in pts]
        for n, p in enumerate(pts):
            E = loc.espectro_feixe(x, p)
            res.hf[k, n] = E[banda_alta].sum() / (E[loc.mask].sum() + 1e-30)
    res.decisoes = decidir(res)
    return res


def decidir(res: Resultado):
    """Regras de decisao por veiculo. Principio: na duvida, NAO autua."""
    cfg, lim, mg = res.cfg, res.limite, res.margem
    K, nv = res.L75_est.shape
    out = []
    for n in range(nv):
        validos, ambiguos, dominados, seguidos = [], 0, 0, 0
        for k in range(K):
            th = res.ang_veic[k, n]
            bw = cfg.largura_feixe_deg(th)
            outros = [u for u in range(nv) if u != n]
            sep = {u: abs(res.ang_veic[k, u] - th) for u in outros}
            if any(sep[u] < bw for u in outros):
                ambiguos += 1                   # outro veiculo dentro do mesmo feixe
                continue
            if any(sep[u] < 2 * bw and res.L75_est[k, u] > res.L75_est[k, n] for u in outros):
                dominados += 1                  # leitura pode ser "vazamento" de vizinho mais forte
                continue
            validos.append(k)
            if len(res.picos[k]) and np.min(np.abs(res.picos[k] - th)) < bw / 2:
                seguidos += 1                   # o pico acustico acompanha o veiculo
        L_med = float(np.median(res.L75_est[:, n]))
        L_val = float(np.median(res.L75_est[validos, n])) if validos else L_med
        hf = float(np.median(res.hf[:, n]))
        frac_seg = seguidos / max(len(validos), 1)
        conf = min(1.0, len(validos) / K) * frac_seg * min(1.0, max(0.0, (L_val - lim) / (2 * mg) + 0.5))

        if L_med < lim - mg:
            status, motivo = STATUS_OK, "nivel abaixo do limite"
        elif not validos and ambiguos:
            status, motivo = STATUS_REVISAO, "fonte ambigua: outro veiculo na mesma direcao em todos os quadros"
        elif seguidos == 0 and any(np.median(res.L75_est[:, u]) > L_med + 6 for u in range(nv) if u != n):
            status, motivo = STATUS_OK, "sem pico acustico proprio: som vem de veiculo vizinho mais ruidoso"
        elif len(validos) < 3:
            status, motivo = STATUS_REVISAO, f"poucos quadros validos ({len(validos)}/{K})"
        elif frac_seg < 0.6:
            status, motivo = STATUS_REVISAO, "pico acustico nao acompanha o movimento do veiculo"
        elif L_val < lim + mg:
            status, motivo = STATUS_REVISAO if L_val >= lim - mg else STATUS_OK, "nivel dentro da margem de incerteza"
        else:
            status, motivo = STATUS_AUTUA, "nivel acima do limite + rastreamento consistente"
        classe = ("escapamento_adulterado_provavel" if hf > 0.3 else "ruido_excessivo") if L_val >= lim - mg else "normal"
        out.append(dict(veiculo=res.veiculos[n].nome, placa=res.veiculos[n].placa, status=status,
                        motivo=motivo, L75=round(L_val, 1), L75_todos=round(L_med, 1), hf=round(hf, 2),
                        classe=classe, quadros_validos=len(validos), quadros_ambiguos=ambiguos,
                        quadros_dominados=dominados, fracao_rastreada=round(frac_seg, 2),
                        confianca=round(conf, 2)))
    return out


# ------------------------------------------------------------------ cenarios prontos
def cenario(nome: str):
    if nome == "Duas motos em faixas diferentes":
        return [Veiculo("Moto A", "SIM0A01", "moto", -9.0, 3.5, 12.5, 94.0, True, 7000),
                Veiculo("Moto B", "SIM0B02", "moto", -2.0, 7.0, 11.0, 75.0, False, 5000)]
    if nome == "Duas motos lado a lado (corredor)":
        return [Veiculo("Moto A", "SIM0A01", "moto", -6.0, 3.5, 12.0, 94.0, True, 7000),
                Veiculo("Moto B", "SIM0B02", "moto", -6.0, 4.5, 12.0, 75.0, False, 5000)]
    if nome == "Moto adulterada + carro + moto normal":
        return [Veiculo("Moto A", "SIM0A01", "moto", -2.0, 7.0, 10.0, 92.0, True, 6500),
                Veiculo("Carro C", "SIM0C03", "carro", -12.0, 3.5, 13.0, 72.0, False, 2500),
                Veiculo("Moto B", "SIM0B02", "moto", 6.0, 3.5, 9.0, 76.0, False, 5000)]
    if nome == "Somente motos normais":
        return [Veiculo("Moto A", "SIM0A01", "moto", -9.0, 3.5, 12.5, 76.0, False, 5500),
                Veiculo("Moto B", "SIM0B02", "moto", -2.0, 7.0, 11.0, 74.0, False, 5000)]
    raise ValueError(nome)


CENARIOS = ["Duas motos em faixas diferentes", "Duas motos lado a lado (corredor)",
            "Moto adulterada + carro + moto normal", "Somente motos normais"]


def cenario_aleatorio(rng):
    faixas = [3.5, 7.0]
    ya = rng.choice(faixas)
    yb = rng.choice(faixas + [ya + 1.0])                       # as vezes no "corredor"
    xa, xb = rng.uniform(-10, 4, 2)
    va = rng.uniform(8, 16)
    vb = va if abs(yb - ya) == 1.0 else rng.uniform(8, 16)
    if abs(yb - ya) == 1.0:
        xb = xa + rng.uniform(-1, 1)
    return [Veiculo("Moto A", "SIM0A01", "moto", xa, ya, va, rng.uniform(86, 98), True, rng.uniform(5000, 8000)),
            Veiculo("Moto B", "SIM0B02", "moto", xb, yb, vb, rng.uniform(70, 77), False, rng.uniform(4000, 6000))]


def avaliar(n_cenas=50, seed=123, cfg=None, limite=80.0, margem=2.0, progresso=None):
    """Monte Carlo: moto A e sempre a adulterada (verdade), moto B a normal."""
    rng = np.random.default_rng(seed)
    cont = dict(acerto=0, revisao=0, perdido=0, falso_positivo=0)
    for c in range(n_cenas):
        res = analisar_cena(cenario_aleatorio(rng), cfg, seed=int(rng.integers(1 << 30)),
                            limite=limite, margem=margem, gerar_mapas=False)
        a, b = res.decisoes
        if b["status"] == STATUS_AUTUA:
            cont["falso_positivo"] += 1
        elif a["status"] == STATUS_AUTUA:
            cont["acerto"] += 1
        elif a["status"] == STATUS_REVISAO:
            cont["revisao"] += 1
        else:
            cont["perdido"] += 1
        if progresso:
            progresso((c + 1) / n_cenas)
    return cont


# ------------------------------------------------------------------ impacto (M4)
def lnight(L_fundo, n_eventos, L_evento, dur_s, horas=9.0):
    """Nivel equivalente noturno (22h-7h) somando fundo + eventos de passagem."""
    T = horas * 3600
    E = 10 ** (L_fundo / 10) * T + n_eventos * 10 ** (L_evento / 10) * dur_s
    return 10 * np.log10(E / T)


# ------------------------------------------------------------------ evento MQTT
RADARES = [
    dict(radar_id="CWB-R01", via="Av. Sete de Setembro (Batel)", lat=-25.4400, lon=-49.2780),
    dict(radar_id="CWB-R02", via="Av. Batel", lat=-25.4425, lon=-49.2893),
    dict(radar_id="CWB-R03", via="Av. Sete de Setembro (Centro)", lat=-25.4380, lon=-49.2670),
]


def gerar_eventos(res: Resultado, radar=None, quando=None):
    radar = radar or RADARES[0]
    quando = quando or dt.datetime.now(dt.timezone(dt.timedelta(hours=-3)))
    eventos = []
    for n, d in enumerate(res.decisoes):
        if d["status"] == STATUS_OK:
            continue
        v = res.veiculos[n]
        k_max = int(np.argmax(res.L75_est[:, n]))
        eid = str(uuid.uuid4())
        eventos.append({
            "id_evento": eid,
            "radar_id": radar["radar_id"],
            "local": {"via": radar["via"], "lat": radar["lat"], "lon": radar["lon"]},
            "timestamp": (quando + dt.timedelta(seconds=float(res.tempos[k_max]))).isoformat(timespec="seconds"),
            "nivel_db_7m5": d["L75"],
            "limite_db": res.limite,
            "excesso_db": round(d["L75"] - res.limite, 1),
            "banda_hz": list(BANDA),
            "direcao_graus": round(float(res.ang_veic[k_max, n]), 1),
            "trajetoria_graus": [round(float(a), 1) for a in res.ang_veic[:, n]],
            "classificacao": d["classe"],
            "confianca": d["confianca"],
            "status": d["status"],
            "motivo": d["motivo"],
            "veiculo": {"placa": v.placa, "tipo": v.tipo, "distancia_m": v.y,
                        "velocidade_kmh": round(v.v * 3.6)},
            "evidencias": {"foto": f"evidencias/{eid}.png", "audio": f"evidencias/{eid}.wav"},
            "versao": "sim-1.0",
        })
    return eventos

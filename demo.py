"""Demonstracao em linha de comando (gera figuras e o JSON de exemplo).

    python demo.py              -> roda os cenarios, salva figuras em saida/
    python demo.py --avaliar 100
"""
import json
import sys
from pathlib import Path

import radar_core as rc
import visual

if "--avaliar" in sys.argv:
    n = int(sys.argv[sys.argv.index("--avaliar") + 1])
    r = rc.avaliar(n)
    print({k: f"{100 * v / n:.0f}%" for k, v in r.items()})
    sys.exit()

out = Path("saida")
out.mkdir(exist_ok=True)
for i, nome in enumerate(rc.CENARIOS):
    res = rc.analisar_cena(rc.cenario(nome), seed=1)
    print(f"\n== {nome}")
    for d in res.decisoes:
        print(f"   {d['veiculo']:8s} {d['placa']}  {d['L75']:5.1f} dB  {d['status']:18s} {d['motivo']}")
    visual.desenhar_cena(res, 4).savefig(out / f"cena{i + 1}.png", dpi=110)
    ev = rc.gerar_eventos(res)
    if ev and i == 0:
        Path("evento_exemplo.json").write_text(json.dumps(ev[0], ensure_ascii=False, indent=2), encoding="utf-8")
print("\nFiguras em saida/, evento em evento_exemplo.json")

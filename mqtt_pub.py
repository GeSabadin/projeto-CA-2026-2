"""Publicacao/assinatura dos eventos do radar via MQTT (paho-mqtt 2.x ou 1.x)."""
import json
import sys

import paho.mqtt.client as mqtt

TOPICO_PADRAO = "cwb/radar-ruido/{radar_id}/eventos"


def _cliente(nome):
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=nome)
    except AttributeError:          # paho 1.x
        return mqtt.Client(client_id=nome)


def publicar(eventos, host="localhost", porta=1883, topico=TOPICO_PADRAO, timeout=5):
    cli = _cliente("radar-ruido-sim")
    cli.connect(host, porta, keepalive=10)
    cli.loop_start()
    try:
        for ev in eventos:
            info = cli.publish(topico.format(radar_id=ev["radar_id"]),
                               json.dumps(ev, ensure_ascii=False), qos=1)
            info.wait_for_publish(timeout)
    finally:
        cli.loop_stop()
        cli.disconnect()
    return len(eventos)


if __name__ == "__main__":
    # Assinante simples (lado da fiscalizacao): python mqtt_pub.py [host]
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    cli = _cliente("painel-fiscalizacao")

    def ao_receber(c, u, msg, *a):
        ev = json.loads(msg.payload)
        print(f"[{ev['timestamp']}] {ev['radar_id']} placa={ev['veiculo']['placa']} "
              f"{ev['nivel_db_7m5']} dB (lim {ev['limite_db']}) -> {ev['status']} | {ev['motivo']}")

    cli.on_message = ao_receber
    cli.connect(host, 1883)
    cli.subscribe("cwb/radar-ruido/+/eventos", qos=1)
    print(f"Aguardando eventos em {host} ... (Ctrl+C para sair)")
    cli.loop_forever()

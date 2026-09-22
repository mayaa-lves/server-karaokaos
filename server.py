import random
import socketio
from fastapi import FastAPI

fastapi_app = FastAPI()
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
salas = {}

@fastapi_app.get("/")
async def inicio():
    return {"status": "online", "mensagem": "Servidor Karaokaos funcionando!"}

@sio.event
async def connect(sid, environ):
    print(f"Conectado: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Desconectado: {sid}")
    salas_para_remover = []
    for pin, sala in list(salas.items()):
        if sala["host"] == sid:
            salas_para_remover.append(pin)
            continue
        jogadores_antes = len(sala["jogadores"])
        sala["jogadores"] = [j for j in sala["jogadores"] if j["sid"] != sid]
        if len(sala["jogadores"]) != jogadores_antes:
            await sio.emit("jogadores_atualizados", {"jogadores": sala["jogadores"]}, to=sala["host"])
    for pin in salas_para_remover:
        del salas[pin]

def gerar_pin():
    while True:
        pin = str(random.randint(1000, 9999))
        if pin not in salas:
            return pin

@sio.event
async def criar_sala(sid):
    pin = gerar_pin()
    salas[pin] = {"host": sid, "jogadores": []}
    print(f"Sala criada: {pin}")
    return {"sucesso": True, "pin": pin}

@sio.event
async def entrar_sala(sid, dados):
    pin = str(dados.get("pin", "")).strip()
    nome = str(dados.get("nome", "")).strip()
    if not pin:
        return {"sucesso": False, "erro": "Digite o PIN da sala."}
    if pin not in salas:
        return {"sucesso": False, "erro": "Sala não encontrada."}
    if not nome:
        return {"sucesso": False, "erro": "Digite seu nome."}
    sala = salas[pin]
    jogador_existente = next((j for j in sala["jogadores"] if j["sid"] == sid), None)
    if jogador_existente:
        return {"sucesso": True, "jogador": jogador_existente["numero"]}
    if len(sala["jogadores"]) >= 2:
        return {"sucesso": False, "erro": "A sala já está cheia."}
    numeros_usados = {j["numero"] for j in sala["jogadores"]}
    numero = 1 if 1 not in numeros_usados else 2
    jogador = {"sid": sid, "nome": nome, "numero": numero}
    sala["jogadores"].append(jogador)
    await sio.enter_room(sid, pin)
    print(f"{nome} entrou na sala {pin} como Jogador {numero}")
    await sio.emit("jogadores_atualizados", {"jogadores": sala["jogadores"]}, to=sala["host"])
    return {"sucesso": True, "jogador": numero}

@sio.event
async def iniciar_partida(sid, dados):
    pin = str(dados.get("pin", "")).strip()
    if pin not in salas:
        return
    sala = salas[pin]
    if sala["host"] != sid:
        return
    print(f"Partida iniciada na sala {pin}")
    await sio.emit("iniciar_partida", {"pin": pin}, room=pin)

@sio.event
async def dados_microfone(sid, dados):
    pin = str(dados.get("pin", "")).strip()
    if pin not in salas:
        return
    sala = salas[pin]
    jogador = next((item for item in sala["jogadores"] if item["sid"] == sid), None)
    if jogador is None:
        return
    try:
        volume = float(dados.get("volume", 0))
    except (TypeError, ValueError):
        volume = 0.0
    volume = max(0.0, min(volume, 1.0))
    frequencia_bruta = dados.get("frequencia")
    frequencia = None
    if frequencia_bruta is not None:
        try:
            frequencia_convertida = float(frequencia_bruta)
            if 80 <= frequencia_convertida <= 1000:
                frequencia = frequencia_convertida
        except (TypeError, ValueError):
            frequencia = None
    payload = {"jogador": jogador["numero"], "nome": jogador["nome"], "volume": volume, "frequencia": frequencia}
    await sio.emit("dados_microfone", payload, to=sala["host"])

app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

"""Analisador do prato: estima o mix (carne / guarnição / salada / outros) a partir da foto.

Dois modos:
  1. IA de visão (Gemini, chave gratuita do Google AI Studio): a foto é enviada ao modelo,
     que devolve as proporções em JSON.
  2. Simulado: sem chave (ou se a chamada falhar), gera uma estimativa aleatória e avisa
     que é simulada. Serve para demonstrar o fluxo completo sem custo.

A chave vem do campo na barra lateral do painel ou da variável de ambiente GEMINI_API_KEY.
Ela NUNCA deve ser salva em arquivo nem enviada ao GitHub.
"""
import base64
import json
import os
import random
import re
import urllib.error
import urllib.request

from custos import CATEGORIAS, calcular_margem, normalizar_mix

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Modelos tentados, em ordem. O primeiro que responder fica guardado para as próximas chamadas.
MODELOS_PREFERIDOS = [
    m for m in [os.getenv("RAIOX_MODELO_GEMINI"), "gemini-3.8-flash", "gemini-2.5-flash", "gemini-flash-latest"] if m
]

PROMPT = (
    "Você analisa fotos de pratos de restaurante por quilo (self-service). "
    "Estime a proporção do prato ocupada por cada categoria: "
    "carne (churrasco, carnes, frango, linguiça, peixe), "
    "guarnicao (arroz, feijão, massas, farofa, purê, batata cozida), "
    "salada (folhas, legumes, verduras, vinagrete) e "
    "outros (frituras, ovo, molhos, frutas, sobremesa, o que não se encaixa). "
    "As quatro proporções devem somar 1. Se a imagem não mostrar um prato de comida, "
    'devolva tudo 0 e explique na observacao. Responda APENAS com JSON no formato: '
    '{"carne": 0.0, "guarnicao": 0.0, "salada": 0.0, "outros": 0.0, '
    '"itens": ["item 1", "item 2"], "observacao": "frase curta em português"}'
)

_modelo_escolhido = None  # cache do modelo que funcionou


class ErroIA(Exception):
    """Erro com mensagem amigável para mostrar no painel."""


# ---------------------------------------------------------------- modo simulado
def _mix_simulado(seed=None):
    rng = random.Random(seed)
    alfa = [3.5, 3.5, 2.5, 0.5]
    if rng.random() < 0.2:
        alfa = [9.0, 2.0, 1.5, 0.5]
    partes = [rng.gammavariate(a, 1) for a in alfa]
    total = sum(partes)
    return {c: p / total for c, p in zip(CATEGORIAS, partes)}


# ---------------------------------------------------------------- HTTP
def _requisitar(url, chave, corpo=None, usar_bearer=False):
    """Faz GET (corpo=None) ou POST JSON e devolve o JSON da resposta."""
    cabecalhos = {"Content-Type": "application/json"}
    if usar_bearer:
        cabecalhos["Authorization"] = f"Bearer {chave}"
    else:
        cabecalhos["x-goog-api-key"] = chave
    dados = json.dumps(corpo).encode() if corpo is not None else None
    requisicao = urllib.request.Request(url, data=dados, headers=cabecalhos)
    with urllib.request.urlopen(requisicao, timeout=45) as resposta:
        return json.loads(resposta.read().decode())


def _mensagem_http(erro):
    try:
        corpo = json.loads(erro.read().decode())
        return corpo.get("error", {}).get("message") or str(corpo)[:200]
    except Exception:
        return erro.reason if hasattr(erro, "reason") else str(erro)


def _chamar(url, chave, corpo=None):
    """Tenta com o cabeçalho de chave; se a autenticação falhar, tenta como token Bearer."""
    try:
        return _requisitar(url, chave, corpo)
    except urllib.error.HTTPError as erro:
        if erro.code in (401, 403) and not chave.startswith("AIza"):
            return _requisitar(url, chave, corpo, usar_bearer=True)
        raise


# ---------------------------------------------------------------- leitura da resposta
def _textos(obj):
    """Percorre a resposta JSON e devolve todos os textos encontrados nela."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for valor in obj.values():
            yield from _textos(valor)
    elif isinstance(obj, list):
        for valor in obj:
            yield from _textos(valor)


def _extrair_resultado(resposta_json):
    for texto in _textos(resposta_json):
        if '"carne"' not in texto:
            continue
        inicio, fim = texto.find("{"), texto.rfind("}")
        if inicio == -1 or fim <= inicio:
            continue
        try:
            dados = json.loads(texto[inicio:fim + 1])
        except json.JSONDecodeError:
            continue
        brutos = {c: float(dados.get(c, 0) or 0) for c in CATEGORIAS}
        if sum(brutos.values()) <= 0:
            raise ErroIA("A IA não reconheceu um prato de comida na imagem. "
                         + str(dados.get("observacao", "")))
        return {
            "mix": normalizar_mix(brutos),
            "itens": [str(i) for i in dados.get("itens", [])][:12],
            "observacao": str(dados.get("observacao", "")),
        }
    raise ErroIA("A resposta da IA não trouxe o JSON esperado.")


# ---------------------------------------------------------------- Gemini
def _descobrir_modelos(chave):
    """Lista os modelos 'flash' disponíveis para a chave (mais novos primeiro)."""
    try:
        lista = _chamar(f"{BASE_URL}/models?pageSize=200", chave).get("models", [])
    except Exception:
        return []
    nomes = []
    for m in lista:
        nome = m.get("name", "").replace("models/", "")
        metodos = m.get("supportedGenerationMethods", [])
        if "flash" in nome and "generateContent" in metodos and not re.search(r"image|tts|audio|live|embed", nome):
            nomes.append(nome)
    return sorted(nomes, reverse=True)


def _gerar(modelo, chave, imagem_b64, media_type):
    corpo = {
        "contents": [{"parts": [
            {"text": PROMPT},
            {"inline_data": {"mime_type": media_type, "data": imagem_b64}},
        ]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    return _chamar(f"{BASE_URL}/models/{modelo}:generateContent", chave, corpo)


def _interactions(modelo, chave, imagem_b64, media_type):
    corpo = {"model": modelo, "input": [
        {"type": "text", "text": PROMPT},
        {"type": "image", "data": imagem_b64, "mime_type": media_type},
    ]}
    return _chamar(f"{BASE_URL}/interactions", chave, corpo)


def analisar_com_gemini(imagem_bytes, media_type, chave):
    """Devolve (resultado, modelo_usado). Levanta ErroIA com mensagem clara se não conseguir."""
    global _modelo_escolhido
    imagem_b64 = base64.b64encode(imagem_bytes).decode()

    candidatos = [_modelo_escolhido] if _modelo_escolhido else []
    candidatos += [m for m in MODELOS_PREFERIDOS if m not in candidatos]
    ultimo_erro = None
    descobriu = False

    i = 0
    while i < len(candidatos):
        modelo = candidatos[i]
        i += 1
        for funcao in (_gerar, _interactions):
            try:
                resultado = _extrair_resultado(funcao(modelo, chave, imagem_b64, media_type))
                _modelo_escolhido = modelo
                return resultado, modelo
            except ErroIA:
                raise
            except urllib.error.HTTPError as erro:
                msg = _mensagem_http(erro)
                if erro.code in (401, 403):
                    raise ErroIA(f"Chave recusada pelo Google ({erro.code}): {msg}")
                if erro.code == 429:
                    raise ErroIA("Limite gratuito da API atingido no momento. Aguarde um minuto e tente de novo.")
                ultimo_erro = f"{modelo}: HTTP {erro.code} - {msg}"
            except urllib.error.URLError as erro:
                raise ErroIA(f"Sem conexão com o Google ({erro.reason}).")
            except Exception as erro:
                ultimo_erro = f"{modelo}: {type(erro).__name__} - {erro}"
        if i == len(candidatos) and not descobriu:
            descobriu = True
            candidatos += [m for m in _descobrir_modelos(chave) if m not in candidatos][:4]

    raise ErroIA(f"Nenhum modelo respondeu. Último erro: {ultimo_erro}")


# ---------------------------------------------------------------- função principal
def analisar_prato(peso_g, imagem_bytes=None, media_type="image/jpeg", seed=None,
                   custo_kg=None, preco_kg=None, chave=None):
    """Devolve dict com mix, itens, margem, fonte da análise e observação."""
    chave = (chave or os.getenv("GEMINI_API_KEY") or "").strip()
    resultado = None
    erro_ia = None
    fonte = "simulado"
    observacao = "Estimativa SIMULADA: configure a chave da IA para analisar a foto de verdade."

    if imagem_bytes and chave:
        try:
            resultado, modelo = analisar_com_gemini(imagem_bytes, media_type, chave)
            fonte = f"IA de visão ({modelo})"
            observacao = resultado["observacao"]
        except ErroIA as erro:
            erro_ia = str(erro)
        except Exception as erro:
            erro_ia = f"Falha inesperada na IA ({type(erro).__name__}: {erro})."
        if erro_ia:
            observacao = f"{erro_ia} Usando estimativa simulada."

    if resultado is None:
        resultado = {"mix": _mix_simulado(seed), "itens": []}

    margem_args = {"custo_kg": custo_kg}
    if preco_kg:
        margem_args["preco_kg"] = preco_kg
    return {
        "mix": resultado["mix"],
        "itens": resultado.get("itens", []),
        "fonte": fonte,
        "ia_real": fonte != "simulado",
        "erro_ia": erro_ia,
        "nao_e_prato": bool(erro_ia and "não reconheceu um prato" in erro_ia),
        "observacao": observacao,
        "margem": calcular_margem(peso_g, resultado["mix"], **margem_args),
    }

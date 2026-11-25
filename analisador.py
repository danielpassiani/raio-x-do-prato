"""Analisador do prato: estima o mix (carne / guarnição / salada / outros) a partir da foto.

Dois modos:
  1. IA de visão (real): se existir a variável de ambiente ANTHROPIC_API_KEY e uma imagem,
     a foto é enviada a um modelo de visão que devolve as proporções em JSON.
  2. Simulado: sem chave (ou se a chamada falhar), gera uma estimativa aleatória e avisa
     que é simulada. Serve para demonstrar o fluxo completo sem custo.
"""
import base64
import json
import os
import random
import re

from custos import CATEGORIAS, calcular_margem, normalizar_mix

MODELO = os.getenv("RAIOX_MODELO", "claude-sonnet-5-5")

PROMPT = (
    "Você analisa fotos de pratos de restaurante por quilo, vistos de cima. "
    "Estime a proporção da ÁREA/VOLUME do prato ocupada por cada categoria: "
    "carne (churrasco, carnes, linguiça), guarnicao (arroz, feijão, massas, farofa, batata), "
    "salada (folhas, legumes, verduras) e outros (frituras, molhos, sobremesa, o que não se encaixa). "
    "As quatro proporções devem somar 1. "
    'Responda APENAS com JSON no formato: {"carne": 0.0, "guarnicao": 0.0, "salada": 0.0, '
    '"outros": 0.0, "observacao": "frase curta"}'
)


def _mix_simulado(seed=None):
    rng = random.Random(seed)
    alfa = [3.5, 3.5, 2.5, 0.5]
    if rng.random() < 0.2:
        alfa = [9.0, 2.0, 1.5, 0.5]
    partes = [rng.gammavariate(a, 1) for a in alfa]
    total = sum(partes)
    return {c: p / total for c, p in zip(CATEGORIAS, partes)}


def _analisar_com_ia(imagem_bytes, media_type):
    import anthropic

    client = anthropic.Anthropic()
    resposta = client.messages.create(
        model=MODELO,
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.b64encode(imagem_bytes).decode(),
                }},
                {"type": "text", "text": PROMPT},
            ],
        }],
    )
    texto = "".join(b.text for b in resposta.content if getattr(b, "type", "") == "text")
    achado = re.search(r"\{.*\}", texto, re.DOTALL)
    if not achado:
        raise ValueError("A IA não devolveu JSON")
    dados = json.loads(achado.group(0))
    mix = normalizar_mix({c: float(dados.get(c, 0)) for c in CATEGORIAS})
    return mix, dados.get("observacao", "")


def analisar_prato(peso_g, imagem_bytes=None, media_type="image/jpeg", seed=None,
                   custo_kg=None, preco_kg=None):
    """Devolve dict com mix, margem, fonte da análise e observação."""
    fonte, observacao = "simulado", "Estimativa simulada (sem chave de API configurada)."
    mix = None

    if imagem_bytes and os.getenv("ANTHROPIC_API_KEY"):
        try:
            mix, observacao = _analisar_com_ia(imagem_bytes, media_type)
            fonte = "ia"
        except Exception as erro:  # qualquer falha cai no modo simulado
            observacao = f"Falha na IA ({type(erro).__name__}); usando estimativa simulada."

    if mix is None:
        mix = _mix_simulado(seed)

    return {
        "mix": mix,
        "fonte": fonte,
        "observacao": observacao,
        "margem": calcular_margem(peso_g, mix, custo_kg=custo_kg, **({"preco_kg": preco_kg} if preco_kg else {})),
    }

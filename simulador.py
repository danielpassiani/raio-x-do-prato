"""Gera um dia de almoço SIMULADO do Bovinu's Grill & Beer (Augusta).

Por que simulado? O restaurante não guarda métricas de mix nem de tempo por estação,
e o vídeo de 1h30 da operação ainda não estava disponível durante o hackathon.
Os parâmetros abaixo seguem o que a diretoria informou:
  - ~600 clientes de segunda a sexta, serviço das 11:30 às 15:30
  - pico entre 12:10 e 13:20
  - fila da churrasqueira chega a ~4 min no pico (meta: 2,5 min)

Quando houver dados reais (câmera na balança + vídeo), basta gerar um CSV com as mesmas
colunas e colocá-lo em data/pratos.csv que o painel passa a usá-lo.
"""
import numpy as np
import pandas as pd

from custos import CATEGORIAS

DURACAO_MIN = 240  # 11:30 -> 15:30


def _intensidade_por_minuto():
    """Peso relativo de chegadas em cada minuto do serviço (pico das 12:10 às 13:20)."""
    m = np.arange(DURACAO_MIN)
    peso = np.full(DURACAO_MIN, 0.3)
    peso[:30] = 0.6                      # 11:30-12:00
    peso[30:40] = 1.2                    # 12:00-12:10
    peso[40:110] = 3.0                   # 12:10-13:20 (pico)
    peso[110:120] = 1.2
    peso[120:] = np.linspace(0.5, 0.15, DURACAO_MIN - 120)  # tarde
    return m, peso


def gerar_dia(n_clientes=600, seed=42):
    rng = np.random.default_rng(seed)
    minutos, peso_chegada = _intensidade_por_minuto()
    prob = peso_chegada / peso_chegada.sum()
    chegada = np.sort(rng.choice(minutos, size=n_clientes, p=prob))
    intensidade = peso_chegada[chegada] / peso_chegada.max()  # 0..1

    peso_g = np.clip(rng.normal(560, 150, n_clientes), 250, 1100)

    # Mix do prato: ~15% dos clientes pegam muita carne
    carnivoro = rng.random(n_clientes) < 0.15
    mix = np.zeros((n_clientes, len(CATEGORIAS)))
    alfa_normal = [3.5, 3.5, 2.5, 0.5]    # carne, guarnição, salada, outros
    alfa_carnivoro = [9.0, 2.0, 1.5, 0.5]
    for i in range(n_clientes):
        mix[i] = rng.dirichlet(alfa_carnivoro if carnivoro[i] else alfa_normal)

    def tempo(media, fator=1.0):
        return rng.gamma(shape=3, scale=(media * fator) / 3)

    t_saladas = tempo(1.0, 1 + 0.3 * intensidade)
    t_quentes = tempo(1.3, 1 + 0.4 * intensidade)
    t_churrasqueira = tempo(1.8 + 2.2 * intensidade)   # gargalo no pico
    t_balanca = tempo(0.6, 1 + 0.5 * intensidade)

    base = pd.Timestamp("2026-11-25 11:30")
    df = pd.DataFrame({
        "hora": [(base + pd.Timedelta(minutes=int(m))).strftime("%H:%M") for m in chegada],
        "hora_cheia": [(base + pd.Timedelta(minutes=int(m))).hour for m in chegada],
        "peso_g": peso_g.round(0),
    })
    for j, c in enumerate(CATEGORIAS):
        df[f"frac_{c}"] = mix[:, j].round(3)
    df["t_saladas"] = t_saladas.round(2)
    df["t_quentes"] = t_quentes.round(2)
    df["t_churrasqueira"] = t_churrasqueira.round(2)
    df["t_balanca"] = t_balanca.round(2)
    df["tempo_total_min"] = (t_saladas + t_quentes + t_churrasqueira + t_balanca).round(2)
    return df


if __name__ == "__main__":
    import os
    os.makedirs("data", exist_ok=True)
    gerar_dia().to_csv("data/pratos_simulados.csv", index=False)
    print("data/pratos_simulados.csv gerado")

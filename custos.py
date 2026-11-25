"""Premissas de custo e cálculo de margem do prato.

Os valores de custo por kg são ESTIMATIVAS ilustrativas, não dados do restaurante.
O preço de R$ 119/kg foi informado pela diretoria do Bovinu's na apresentação.
Para usar números reais, basta editar o dicionário CUSTO_KG (ou usar a barra lateral do painel).
"""

PRECO_KG = 119.0

# Custo estimado do alimento por kg servido, por categoria (R$/kg)
CUSTO_KG = {
    "carne": 58.0,       # churrasco: picanha, costela, linguiça...
    "guarnicao": 11.0,   # arroz, feijão, massas, farofa
    "salada": 14.0,      # saladas e legumes
    "outros": 22.0,      # frituras, molhos, sobremesas
}

CATEGORIAS = list(CUSTO_KG.keys())

# Metas operacionais citadas pela diretoria
META_FILA_CHURRASQUEIRA_MIN = 2.5   # tempo bom de fila na churrasqueira
LIMITE_FILA_CHURRASQUEIRA_MIN = 4.0  # tempo considerado ruim

# Abaixo dessa margem, o prato é marcado como "custo alto"
LIMITE_MARGEM_ALERTA = 0.68


def normalizar_mix(mix):
    """Garante que as proporções somem 1. Se tudo for zero, divide igualmente."""
    total = sum(max(0.0, mix.get(c, 0.0)) for c in CATEGORIAS)
    if total <= 0:
        return {c: 1 / len(CATEGORIAS) for c in CATEGORIAS}
    return {c: max(0.0, mix.get(c, 0.0)) / total for c in CATEGORIAS}


def calcular_margem(peso_g, mix, custo_kg=None, preco_kg=PRECO_KG):
    """Calcula receita, custo e margem de UM prato."""
    custo_kg = custo_kg or CUSTO_KG
    mix = normalizar_mix(mix)
    kg = peso_g / 1000
    receita = kg * preco_kg
    custo = kg * sum(mix[c] * custo_kg[c] for c in CATEGORIAS)
    margem_rs = receita - custo
    return {
        "receita": receita,
        "custo": custo,
        "margem_rs": margem_rs,
        "margem_pct": margem_rs / receita if receita else 0.0,
    }


def aplicar_margem(df, custo_kg=None, preco_kg=PRECO_KG, limite=LIMITE_MARGEM_ALERTA):
    """Versão para tabela inteira (pandas). Espera colunas peso_g e frac_<categoria>."""
    custo_kg = custo_kg or CUSTO_KG
    df = df.copy()
    kg = df["peso_g"] / 1000
    df["receita"] = kg * preco_kg
    custo_por_kg = sum(df[f"frac_{c}"] * custo_kg[c] for c in CATEGORIAS)
    df["custo"] = kg * custo_por_kg
    df["margem_rs"] = df["receita"] - df["custo"]
    df["margem_pct"] = df["margem_rs"] / df["receita"]
    df["custo_alto"] = df["margem_pct"] < limite
    return df

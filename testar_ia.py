"""Testa a IA de visão com a sua chave e, opcionalmente, reanalisa a galeria inteira.

Uso (PowerShell, dentro da pasta do projeto):
    $env:GEMINI_API_KEY="sua-chave"
    python testar_ia.py              -> analisa 1 foto e mostra o resultado
    python testar_ia.py --galeria    -> reanalisa as 9 fotos e atualiza data/analises_fotos.json

Se a variável não estiver definida, o script pede a chave (ela não é salva em lugar nenhum).
"""
import getpass
import json
import os
import sys
import time

from analisador import ErroIA, analisar_com_gemini

ARQUIVO = "data/analises_fotos.json"


def obter_chave():
    chave = os.getenv("GEMINI_API_KEY", "").strip()
    if not chave:
        chave = getpass.getpass("Cole a chave da API do Gemini (não aparece na tela) e aperte Enter: ").strip()
    if not chave:
        sys.exit("Nenhuma chave informada.")
    return chave


def mostrar(nome, resultado, modelo):
    mix = resultado["mix"]
    print(f"\n{nome}  (modelo: {modelo})")
    for categoria, valor in mix.items():
        print(f"  {categoria:10s} {valor * 100:5.1f}%  " + "#" * int(valor * 40))
    if resultado["itens"]:
        print("  itens:", ", ".join(resultado["itens"]))
    print("  obs:", resultado["observacao"])


def main():
    chave = obter_chave()
    with open(ARQUIVO, encoding="utf-8") as f:
        pratos = json.load(f)

    if "--galeria" not in sys.argv:
        prato = pratos[0]
        try:
            resultado, modelo = analisar_com_gemini(open(os.path.join("data", prato["arquivo"]), "rb").read(), "image/jpeg", chave)
        except ErroIA as erro:
            sys.exit(f"\nFALHOU: {erro}")
        mostrar(prato["titulo"], resultado, modelo)
        print("\nOK! A IA está funcionando. Rode 'python testar_ia.py --galeria' para reanalisar todas as fotos.")
        return

    atualizados = 0
    for prato in pratos:
        try:
            resultado, modelo = analisar_com_gemini(open(os.path.join("data", prato["arquivo"]), "rb").read(), "image/jpeg", chave)
        except ErroIA as erro:
            print(f"\n{prato['titulo']}: falhou ({erro}). Mantendo a análise anterior.")
            continue
        mostrar(prato["titulo"], resultado, modelo)
        prato["mix"] = {c: round(v, 3) for c, v in resultado["mix"].items()}
        prato["itens"] = resultado["itens"]
        prato["observacao"] = resultado["observacao"] or prato["observacao"]
        prato["modelo"] = modelo
        atualizados += 1
        time.sleep(2)  # respeita o limite do plano gratuito

    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(pratos, f, ensure_ascii=False, indent=2)
    print(f"\n{atualizados} de {len(pratos)} pratos atualizados em {ARQUIVO}.")
    if atualizados:
        print("Suba o arquivo data/analises_fotos.json atualizado para o GitHub.")


if __name__ == "__main__":
    main()

# Raio-X do Prato

Protótipo desenvolvido no Hackathon FMU para o **Bovinu's Grill & Beer (Rua Augusta)**, almoço por quilo.

**Equipe:** Daniel Passiani, Pedro Torres e Kauan Lucindo | **Curso:** Análise e Desenvolvimento de Sistemas, FMU

## 1. O problema

A diretoria do Grupo Bovinu's apresentou o desafio: a casa atende cerca de 600 clientes por dia no almoço, mas hoje só mede **ticket médio e peso médio**. O restante é "olhômetro". Duas perguntas ficam sem resposta:

1. **O que o cliente pegou?** O peso do prato é conhecido, mas não se é 600 g de arroz ou de picanha. Isso afeta diretamente o lucro (foi apontada como a dor mais crítica).
2. **Onde o cliente demora?** A fila da churrasqueira já chegou a 4 min (a meta é 2,5 min), e o público executivo tem 30 a 40 min para almoçar.

Frase-guia do desafio: *"que dados o cliente demonstra, mas não conta?"*

## 2. A solução

Uma **câmera apontada para a balança** (os donos já indicaram que seria um investimento plausível) e um painel que transforma a imagem em decisões:

| Etapa | O que acontece |
|---|---|
| 1. Foto do prato | A câmera registra o prato no momento da pesagem |
| 2. IA de visão | Estima a proporção de carne, guarnição, salada e outros |
| 3. Margem do prato | Cruza o mix com o peso e com o custo por categoria |
| 4. Tempo por estação | Mostra quanto tempo o cliente leva em saladas, quentes, churrasqueira e balança |
| 5. Painel do gerente | Margem por hora, gargalos e alertas |

**Respeita as restrições da diretoria:** não toca cozinha, compras, estoque nem pagamento; mantém o modelo por quilo; não adiciona catraca nem nada que afaste o contato humano com o cliente.

## 3. Como executar

```bash
pip install -r requirements.txt
python simulador.py        # opcional: regera data/pratos_simulados.csv
streamlit run app.py
```

**Galeria de pratos analisados:** a aba "Galeria de pratos analisados" mostra 9 fotos de exemplo cujo mix (carne, guarnição, salada, outros) foi estimado por um modelo de visão de IA durante o desenvolvimento. Os resultados estão em `data/analises_fotos.json` e as fotos em `data/fotos/` (fontes em `data/fontes_imagens.md`). Os pesos dos pratos são estimativas visuais. Em produção, essa análise seria feita automaticamente, a cada prato, pela câmera da balança.

**Ligar a IA de visão ao vivo (opcional):** defina a variável de ambiente `ANTHROPIC_API_KEY` antes de rodar. Sem ela, a aba "Analisar um prato" funciona em **modo simulado** e avisa isso na tela. O modelo pode ser trocado com `RAIOX_MODELO`.

```bash
# Linux/Mac
export ANTHROPIC_API_KEY="sua-chave"
# Windows (PowerShell)
$env:ANTHROPIC_API_KEY="sua-chave"
```

## 4. Estrutura

```
app.py          painel Streamlit (visão do gerente + análise de prato)
analisador.py   estima o mix do prato (IA de visão ou modo simulado)
custos.py       premissas de preço/custo e cálculo de margem
simulador.py    gera um dia de almoço simulado
data/           pratos_simulados.csv, analises_fotos.json, fotos/ e fontes_imagens.md
```

Para usar dados reais, salve um CSV com as mesmas colunas em `data/pratos.csv`. O painel passa a usá-lo automaticamente.

## 5. Premissas e limitações (importante)

- **Os dados do painel são simulados.** Foram gerados com os números que a diretoria informou: ~600 clientes por dia, serviço das 11:30 às 15:30, pico das 12:10 às 13:20, fila da churrasqueira chegando a ~4 min no pico.
- **Os custos por kg são estimativas nossas**, não dados do restaurante (carne R$ 58, guarnição R$ 11, salada R$ 14, outros R$ 22). Podem ser editados na barra lateral. O preço de R$ 119/kg foi informado pela diretoria.
- **As fotos da galeria são de exemplo**, tiradas da internet, e os pesos são estimados. A análise delas é real, mas não foi feita ao vivo e não foi validada contra a pesagem de pratos de verdade.
- **A estimativa visual do mix é aproximada.** Ela mede proporção na imagem, não gramas exatas. Deve ser usada para tendências (margem por hora, por dia), não para auditar um prato individual.
- **A estimativa de ganho** exibida no painel é ilustrativa e depende das premissas de custo acima.
- O vídeo de 1h30 da operação prometido pela organização não estava disponível durante o desenvolvimento. Os tempos por estação são, por isso, simulados.

## 6. Roadmap

1. **Câmera real na balança** e leitura automática do peso, ligada ao número da comanda (código de barras) já usado no sistema.
2. **Tempo por estação com dados reais**, a partir do vídeo da operação e das câmeras já instaladas (contagem de pessoas na fila da churrasqueira e na entrada).
3. **Câmera na devolução dos pratos** para estimar o que sobra (qualidade da comida).
4. **Medir desistência na entrada**: contar quem olha a fila na escada e vai embora.
5. **Previsão de movimento** cruzando chuva, feriado e dia da semana com o cardápio.
6. **Sensores/leitor de comanda** no início do buffet para medir o tempo total do cliente, a ser avaliado para não criar fila na entrada.

## 7. Impacto esperado

- A diretoria passa a ter, pela primeira vez, **uma métrica de mix e de margem por prato**.
- O gerente enxerga **onde está o gargalo** e em que horário (ex.: reforço na churrasqueira no pico).
- Custo baixo: aproveita câmeras já instaladas e exige no máximo uma câmera nova na balança.

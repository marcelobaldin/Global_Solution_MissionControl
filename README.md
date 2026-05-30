# MissionControl - Sistema Inteligente de Monitoramento de Missao Espacial

**Global Solution 2026 - FIAP - Ciencias da Computacao**

## Equipe - Grupo 28

| Nome | RM | Email |
|------|-----|-------|
| Marcelo Bastianello Baldin | 568746 | marcelobbaldin@gmail.com |

---

## 1. Resumo do Problema

O sistema simula o monitoramento operacional de uma base espacial em Marte (Sol 147), capaz de interpretar dados de telemetria, identificar situacoes criticas, gerar alertas automaticos e fornecer previsoes e recomendacoes para manter a seguranca da tripulacao.

**Cenario:** Uma base marciana com 6 modulos criticos (Suporte a Vida, Energia, Comunicacao, Habitat, Laboratorio e Armazenamento) enfrenta uma degradacao progressiva ao longo de 24 horas: perda de comunicacao, falha energetica, radiacao elevada e queda na reserva de bateria de 82% para 28%.

**Dados simulados:** 8 leituras de telemetria (a cada 3 horas), 12 eventos registrados e 1 inconsistencia proposital (geracao solar reportada durante periodo noturno) para testar a capacidade de diagnostico.

---

## 2. Estruturas de Dados

| Estrutura | Implementacao Python | Justificativa |
|-----------|---------------------|---------------|
| **Lista** | `list` | Series temporais de geracao, consumo e temperatura — acesso sequencial e calculo de tendencias |
| **Fila** | `collections.deque` | Alertas pendentes por ordem de chegada (FIFO) — garante processamento na ordem correta |
| **Pilha** | `list` (append/pop) | Ultimos eventos criticos (LIFO) — acesso rapido ao evento mais recente |
| **Dicionario** | `dict` | Acesso O(1) a modulos pelo nome — consulta rapida durante diagnostico |
| **Hierarquia** | `dict` aninhado | Arvore: energia (solar/eolica/baterias) e habitat (oxigenio/temperatura/comunicacao) |
| **Matriz** | `list[list]` | Leituras 8x10: cada linha = horario, cada coluna = variavel |

---

## 3. Regras Logicas

### Expressao Booleana Principal

```
CRITICO = (reserva < 25 AND consumo > geracao_total)
       OR (NOT comunicacao AND radiacao > 1.0)
       OR (NOT suporte_vida)
```

### Regras Implementadas

| Regra | Expressao | Acao |
|-------|-----------|------|
| **R1** | `reserva < 25% AND consumo > geracao` | Energia critica: desligar sistemas nao essenciais |
| **R2** | `NOT comunicacao OR (radiacao > 1.0 AND NOT suporte_vida)` | Isolamento/exposicao: ativar comunicacao de emergencia |
| **R3** | `(temp < 15 OR temp > 30) AND NOT habitat` | Temperatura critica: restaurar habitat imediatamente |
| **R4** | `radiacao > 0.8 AND NOT (habitat AND suporte_vida)` | Radiacao elevada: recolher tripulacao |
| **R5** | `NOT suporte_vida` | Prioridade absoluta: restaurar suporte a vida |

Cada regra usa **IF/ELIF/ELSE** para classificar em NORMAL, ALERTA ou CRITICO, com operadores **AND**, **OR** e **NOT**.

---

## 4. Tecnica de Previsao

**Regressao linear por minimos quadrados** aplicada a serie temporal da reserva de bateria.

- **Dados:** 8 leituras de reserva ao longo de 24h
- **Metodologia:** Calculo de y = ax + b sem bibliotecas externas, usando apenas operacoes aritmeticas
- **Resultado:** Tendencia declinante com coeficiente angular negativo, prevendo nivel critico (25%) em poucas horas
- **Influencia:** A previsao determina a urgencia das recomendacoes — se o nivel critico sera atingido em menos de 6h, o sistema recomenda desligamento imediato de modulos nao essenciais

**Media movel** (janela 3) aplicada a temperatura interna e consumo energetico para suavizar flutuacoes.

---

## 5. Como Executar

### Automatico (recomendado)
```bash
python instalar_missioncontrol.py
```

### Manual
```bash
python -m venv venv_missioncontrol
source venv_missioncontrol/bin/activate    # Linux/Mac
pip install flask fpdf2
python src/sistema.py
```

Acesse: **http://localhost:5050** | Usuario: `usuario` | Senha: `senha`

---

## 6. Exemplo de Entrada e Saida

### Entrada (dados.csv - ultimo registro)

```
hora=21:00, suporte_vida=1, energia=1, comunicacao=1, habitat=1,
laboratorio=1, armazenamento=1, geracao_solar=0, geracao_eolica=15,
consumo=48, reserva_bateria=28, temp_interna=21.5, temp_externa=-65.8,
radiacao=0.22, qualidade_comm=85, velocidade_vento=25
```

### Saida do Sistema

```
Status da missao: ALERTA
Modulos online: 6/6
Reserva de bateria: 28%

Diagnostico:
  R1 - ALERTA: reserva < 40% AND consumo > geracao_total
       Reserva em 28% com consumo superior a geracao (15.0 kWh)
       Acao: Reduzir consumo nao essencial. Monitorar tendencia.

Previsao (regressao linear):
  Tendencia: declinante
  R²: 0.9753
  Nivel critico em: ~5.2h
  Recomendacao: ATENCAO - reserva pode atingir 25% em ~5h.
                Ativar economia e priorizar recarga.
```

---

## 7. Recomendacoes Geradas

O sistema gera recomendacoes automaticas priorizadas:

1. **CRITICO** - Desligar laboratorio e armazenamento, manter suporte a vida e habitat
2. **CRITICO** - Ativar comunicacao de emergencia ao perder contato
3. **CRITICO** - Recolher tripulacao ao habitat em caso de radiacao perigosa
4. **ALERTA** - Ativar modo de economia quando reserva < 40%
5. **ALERTA** - Verificar sensor solar (anomalia: geracao noturna reportada)

---

## 8. Link do Video

[Video de apresentacao no YouTube](docs/link_video.txt)

---

## 9. Conclusoes e Aprendizados

- **Estruturas de dados:** Cada estrutura foi escolhida por adequacao ao problema — listas para dados sequenciais, fila para alertas ordenados, pilha para historico recente, dicionario para busca rapida
- **Regras logicas:** A combinacao de IF/ELIF/ELSE com AND/OR/NOT permite diagnosticos precisos que consideram multiplas variaveis simultaneamente
- **Previsao:** A regressao linear, mesmo simples, fornece informacoes valiosas para antecipar crises e tomar decisoes preventivas
- **Integracao:** O maior aprendizado foi integrar leitura de dados, diagnostico, alertas e previsao em um sistema coeso que transforma dados brutos em recomendacoes uteis

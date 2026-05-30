# MissionControl - Guia de Instalacao

**Global Solution 2026 - FIAP**
**Aluno:** Marcelo Bastianello Baldin | RM568746 | Grupo 28

---

## Requisitos

- Python 3.9 ou superior
- Conexao com internet (apenas na primeira execucao, para instalar o Flask)

---

## Instalacao Automatica (Recomendado)

```bash
python instalar_missioncontrol.py
```

O instalador cria automaticamente o ambiente virtual, instala as dependencias e inicia o sistema.

---

## Instalacao Manual

### 1. Criar ambiente virtual

```bash
python -m venv venv_missioncontrol
```

### 2. Ativar o ambiente

**Windows:**
```bash
venv_missioncontrol\Scripts\activate
```

**Mac / Linux:**
```bash
source venv_missioncontrol/bin/activate
```

### 3. Instalar dependencias

```bash
pip install flask fpdf2
```

### 4. Executar o sistema

```bash
python src/sistema.py
```

---

## Acesso

**URL:** http://localhost:5050

## Credenciais

| Perfil   | Usuario   | Senha  |
|----------|-----------|--------|
| Operador | `usuario` | `senha`|

---

## Funcionalidades

### Visao Geral
- Status de todos os 6 modulos criticos (online/offline)
- Diagnostico geral da missao (Normal / Alerta / Critico)
- Deteccao automatica de anomalias nos dados

### Energia
- Graficos de geracao solar e eolica vs consumo
- Reserva de bateria com tendencia
- Distribuicao solar vs eolica (pie chart)
- Consumo com media movel

### Ambiente
- Temperatura interna e externa com media movel
- Nivel de radiacao com indicadores de risco
- Qualidade de comunicacao
- Velocidade do vento

### Alertas Automaticos
- Fila de alertas ordenada por severidade (CRITICO > ALERTA)
- Recomendacoes de acao para cada alerta
- 3 niveis: Normal, Alerta, Critico

### Log de Eventos (Pilha)
- Eventos mais recentes primeiro (LIFO)
- 12 registros incluindo alertas, falhas e reinicializacoes

### Matriz de Dados
- Tabela completa de leituras por horario e variavel
- Destaque visual para valores fora das faixas de seguranca

### Hierarquia da Missao
- Arvore: Energia (solar, eolica, baterias)
- Arvore: Habitat (oxigenio, temperatura, comunicacao)

### Previsao
- Regressao linear na reserva de bateria
- Media movel na temperatura e consumo
- Previsao influencia recomendacoes do sistema

### Regras Logicas
- 5 regras com IF/ELIF/ELSE e operadores AND, OR, NOT
- Expressao booleana principal do diagnostico
- Timeline de status por horario

---

## Estruturas de Dados Utilizadas

| Estrutura | Implementacao | Uso |
|-----------|---------------|-----|
| Lista | `list` | Series temporais (geracao, consumo, temperatura) |
| Fila | `collections.deque` | Alertas pendentes por ordem de chegada |
| Pilha | `list` (append/pop) | Ultimos eventos criticos (LIFO) |
| Dicionario | `dict` | Acesso rapido a modulos por nome |
| Hierarquia | `dict` aninhado | Arvore energia/habitat da missao |
| Matriz | `list[list]` | Leituras [horario][variavel] |

---

## Estrutura de Arquivos

```
GLOBAL_SOLUTION_SEMESTRE/
  README.md                       # Documentacao do projeto
  instalar_missioncontrol.py      # Instalador automatico
  instalacao_missioncontrol.md    # Este guia
  src/
    sistema.py                    # Sistema completo (engine + web)
    templates/
      login.html                  # Pagina de login
      dashboard.html              # Dashboard principal (SPA)
  data/
    dados.csv                     # Telemetria simulada (8 leituras)
    eventos.csv                   # Log de eventos (12 registros)
  docs/
    relatorio.pdf                 # Relatorio tecnico (gerado)
    link_video.txt                # Link do video no YouTube
    uso_ia.md                     # Documentacao de uso de IA
```

---

## Geracao do Relatorio PDF

O sistema pode gerar o relatorio tecnico automaticamente:

1. Acesse o dashboard (http://localhost:5050)
2. O relatorio tambem pode ser gerado via API: `GET /api/gerar-relatorio`
3. O PDF sera salvo em `docs/relatorio.pdf`

Prerequisito: `pip install fpdf2` (ja incluido no instalador)

---

## Notas Tecnicas

- Todos os dados sao carregados dos arquivos CSV em `data/`
- Nao requer banco de dados
- Regressao linear implementada sem bibliotecas externas (minimos quadrados)
- Media movel com janela de 3 pontos
- 5 regras logicas com AND, OR e NOT
- Dados incluem 1 inconsistencia proposital (geracao solar a meia-noite)
- Porta padrao: 5050
- Para encerrar: Ctrl+C no terminal

---

## Solucao de Problemas

| Problema | Solucao |
|----------|---------|
| Porta 5050 ocupada | Altere a porta no final de `src/sistema.py` |
| ModuleNotFoundError: flask | Execute `pip install flask` no ambiente virtual |
| Arquivo dados.csv nao encontrado | Execute a partir da raiz do projeto |
| Pagina em branco | Limpe o cache do navegador (Ctrl+Shift+R) |

---

**Contato:** marcelobbaldin@gmail.com

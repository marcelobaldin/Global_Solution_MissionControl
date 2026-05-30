#!/usr/bin/env python3
"""
MissionControl - Sistema Inteligente de Monitoramento de Missao Espacial
Global Solution 2026 - FIAP - Ciencias da Computacao
Marcelo Bastianello Baldin - RM568746 - Grupo 28

Execucao: python src/sistema.py
Acesso: http://localhost:5050 (usuario: usuario / senha: senha)
"""

import csv
import os
import json
import math
from collections import deque
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, session, jsonify)

# ============================================================
# CONFIGURACOES
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, 'data')

USUARIOS = {
    'usuario': {'senha': 'senha', 'nome': 'Operador de Missao'}
}

# Faixas de seguranca para classificacao
FAIXAS = {
    'reserva_bateria': {'critico': 25, 'alerta': 40},
    'temp_interna': {'min_critico': 10, 'min_alerta': 18,
                     'max_alerta': 28, 'max_critico': 35},
    'radiacao': {'alerta': 0.8, 'critico': 1.0},
    'qualidade_comm': {'critico': 30, 'alerta': 60},
    'velocidade_vento': {'min_operacional': 8},
}


# ============================================================
# 1. ESTRUTURAS DE DADOS
# ============================================================

class EstruturaDados:
    """Gerencia as 6 estruturas de dados obrigatorias da missao.

    1. Listas   - series temporais de geracao, consumo, temperatura
    2. Fila     - alertas pendentes ordenados por chegada (FIFO)
    3. Pilha    - ultimos eventos criticos analisados (LIFO)
    4. Dicionario - acesso rapido a modulos pelo nome
    5. Hierarquia - arvore energia (solar/eolica/baterias) e
                    habitat (oxigenio/temperatura/comunicacao)
    6. Matriz   - leituras por horario e variavel
    """

    def __init__(self):
        # 1. LISTAS - series temporais
        self.serie_geracao_solar: list[float] = []
        self.serie_geracao_eolica: list[float] = []
        self.serie_consumo: list[float] = []
        self.serie_reserva: list[float] = []
        self.serie_temp_interna: list[float] = []
        self.serie_temp_externa: list[float] = []
        self.serie_radiacao: list[float] = []
        self.serie_comm: list[float] = []
        self.serie_vento: list[float] = []
        self.horarios: list[str] = []

        # 2. FILA - alertas pendentes (collections.deque, FIFO)
        self.fila_alertas: deque = deque()

        # 3. PILHA - eventos criticos (lista Python, LIFO)
        self.pilha_eventos: list[dict] = []

        # 4. DICIONARIO - modulos acessiveis por nome
        self.modulos: dict[str, dict] = {}

        # 5. HIERARQUIA - arvore da missao
        self.hierarquia: dict = {
            'missao_espacial': {
                'energia': {
                    'solar':    {'status': 1, 'geracao_kwh': 0, 'tipo': 'renovavel'},
                    'eolica':   {'status': 1, 'geracao_kwh': 0, 'tipo': 'renovavel'},
                    'baterias': {'capacidade_pct': 100, 'reserva_pct': 0, 'tipo': 'armazenamento'}
                },
                'habitat': {
                    'oxigenio':     {'nivel_pct': 98, 'producao': 'nominal', 'reserva_h': 72},
                    'temperatura':  {'interna_c': 22.0, 'externa_c': -60.0, 'regulacao': 'ativa'},
                    'comunicacao':  {'status': 1, 'latencia_min': 14.4, 'banda': 'normal'}
                }
            }
        }

        # 6. MATRIZ - leituras[horario][variavel]
        self.matriz_leituras: list[list] = []
        self.colunas_matriz = [
            'Hora', 'Solar(kWh)', 'Eolica(kWh)', 'Consumo(kWh)',
            'Reserva(%)', 'T.Int(C)', 'T.Ext(C)', 'Rad(mSv/h)',
            'Comm(%)', 'Vento(km/h)'
        ]

    # -- operacoes de pilha (LIFO) --
    def empilhar_evento(self, evento: dict):
        self.pilha_eventos.append(evento)

    def desempilhar_evento(self) -> dict | None:
        return self.pilha_eventos.pop() if self.pilha_eventos else None

    def topo_pilha(self) -> dict | None:
        return self.pilha_eventos[-1] if self.pilha_eventos else None

    # -- operacoes de fila (FIFO) --
    def enfileirar_alerta(self, alerta: dict):
        self.fila_alertas.append(alerta)

    def desenfileirar_alerta(self) -> dict | None:
        return self.fila_alertas.popleft() if self.fila_alertas else None


# ============================================================
# 2. LEITURA E INTERPRETACAO DE DADOS
# ============================================================

class LeitorDados:
    """Le dados de telemetria (CSV) e eventos (CSV)."""

    @staticmethod
    def carregar_telemetria(caminho: str) -> list[dict]:
        """Le o arquivo de telemetria e converte tipos."""
        dados = []
        with open(caminho, 'r', encoding='utf-8') as f:
            for linha in csv.DictReader(f):
                dados.append({
                    'hora':             linha['hora'],
                    'suporte_vida':     int(linha['suporte_vida']),
                    'energia':          int(linha['energia']),
                    'comunicacao':      int(linha['comunicacao']),
                    'habitat':          int(linha['habitat']),
                    'laboratorio':      int(linha['laboratorio']),
                    'armazenamento':    int(linha['armazenamento']),
                    'geracao_solar':    float(linha['geracao_solar']),
                    'geracao_eolica':   float(linha['geracao_eolica']),
                    'consumo':          float(linha['consumo']),
                    'reserva_bateria':  float(linha['reserva_bateria']),
                    'temp_interna':     float(linha['temp_interna']),
                    'temp_externa':     float(linha['temp_externa']),
                    'radiacao':         float(linha['radiacao']),
                    'qualidade_comm':   float(linha['qualidade_comm']),
                    'velocidade_vento': float(linha['velocidade_vento']),
                })
        return dados

    @staticmethod
    def carregar_eventos(caminho: str) -> list[dict]:
        """Le o log de eventos."""
        eventos = []
        with open(caminho, 'r', encoding='utf-8') as f:
            for linha in csv.DictReader(f):
                eventos.append({
                    'timestamp': linha['timestamp'],
                    'tipo':      linha['tipo'],
                    'modulo':    linha['modulo'],
                    'descricao': linha['descricao'],
                })
        return eventos

    @staticmethod
    def detectar_anomalias(dados: list[dict]) -> list[dict]:
        """Identifica inconsistencias propositais nos dados."""
        anomalias = []
        for d in dados:
            hora_int = int(d['hora'].split(':')[0])

            # Anomalia 1: geracao solar durante a noite
            if (hora_int < 5 or hora_int >= 20) and d['geracao_solar'] > 0:
                anomalias.append({
                    'hora': d['hora'],
                    'tipo': 'INCONSISTENCIA',
                    'variavel': 'geracao_solar',
                    'valor': d['geracao_solar'],
                    'descricao': (
                        f"Sensor solar reportou {d['geracao_solar']} kWh as {d['hora']} "
                        f"(periodo noturno). Possivel defeito no sensor ou "
                        f"dado corrompido na transmissao."
                    ),
                })

            # Anomalia 2: comunicacao offline mas qualidade alta
            if d['comunicacao'] == 0 and d['qualidade_comm'] > 50:
                anomalias.append({
                    'hora': d['hora'],
                    'tipo': 'INCONSISTENCIA',
                    'variavel': 'qualidade_comm',
                    'valor': d['qualidade_comm'],
                    'descricao': (
                        f"Modulo de comunicacao offline mas qualidade reportada "
                        f"em {d['qualidade_comm']}%. Dado inconsistente — "
                        f"verificar calibracao do sensor de sinal."
                    ),
                })
        return anomalias


# ============================================================
# 3. REGRAS LOGICAS (IF / ELIF / ELSE  +  AND / OR / NOT)
# ============================================================
#
# Expressao booleana principal do diagnostico:
#
#   CRITICO = (reserva < 25 AND consumo > geracao_total)
#          OR (NOT comunicacao AND radiacao > 1.0)
#          OR (NOT suporte_vida)
#
# Em Python:
#   critico = (reserva < 25 and consumo > geracao) \
#          or (not comunicacao and radiacao > 1.0) \
#          or (not suporte_vida)
#

class MotorLogica:
    """Aplica regras logicas para diagnostico da missao.

    Cada regra usa IF/ELIF/ELSE e operadores AND, OR, NOT.
    As 5 regras cobrem: energia, comunicacao+radiacao, temperatura,
    radiacao isolada e suporte a vida.
    """

    @staticmethod
    def diagnosticar(dados: dict) -> dict:
        """Retorna diagnostico completo para um instante da missao."""
        geracao_total = dados['geracao_solar'] + dados['geracao_eolica']
        nivel = 0   # 0=normal, 1=alerta, 2=critico
        regras = []

        # --- REGRA 1: Energia critica ---
        # IF reserva < 25 AND consumo > geracao_total THEN CRITICO
        # ELIF reserva < 40 AND consumo > geracao_total THEN ALERTA
        # ELSE energia OK
        if dados['reserva_bateria'] < FAIXAS['reserva_bateria']['critico'] \
                and dados['consumo'] > geracao_total:
            regras.append({
                'id': 'R1', 'resultado': 'CRITICO',
                'expressao': 'reserva < 25% AND consumo > geracao_total',
                'motivo': (
                    f"Reserva em {dados['reserva_bateria']}% com deficit "
                    f"energetico (consumo {dados['consumo']} kWh > "
                    f"geracao {geracao_total:.1f} kWh). Risco de colapso."
                ),
                'acao': ('Ativar protocolo de emergencia. Desligar '
                         'laboratorio e sistemas nao essenciais.'),
            })
            nivel = max(nivel, 2)
        elif dados['reserva_bateria'] < FAIXAS['reserva_bateria']['alerta'] \
                and dados['consumo'] > geracao_total:
            regras.append({
                'id': 'R1', 'resultado': 'ALERTA',
                'expressao': 'reserva < 40% AND consumo > geracao_total',
                'motivo': (
                    f"Reserva em {dados['reserva_bateria']}% com consumo "
                    f"superior a geracao ({geracao_total:.1f} kWh)."
                ),
                'acao': 'Reduzir consumo nao essencial. Monitorar tendencia.',
            })
            nivel = max(nivel, 1)
        else:
            regras.append({
                'id': 'R1', 'resultado': 'NORMAL',
                'expressao': 'reserva >= 40% OR consumo <= geracao_total',
                'motivo': 'Balanco energetico dentro dos limites aceitaveis.',
                'acao': 'Manter operacoes normais.',
            })

        # --- REGRA 2: Comunicacao + Radiacao ---
        # IF (NOT comunicacao) OR (radiacao > 1.0 AND NOT suporte_vida) THEN CRITICO
        # ELIF NOT comunicacao AND qualidade_comm < 50 THEN ALERTA
        if (not dados['comunicacao']) \
                or (dados['radiacao'] > FAIXAS['radiacao']['critico']
                    and not dados['suporte_vida']):
            partes = []
            if not dados['comunicacao']:
                partes.append('comunicacao offline')
            if dados['radiacao'] > FAIXAS['radiacao']['critico'] \
                    and not dados['suporte_vida']:
                partes.append(f"radiacao {dados['radiacao']} mSv/h sem suporte a vida")
            regras.append({
                'id': 'R2', 'resultado': 'CRITICO',
                'expressao': 'NOT comunicacao OR (radiacao > 1.0 AND NOT suporte_vida)',
                'motivo': f"Condicao critica: {' e '.join(partes)}.",
                'acao': ('Ativar comunicacao de emergencia. '
                         'Recolher tripulacao ao habitat.'),
            })
            nivel = max(nivel, 2)
        elif not dados['comunicacao'] \
                and dados['qualidade_comm'] < FAIXAS['qualidade_comm']['alerta']:
            regras.append({
                'id': 'R2', 'resultado': 'ALERTA',
                'expressao': 'NOT comunicacao AND qualidade_comm < 60%',
                'motivo': f"Comunicacao degradada ({dados['qualidade_comm']}%).",
                'acao': 'Reinicializar antena. Usar canal secundario.',
            })
            nivel = max(nivel, 1)
        else:
            regras.append({
                'id': 'R2', 'resultado': 'NORMAL',
                'expressao': 'comunicacao AND (radiacao <= 1.0 OR suporte_vida)',
                'motivo': 'Comunicacao e protecao contra radiacao operacionais.',
                'acao': 'Manter operacoes normais.',
            })

        # --- REGRA 3: Temperatura do habitat ---
        # IF (temp < 15 OR temp > 30) AND NOT habitat THEN CRITICO
        # ELIF temp < 18 OR temp > 28 THEN ALERTA
        if (dados['temp_interna'] < 15 or dados['temp_interna'] > 30) \
                and not dados['habitat']:
            regras.append({
                'id': 'R3', 'resultado': 'CRITICO',
                'expressao': '(temp_interna < 15 OR temp_interna > 30) AND NOT habitat',
                'motivo': (
                    f"Temperatura em {dados['temp_interna']}C com habitat "
                    f"offline. Risco para a tripulacao."
                ),
                'acao': 'Restaurar habitat. Ativar aquecimento/resfriamento de emergencia.',
            })
            nivel = max(nivel, 2)
        elif dados['temp_interna'] < FAIXAS['temp_interna']['min_alerta'] \
                or dados['temp_interna'] > FAIXAS['temp_interna']['max_alerta']:
            regras.append({
                'id': 'R3', 'resultado': 'ALERTA',
                'expressao': 'temp_interna < 18 OR temp_interna > 28',
                'motivo': (
                    f"Temperatura em {dados['temp_interna']}C "
                    f"(faixa ideal: 18-28C)."
                ),
                'acao': 'Ajustar regulacao termica. Verificar isolamento.',
            })
            nivel = max(nivel, 1)
        else:
            regras.append({
                'id': 'R3', 'resultado': 'NORMAL',
                'expressao': '18 <= temp_interna <= 28',
                'motivo': 'Temperatura interna dentro da faixa ideal.',
                'acao': 'Manter regulacao termica atual.',
            })

        # --- REGRA 4: Radiacao elevada ---
        # IF radiacao > 0.8 AND NOT (habitat AND suporte_vida) THEN ALERTA
        if dados['radiacao'] > FAIXAS['radiacao']['alerta'] \
                and not (dados['habitat'] and dados['suporte_vida']):
            regras.append({
                'id': 'R4', 'resultado': 'ALERTA',
                'expressao': 'radiacao > 0.8 AND NOT (habitat AND suporte_vida)',
                'motivo': (
                    f"Radiacao em {dados['radiacao']} mSv/h com "
                    f"protecao comprometida."
                ),
                'acao': 'Recolher tripulacao. Verificar blindagem.',
            })
            nivel = max(nivel, 1)
        elif dados['radiacao'] > FAIXAS['radiacao']['critico']:
            regras.append({
                'id': 'R4', 'resultado': 'ALERTA',
                'expressao': 'radiacao > 1.0',
                'motivo': f"Radiacao elevada em {dados['radiacao']} mSv/h.",
                'acao': 'Limitar atividades externas. Monitorar exposicao.',
            })
            nivel = max(nivel, 1)
        else:
            regras.append({
                'id': 'R4', 'resultado': 'NORMAL',
                'expressao': 'radiacao <= 0.8',
                'motivo': 'Niveis de radiacao dentro do aceitavel.',
                'acao': 'Manter monitoramento padrao.',
            })

        # --- REGRA 5: Suporte a vida ---
        # IF NOT suporte_vida THEN CRITICO (prioridade absoluta)
        if not dados['suporte_vida']:
            regras.append({
                'id': 'R5', 'resultado': 'CRITICO',
                'expressao': 'NOT suporte_vida',
                'motivo': 'Suporte a vida offline. Emergencia maxima.',
                'acao': ('PRIORIDADE ABSOLUTA: restaurar suporte a vida. '
                         'Acionar reserva de oxigenio.'),
            })
            nivel = max(nivel, 2)
        else:
            regras.append({
                'id': 'R5', 'resultado': 'NORMAL',
                'expressao': 'suporte_vida == True',
                'motivo': 'Suporte a vida operacional.',
                'acao': 'Manter monitoramento continuo.',
            })

        if nivel == 2:
            status = 'CRITICO'
        elif nivel == 1:
            status = 'ALERTA'
        else:
            status = 'NORMAL'

        return {
            'status_geral': status,
            'nivel': nivel,
            'regras_ativadas': regras,
        }


# ============================================================
# 4. ALERTAS AUTOMATICOS
# ============================================================

class GeradorAlertas:
    """Gera alertas automaticos com severidade e recomendacoes."""

    ORDEM_SEVERIDADE = {'CRITICO': 0, 'ALERTA': 1, 'NORMAL': 2}

    @staticmethod
    def gerar_alertas(dados: dict) -> list[dict]:
        """Gera lista de alertas para um instante, ordenados por severidade."""
        alertas = []

        # -- Energia --
        if dados['reserva_bateria'] < FAIXAS['reserva_bateria']['critico']:
            alertas.append({
                'severidade': 'CRITICO', 'modulo': 'energia',
                'titulo': 'Reserva de bateria critica',
                'descricao': f"Reserva em {dados['reserva_bateria']}%",
                'recomendacao': ('Desligar laboratorio e sistemas nao essenciais. '
                                 'Redirecionar energia para suporte a vida e habitat.'),
            })
        elif dados['reserva_bateria'] < FAIXAS['reserva_bateria']['alerta']:
            alertas.append({
                'severidade': 'ALERTA', 'modulo': 'energia',
                'titulo': 'Reserva de bateria baixa',
                'descricao': f"Reserva em {dados['reserva_bateria']}%",
                'recomendacao': 'Ativar modo de economia. Adiar atividades nao prioritarias.',
            })

        # Deficit energetico
        geracao_total = dados['geracao_solar'] + dados['geracao_eolica']
        if dados['consumo'] > geracao_total * 1.2:
            alertas.append({
                'severidade': 'ALERTA', 'modulo': 'energia',
                'titulo': 'Deficit energetico',
                'descricao': (f"Consumo {dados['consumo']} kWh > "
                              f"geracao {geracao_total:.1f} kWh"),
                'recomendacao': 'Reduzir carga nao essencial. Priorizar sistemas criticos.',
            })

        # -- Comunicacao --
        if not dados['comunicacao']:
            alertas.append({
                'severidade': 'CRITICO', 'modulo': 'comunicacao',
                'titulo': 'Comunicacao offline',
                'descricao': 'Modulo de comunicacao nao operacional',
                'recomendacao': 'Reinicializar antena principal. Ativar antena de emergencia.',
            })
        elif dados['qualidade_comm'] < FAIXAS['qualidade_comm']['critico']:
            alertas.append({
                'severidade': 'ALERTA', 'modulo': 'comunicacao',
                'titulo': 'Qualidade de comunicacao critica',
                'descricao': f"Qualidade do sinal em {dados['qualidade_comm']}%",
                'recomendacao': 'Verificar orientacao da antena. Reduzir largura de banda.',
            })

        # -- Radiacao --
        if dados['radiacao'] > FAIXAS['radiacao']['critico']:
            alertas.append({
                'severidade': 'CRITICO', 'modulo': 'habitat',
                'titulo': 'Radiacao perigosa',
                'descricao': f"Radiacao em {dados['radiacao']} mSv/h (limite: 1.0)",
                'recomendacao': 'Recolher tripulacao ao habitat. Cancelar atividades externas.',
            })
        elif dados['radiacao'] > FAIXAS['radiacao']['alerta']:
            alertas.append({
                'severidade': 'ALERTA', 'modulo': 'habitat',
                'titulo': 'Radiacao elevada',
                'descricao': f"Radiacao em {dados['radiacao']} mSv/h",
                'recomendacao': 'Limitar exposicao. Monitorar dosimetros.',
            })

        # -- Temperatura interna --
        if dados['temp_interna'] < FAIXAS['temp_interna']['min_critico'] \
                or dados['temp_interna'] > FAIXAS['temp_interna']['max_critico']:
            alertas.append({
                'severidade': 'CRITICO', 'modulo': 'habitat',
                'titulo': 'Temperatura interna critica',
                'descricao': f"Temperatura em {dados['temp_interna']}C",
                'recomendacao': 'Verificar regulacao termica. Isolar compartimentos.',
            })
        elif dados['temp_interna'] < FAIXAS['temp_interna']['min_alerta'] \
                or dados['temp_interna'] > FAIXAS['temp_interna']['max_alerta']:
            alertas.append({
                'severidade': 'ALERTA', 'modulo': 'habitat',
                'titulo': 'Temperatura fora da faixa ideal',
                'descricao': f"Temperatura em {dados['temp_interna']}C (ideal: 18-28C)",
                'recomendacao': 'Ajustar termostato. Verificar vedacao do habitat.',
            })

        # -- Modulos offline --
        nomes = {
            'suporte_vida': ('Suporte a Vida', 'CRITICO'),
            'energia':      ('Energia',        'CRITICO'),
            'comunicacao':  ('Comunicacao',     'CRITICO'),
            'habitat':      ('Habitat',         'CRITICO'),
            'laboratorio':  ('Laboratorio',     'ALERTA'),
            'armazenamento':('Armazenamento',   'ALERTA'),
        }
        for chave, (nome, sev) in nomes.items():
            if not dados.get(chave):
                ja_tem = any(a['modulo'] == chave for a in alertas)
                if not ja_tem:
                    alertas.append({
                        'severidade': sev, 'modulo': chave,
                        'titulo': f'Modulo {nome} offline',
                        'descricao': f'{nome} nao operacional',
                        'recomendacao': f'Reinicializar modulo {nome}. Verificar conexoes.',
                    })

        # -- Vento insuficiente para eolica --
        if dados['velocidade_vento'] < FAIXAS['velocidade_vento']['min_operacional']:
            alertas.append({
                'severidade': 'ALERTA', 'modulo': 'energia',
                'titulo': 'Vento insuficiente para eolica',
                'descricao': f"Velocidade do vento: {dados['velocidade_vento']} km/h (min: 8)",
                'recomendacao': 'Geracao eolica comprometida. Depender de solar e baterias.',
            })

        alertas.sort(key=lambda a: GeradorAlertas.ORDEM_SEVERIDADE.get(a['severidade'], 9))
        return alertas


# ============================================================
# 5. ANALISE E PREVISAO DE DADOS
# ============================================================

class AnaliseDados:
    """Regressao linear e media movel — sem bibliotecas externas."""

    @staticmethod
    def regressao_linear(x: list, y: list) -> tuple[float, float]:
        """y = a*x + b  (minimos quadrados)."""
        n = len(x)
        if n < 2:
            return 0.0, (y[0] if y else 0.0)
        sx  = sum(x)
        sy  = sum(y)
        sxy = sum(xi * yi for xi, yi in zip(x, y))
        sx2 = sum(xi ** 2 for xi in x)
        den = n * sx2 - sx ** 2
        if den == 0:
            return 0.0, sy / n
        a = (n * sxy - sx * sy) / den
        b = (sy - a * sx) / n
        return a, b

    @staticmethod
    def r_quadrado(x: list, y: list, a: float, b: float) -> float:
        """Coeficiente de determinacao R²."""
        y_med = sum(y) / len(y)
        ss_tot = sum((yi - y_med) ** 2 for yi in y)
        ss_res = sum((yi - (a * xi + b)) ** 2 for xi, yi in zip(x, y))
        return 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    @staticmethod
    def media_movel(valores: list, janela: int = 3) -> list[float]:
        """Media movel simples."""
        resultado = []
        for i in range(len(valores)):
            inicio = max(0, i - janela + 1)
            resultado.append(sum(valores[inicio:i + 1]) / (i - inicio + 1))
        return resultado

    @staticmethod
    def prever_reserva(serie: list[float], passos: int = 4) -> dict:
        """Preve reserva de bateria usando regressao linear."""
        x = list(range(len(serie)))
        a, b = AnaliseDados.regressao_linear(x, serie)
        r2 = AnaliseDados.r_quadrado(x, serie, a, b)

        previsoes = []
        for i in range(1, passos + 1):
            idx = len(serie) - 1 + i
            prev = max(0.0, min(100.0, a * idx + b))
            previsoes.append(round(prev, 1))

        # Horas ate nivel critico (25%) — cada ponto = 3h
        horas_ate_critico = None
        if a < 0:
            idx_crit = (25 - b) / a
            h = (idx_crit - (len(serie) - 1)) * 3
            if h > 0:
                horas_ate_critico = round(h, 1)

        if a < -0.5:
            tendencia = 'declinante'
        elif a > 0.5:
            tendencia = 'crescente'
        else:
            tendencia = 'estavel'

        return {
            'coef_angular': round(a, 4),
            'intercepto': round(b, 2),
            'r_quadrado': round(r2, 4),
            'tendencia': tendencia,
            'previsoes': previsoes,
            'horas_ate_critico': horas_ate_critico,
        }

    @staticmethod
    def analisar_temperatura(serie: list[float]) -> dict:
        """Analise de temperatura com media movel."""
        mm = AnaliseDados.media_movel(serie, 3)
        variacao = serie[-1] - serie[0] if len(serie) >= 2 else 0
        media = sum(serie) / len(serie) if serie else 0

        if variacao > 0.5:
            tend = 'aquecendo'
        elif variacao < -0.5:
            tend = 'resfriando'
        else:
            tend = 'estavel'

        return {
            'media': round(media, 1),
            'minima': round(min(serie), 1),
            'maxima': round(max(serie), 1),
            'variacao': round(variacao, 1),
            'media_movel': [round(v, 1) for v in mm],
            'tendencia': tend,
        }

    @staticmethod
    def recomendacao_previsao(prev: dict) -> str:
        """Gera recomendacao baseada na previsao de reserva."""
        if prev['horas_ate_critico'] is not None:
            h = prev['horas_ate_critico']
            if h < 6:
                return (f"URGENTE: reserva atingira 25% em ~{h:.0f}h. "
                        f"Desligar laboratorio e armazenamento, "
                        f"manter apenas suporte a vida e habitat.")
            if h < 12:
                return (f"ATENCAO: reserva pode atingir 25% em ~{h:.0f}h. "
                        f"Ativar economia e priorizar recarga.")
            return (f"Reserva em queda — nivel critico em ~{h:.0f}h. "
                    f"Planejar reducao de consumo.")
        if prev['tendencia'] == 'declinante':
            return ('Reserva em tendencia de queda. '
                    'Considerar reducao preventiva de consumo.')
        if prev['tendencia'] == 'crescente':
            return 'Reserva em recuperacao. Manter operacoes normais.'
        return 'Reserva estavel. Manter operacoes normais.'


# ============================================================
# 6. SISTEMA INTEGRADO
# ============================================================

class SistemaMonitoramento:
    """Integra leitura, estruturas, logica, alertas e previsao."""

    def __init__(self):
        self.estrutura = EstruturaDados()
        self.dados_telemetria = LeitorDados.carregar_telemetria(
            os.path.join(DATA_DIR, 'dados.csv'))
        self.eventos = LeitorDados.carregar_eventos(
            os.path.join(DATA_DIR, 'eventos.csv'))
        self._popular_estruturas()
        self._processar_eventos()
        self._gerar_alertas()

    # -- Populacao das estruturas --

    def _popular_estruturas(self):
        for d in self.dados_telemetria:
            self.estrutura.horarios.append(d['hora'])
            self.estrutura.serie_geracao_solar.append(d['geracao_solar'])
            self.estrutura.serie_geracao_eolica.append(d['geracao_eolica'])
            self.estrutura.serie_consumo.append(d['consumo'])
            self.estrutura.serie_reserva.append(d['reserva_bateria'])
            self.estrutura.serie_temp_interna.append(d['temp_interna'])
            self.estrutura.serie_temp_externa.append(d['temp_externa'])
            self.estrutura.serie_radiacao.append(d['radiacao'])
            self.estrutura.serie_comm.append(d['qualidade_comm'])
            self.estrutura.serie_vento.append(d['velocidade_vento'])

            self.estrutura.matriz_leituras.append([
                d['hora'], d['geracao_solar'], d['geracao_eolica'],
                d['consumo'], d['reserva_bateria'], d['temp_interna'],
                d['temp_externa'], d['radiacao'], d['qualidade_comm'],
                d['velocidade_vento'],
            ])

        ultimo = self.dados_telemetria[-1]

        self.estrutura.modulos = {
            'suporte_vida':  {'nome': 'Suporte a Vida',  'status': ultimo['suporte_vida'],
                              'desc': 'Oxigenio, pressao e filtragem', 'prior': 1},
            'energia':       {'nome': 'Energia',          'status': ultimo['energia'],
                              'desc': 'Solar, eolica e baterias',     'prior': 2},
            'comunicacao':   {'nome': 'Comunicacao',      'status': ultimo['comunicacao'],
                              'desc': 'Antenas e link Terra',         'prior': 3},
            'habitat':       {'nome': 'Habitat',          'status': ultimo['habitat'],
                              'desc': 'Termica, estrutura e vedacao', 'prior': 4},
            'laboratorio':   {'nome': 'Laboratorio',      'status': ultimo['laboratorio'],
                              'desc': 'Pesquisa e experimentos',      'prior': 5},
            'armazenamento': {'nome': 'Armazenamento',    'status': ultimo['armazenamento'],
                              'desc': 'Suprimentos e pecas',          'prior': 6},
        }

        h = self.estrutura.hierarquia['missao_espacial']
        h['energia']['solar']['geracao_kwh'] = ultimo['geracao_solar']
        h['energia']['eolica']['geracao_kwh'] = ultimo['geracao_eolica']
        h['energia']['baterias']['reserva_pct'] = ultimo['reserva_bateria']
        h['habitat']['temperatura']['interna_c'] = ultimo['temp_interna']
        h['habitat']['temperatura']['externa_c'] = ultimo['temp_externa']
        h['habitat']['comunicacao']['status'] = ultimo['comunicacao']

    def _processar_eventos(self):
        for ev in self.eventos:
            self.estrutura.empilhar_evento(ev)

    def _gerar_alertas(self):
        for d in self.dados_telemetria:
            for a in GeradorAlertas.gerar_alertas(d):
                a['hora'] = d['hora']
                self.estrutura.enfileirar_alerta(a)

    # -- Consultas --

    def visao_geral(self) -> dict:
        ultimo = self.dados_telemetria[-1]
        diag = MotorLogica.diagnosticar(ultimo)
        anomalias = LeitorDados.detectar_anomalias(self.dados_telemetria)
        online = sum(1 for m in self.estrutura.modulos.values() if m['status'])
        total = len(self.estrutura.modulos)
        gt = ultimo['geracao_solar'] + ultimo['geracao_eolica']
        return {
            'status_geral': diag['status_geral'],
            'diagnostico': diag,
            'modulos': self.estrutura.modulos,
            'modulos_online': online,
            'modulos_total': total,
            'energia': {
                'solar': ultimo['geracao_solar'],
                'eolica': ultimo['geracao_eolica'],
                'total': round(gt, 1),
                'consumo': ultimo['consumo'],
                'reserva': ultimo['reserva_bateria'],
                'balanco': round(gt - ultimo['consumo'], 1),
            },
            'ambiente': {
                'temp_interna': ultimo['temp_interna'],
                'temp_externa': ultimo['temp_externa'],
                'radiacao': ultimo['radiacao'],
                'comm': ultimo['qualidade_comm'],
                'vento': ultimo['velocidade_vento'],
            },
            'anomalias': anomalias,
            'hora_atual': ultimo['hora'],
        }

    def alertas(self) -> list[dict]:
        return list(self.estrutura.fila_alertas)

    def eventos_pilha(self) -> list[dict]:
        return list(reversed(self.estrutura.pilha_eventos))

    def previsao(self) -> dict:
        prev = AnaliseDados.prever_reserva(self.estrutura.serie_reserva)
        prev['recomendacao'] = AnaliseDados.recomendacao_previsao(prev)
        temp = AnaliseDados.analisar_temperatura(self.estrutura.serie_temp_interna)
        mm_consumo = AnaliseDados.media_movel(self.estrutura.serie_consumo, 3)
        gtotal = [s + e for s, e in zip(
            self.estrutura.serie_geracao_solar,
            self.estrutura.serie_geracao_eolica)]
        return {
            'reserva': {'serie': self.estrutura.serie_reserva, 'previsao': prev},
            'temperatura': temp,
            'consumo': {
                'serie': self.estrutura.serie_consumo,
                'media_movel': [round(v, 1) for v in mm_consumo],
            },
            'geracao': {
                'solar': self.estrutura.serie_geracao_solar,
                'eolica': self.estrutura.serie_geracao_eolica,
                'total': gtotal,
            },
            'horarios': self.estrutura.horarios,
        }

    def matriz(self) -> dict:
        return {
            'colunas': self.estrutura.colunas_matriz,
            'dados': self.estrutura.matriz_leituras,
        }

    def hierarquia(self) -> dict:
        return self.estrutura.hierarquia

    def diagnostico_idx(self, idx: int) -> dict:
        if 0 <= idx < len(self.dados_telemetria):
            return MotorLogica.diagnosticar(self.dados_telemetria[idx])
        return {}

    def timeline_diagnosticos(self) -> list[dict]:
        """Diagnostico para cada horario (usado no grafico de timeline)."""
        resultados = []
        for i, d in enumerate(self.dados_telemetria):
            diag = MotorLogica.diagnosticar(d)
            resultados.append({
                'hora': d['hora'],
                'status': diag['status_geral'],
                'nivel': diag['nivel'],
                'regras_criticas': [r for r in diag['regras_ativadas']
                                    if r['resultado'] != 'NORMAL'],
            })
        return resultados


# ============================================================
# 7. GERACAO DE RELATORIO PDF
# ============================================================

def gerar_relatorio_pdf(sistema: SistemaMonitoramento, caminho: str):
    """Gera relatorio tecnico em PDF (4-8 paginas)."""
    try:
        from fpdf import FPDF
    except ImportError:
        print("  fpdf2 nao instalado. Execute: pip install fpdf2")
        return False

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    largura = 170

    def titulo_secao(texto):
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(0, 100, 200)
        pdf.cell(0, 10, texto, ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    def texto(t, negrito=False):
        pdf.set_font('Helvetica', 'B' if negrito else '', 10)
        pdf.multi_cell(largura, 5, t)
        pdf.ln(1)

    # --- Pagina 1: Capa ---
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 24)
    pdf.ln(40)
    pdf.cell(0, 15, 'MissionControl', ln=True, align='C')
    pdf.set_font('Helvetica', '', 16)
    pdf.cell(0, 10, 'Sistema Inteligente de Monitoramento', ln=True, align='C')
    pdf.cell(0, 10, 'de Missao Espacial', ln=True, align='C')
    pdf.ln(20)
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 8, 'Global Solution 2026 - FIAP', ln=True, align='C')
    pdf.cell(0, 8, 'Ciencias da Computacao - 1o Semestre', ln=True, align='C')
    pdf.ln(10)
    pdf.cell(0, 8, 'Marcelo Bastianello Baldin', ln=True, align='C')
    pdf.cell(0, 8, 'RM568746 - Grupo 28', ln=True, align='C')
    pdf.ln(20)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 8, 'Maio 2026', ln=True, align='C')

    # --- Pagina 2: Introducao e Analise ---
    pdf.add_page()
    titulo_secao('1. Introducao')
    texto(
        'Este relatorio apresenta o sistema MissionControl, desenvolvido como '
        'resposta ao desafio Global Solution 2026 da FIAP. O sistema simula o '
        'monitoramento operacional de uma base espacial em Marte (Sol 147), '
        'integrando leitura de telemetria, organizacao em estruturas de dados, '
        'regras logicas de diagnostico, alertas automaticos e previsao de '
        'variaveis criticas por regressao linear.')
    pdf.ln(2)
    titulo_secao('2. Analise do Problema')
    texto(
        'O cenario simulado envolve uma base marciana com 6 modulos criticos: '
        'Suporte a Vida, Energia, Comunicacao, Habitat, Laboratorio e '
        'Armazenamento. A telemetria cobre 24 horas (8 leituras a cada 3h) '
        'com dados de geracao energetica (solar e eolica), consumo, reserva '
        'de bateria, temperatura (interna e externa), radiacao, qualidade de '
        'comunicacao e velocidade do vento.')
    texto(
        'O cenario inclui uma degradacao progressiva: comunicacao falha as '
        '12:00, energia entra em emergencia as 15:00, e a reserva de bateria '
        'cai de 82% para 28% ao longo do dia. Uma inconsistencia proposital '
        '(geracao solar de 12 kWh a meia-noite) testa a capacidade de '
        'deteccao de anomalias do sistema.')
    texto(
        'O sistema deve interpretar esses dados, classificar situacoes, '
        'gerar alertas priorizados e prever quando a reserva atingira nivel '
        'critico, influenciando as recomendacoes operacionais.')

    # --- Pagina 3: Estruturas de Dados ---
    pdf.add_page()
    titulo_secao('3. Estruturas de Dados Utilizadas')

    texto('3.1 Listas (series temporais)', negrito=True)
    texto(
        'Listas Python armazenam series temporais de cada variavel: '
        'serie_geracao_solar, serie_consumo, serie_reserva, serie_temp_interna, '
        'etc. Permitem iteracao sequencial, calculo de tendencias e alimentacao '
        'dos graficos do dashboard.')

    texto('3.2 Fila (collections.deque - FIFO)', negrito=True)
    texto(
        'Uma fila (deque) organiza os alertas pendentes por ordem de chegada. '
        'Alertas sao enfileirados com append() e desenfileirados com popleft(). '
        'A ordenacao por severidade garante que alertas criticos sejam '
        'processados primeiro.')

    texto('3.3 Pilha (lista Python - LIFO)', negrito=True)
    texto(
        'Uma pilha registra os eventos criticos usando append() e pop(). '
        'A visualizacao mostra os eventos mais recentes primeiro (topo da '
        'pilha), permitindo analise rapida das ultimas ocorrencias.')

    texto('3.4 Dicionario (tabela hash)', negrito=True)
    texto(
        'Um dicionario mapeia o nome de cada modulo a seus dados (status, '
        'descricao, prioridade). Permite acesso O(1) por nome, essencial '
        'para consultas rapidas durante o diagnostico.')

    texto('3.5 Hierarquia (dicionario aninhado - arvore)', negrito=True)
    texto(
        'A hierarquia da missao e representada como dicionario aninhado: '
        'missao > energia (solar, eolica, baterias) e habitat (oxigenio, '
        'temperatura, comunicacao). Reflete a organizacao real de uma base.')

    texto('3.6 Matriz (lista de listas)', negrito=True)
    texto(
        'Uma matriz 8x10 organiza todas as leituras: cada linha e um horario, '
        'cada coluna uma variavel. Permite visualizacao tabular completa e '
        'acesso por indice [horario][variavel].')

    # --- Pagina 4: Regras Logicas ---
    pdf.add_page()
    titulo_secao('4. Regras Logicas e Diagnostico')

    texto('Expressao booleana principal:', negrito=True)
    pdf.set_font('Courier', '', 9)
    pdf.multi_cell(largura, 4,
        'CRITICO = (reserva < 25 AND consumo > geracao_total)\n'
        '       OR (NOT comunicacao AND radiacao > 1.0)\n'
        '       OR (NOT suporte_vida)')
    pdf.set_font('Helvetica', '', 10)
    pdf.ln(3)

    regras_texto = [
        ('R1 - Energia', 'IF reserva < 25% AND consumo > geracao THEN CRITICO',
         'Detecta deficit energetico critico quando a reserva esta baixa e o consumo supera a geracao.'),
        ('R2 - Comunicacao + Radiacao', 'IF NOT comunicacao OR (radiacao > 1.0 AND NOT suporte_vida) THEN CRITICO',
         'Identifica situacao de isolamento (sem comunicacao) ou exposicao a radiacao sem protecao.'),
        ('R3 - Temperatura', 'IF (temp < 15 OR temp > 30) AND NOT habitat THEN CRITICO',
         'Alerta quando a temperatura sai da faixa segura e o habitat nao pode compensar.'),
        ('R4 - Radiacao', 'IF radiacao > 0.8 AND NOT (habitat AND suporte_vida) THEN ALERTA',
         'Monitora radiacao elevada quando os sistemas de protecao estao comprometidos.'),
        ('R5 - Suporte a Vida', 'IF NOT suporte_vida THEN CRITICO',
         'Prioridade absoluta: qualquer falha no suporte a vida e emergencia maxima.'),
    ]
    for nome, expr, explicacao in regras_texto:
        texto(nome, negrito=True)
        pdf.set_font('Courier', '', 9)
        pdf.multi_cell(largura, 4, expr)
        pdf.set_font('Helvetica', '', 10)
        texto(explicacao)

    # --- Pagina 5: Previsao ---
    pdf.add_page()
    titulo_secao('5. Analise e Previsao de Dados')

    texto('5.1 Regressao Linear', negrito=True)
    texto(
        'A tecnica de regressao linear por minimos quadrados e aplicada a '
        'serie temporal da reserva de bateria para estimar quando atingira '
        'o nivel critico de 25%. A formula y = ax + b e calculada sem '
        'bibliotecas externas, usando apenas operacoes aritmeticas basicas.')
    prev = sistema.previsao()
    p = prev['reserva']['previsao']
    texto(
        f"Resultado: coeficiente angular = {p['coef_angular']}, "
        f"R2 = {p['r_quadrado']}, tendencia {p['tendencia']}. "
        f"Previsoes: {p['previsoes']}%."
    )
    if p['horas_ate_critico']:
        texto(f"Tempo estimado ate nivel critico: {p['horas_ate_critico']} horas.")
    texto(f"Recomendacao: {p['recomendacao']}")

    texto('5.2 Media Movel', negrito=True)
    texto(
        'A media movel com janela de 3 pontos e aplicada ao consumo e a '
        'temperatura interna para suavizar flutuacoes e identificar '
        'tendencias. Permite distinguir variacoes pontuais de tendencias '
        'reais nos dados.')

    texto('5.3 Influencia nas Decisoes', negrito=True)
    texto(
        'A previsao de reserva influencia diretamente as recomendacoes: '
        'se a reserva atingira 25% em menos de 6 horas, o sistema recomenda '
        'desligamento imediato de modulos nao essenciais. Essa integracao '
        'entre previsao e acao e o diferencial do sistema.')

    # --- Pagina 6: Alertas ---
    pdf.add_page()
    titulo_secao('6. Alertas Automaticos e Recomendacoes')
    texto(
        'O sistema gera alertas automaticos classificados em 3 niveis de '
        'severidade: NORMAL (verde), ALERTA (amarelo) e CRITICO (vermelho). '
        'Cada alerta inclui o modulo afetado, descricao do problema e uma '
        'recomendacao de acao especifica.')
    texto(
        'Os alertas sao organizados em uma fila (FIFO) e ordenados por '
        'severidade, priorizando os criticos. As recomendacoes variam de '
        'monitoramento continuo (normal) ate protocolos de emergencia '
        '(critico), incluindo:')
    recomendacoes = [
        '- Desligar laboratorio e armazenamento em caso de energia critica',
        '- Ativar antena de emergencia em caso de perda de comunicacao',
        '- Recolher tripulacao ao habitat em caso de radiacao perigosa',
        '- Restaurar suporte a vida como prioridade absoluta',
        '- Ativar modo de economia energetica quando reserva < 40%',
    ]
    for r in recomendacoes:
        texto(r)

    # --- Pagina 7: Decisoes Tecnicas ---
    pdf.add_page()
    titulo_secao('7. Decisoes Tecnicas e Arquitetura')

    texto('7.1 Arquitetura', negrito=True)
    texto(
        'O sistema utiliza arquitetura MVC simplificada: o modelo '
        '(SistemaMonitoramento) integra leitura, estruturas e logica; '
        'o controlador (Flask) expoe endpoints REST; e a visao '
        '(dashboard HTML/JS) renderiza os dados com Chart.js.')

    texto('7.2 Stack Tecnologico', negrito=True)
    texto(
        'Backend: Python 3.9+ com Flask. Frontend: HTML5, CSS3, JavaScript '
        'vanilla com Chart.js (CDN). Dados: CSV externo. Sem banco de dados '
        '- todos os dados sao processados em memoria a partir dos CSV.')

    texto('7.3 Tema Visual', negrito=True)
    texto(
        'Interface com tema espacial escuro (fundo #0b0d1a), com indicadores '
        'visuais coloridos: verde (normal), amarelo (alerta) e vermelho '
        '(critico). Sidebar com navegacao por secoes.')

    texto('7.4 Justificativa das Estruturas', negrito=True)
    texto(
        'Cada estrutura foi escolhida por adequacao ao problema: listas para '
        'dados sequenciais, fila para processamento ordenado de alertas, '
        'pilha para historico recente, dicionario para busca rapida, '
        'hierarquia para organizacao logica e matriz para visao tabular.')

    # --- Pagina 8: Conclusao ---
    pdf.add_page()
    titulo_secao('8. Conclusao')
    texto(
        'O sistema MissionControl demonstra a aplicacao pratica de conceitos '
        'de programacao, estruturas de dados e algoritmos em um cenario '
        'realista de operacao espacial. A integracao entre leitura de dados, '
        'diagnostico logico, alertas automaticos e previsao por regressao '
        'linear cria um sistema capaz de apoiar decisoes operacionais '
        'criticas.')
    texto(
        'O projeto aplica conteudos das 3 primeiras fases do curso: '
        'logica e algoritmos (Fase 1), estruturas de dados como listas, '
        'filas e pilhas (Fase 2), e dicionarios, hierarquias, matrizes '
        'e analise de dados (Fase 3). A interface web com tema espacial '
        'torna o sistema acessivel e intuitivo para operadores.')
    texto(
        'Principais aprendizados: a importancia de escolher estruturas de '
        'dados adequadas ao problema, a construcao de regras logicas '
        'claras e justificadas, e a integracao entre analise de dados '
        'e tomada de decisao automatizada.')

    pdf.output(caminho)
    return True


# ============================================================
# 8. APLICACAO FLASK
# ============================================================

app = Flask(__name__)
app.secret_key = 'missioncontrol-gs2026-fiap-rm568746'

sistema: SistemaMonitoramento | None = None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usr = request.form.get('usuario', '')
        pwd = request.form.get('senha', '')
        if usr in USUARIOS and USUARIOS[usr]['senha'] == pwd:
            session['usuario'] = usr
            session['nome'] = USUARIOS[usr]['nome']
            return redirect(url_for('dashboard'))
        return render_template('login.html', erro='Credenciais invalidas')
    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', nome=session.get('nome'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------- API REST ----------

@app.route('/api/visao-geral')
@login_required
def api_visao_geral():
    return jsonify(sistema.visao_geral())


@app.route('/api/energia')
@login_required
def api_energia():
    p = sistema.previsao()
    return jsonify({
        'horarios': p['horarios'],
        'solar': p['geracao']['solar'],
        'eolica': p['geracao']['eolica'],
        'consumo': p['consumo']['serie'],
        'media_movel_consumo': p['consumo']['media_movel'],
        'reserva': p['reserva']['serie'],
        'previsao_reserva': p['reserva']['previsao'],
    })


@app.route('/api/ambiente')
@login_required
def api_ambiente():
    p = sistema.previsao()
    return jsonify({
        'horarios': p['horarios'],
        'temp_interna': sistema.estrutura.serie_temp_interna,
        'temp_externa': sistema.estrutura.serie_temp_externa,
        'temp_media_movel': p['temperatura']['media_movel'],
        'radiacao': sistema.estrutura.serie_radiacao,
        'comm': sistema.estrutura.serie_comm,
        'vento': sistema.estrutura.serie_vento,
        'analise_temp': p['temperatura'],
    })


@app.route('/api/alertas')
@login_required
def api_alertas():
    return jsonify(sistema.alertas())


@app.route('/api/eventos')
@login_required
def api_eventos():
    return jsonify(sistema.eventos_pilha())


@app.route('/api/matriz')
@login_required
def api_matriz():
    return jsonify(sistema.matriz())


@app.route('/api/hierarquia')
@login_required
def api_hierarquia():
    return jsonify(sistema.hierarquia())


@app.route('/api/previsao')
@login_required
def api_previsao():
    return jsonify(sistema.previsao())


@app.route('/api/timeline')
@login_required
def api_timeline():
    return jsonify(sistema.timeline_diagnosticos())


@app.route('/api/diagnostico/<int:idx>')
@login_required
def api_diagnostico(idx):
    return jsonify(sistema.diagnostico_idx(idx))


@app.route('/api/gerar-relatorio')
@login_required
def api_gerar_relatorio():
    caminho = os.path.join(DOCS_DIR, 'relatorio.pdf')
    os.makedirs(DOCS_DIR, exist_ok=True)
    ok = gerar_relatorio_pdf(sistema, caminho)
    if ok:
        return jsonify({'status': 'ok', 'mensagem': 'Relatorio gerado em docs/relatorio.pdf'})
    return jsonify({'status': 'erro', 'mensagem': 'fpdf2 nao instalado'}), 500


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    sistema = SistemaMonitoramento()

    print()
    print('=' * 60)
    print('  MissionControl - Monitoramento de Missao Espacial')
    print('  Global Solution 2026 - FIAP')
    print('=' * 60)
    print()
    print(f'  Telemetria: {len(sistema.dados_telemetria)} leituras carregadas')
    print(f'  Eventos: {len(sistema.eventos)} registros carregados')
    print(f'  Alertas: {len(sistema.alertas())} gerados')
    print(f'  Anomalias: {len(LeitorDados.detectar_anomalias(sistema.dados_telemetria))} detectadas')
    print()

    visao = sistema.visao_geral()
    print(f'  Status da missao: {visao["status_geral"]}')
    print(f'  Modulos online: {visao["modulos_online"]}/{visao["modulos_total"]}')
    print(f'  Reserva de bateria: {visao["energia"]["reserva"]}%')
    print()

    prev = sistema.previsao()
    p = prev['reserva']['previsao']
    print(f'  Previsao (regressao linear):')
    print(f'    Tendencia: {p["tendencia"]}')
    print(f'    R²: {p["r_quadrado"]}')
    if p['horas_ate_critico']:
        print(f'    Nivel critico em: ~{p["horas_ate_critico"]}h')
    print(f'    Recomendacao: {p["recomendacao"]}')
    print()
    print('  Acesse: http://localhost:5050')
    print('  Usuario: usuario | Senha: senha')
    print('  Para encerrar: Ctrl+C')
    print()

    app.run(host='0.0.0.0', port=5050, debug=False)

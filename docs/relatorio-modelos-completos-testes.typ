#set document(
  title: "Testes e experimentos dos modelos completos M1, M2 e M3",
  author: "UFABC — PGC — WSRP",
  date: datetime(year: 2026, month: 10, day: 18),
)
#set page(
  paper: "a4",
  margin: (x: 1.7cm, y: 1.9cm),
  footer: context {
    if counter(page).get().first() == 1 { return }
    set text(size: 8.5pt)
    [Testes e experimentos dos modelos completos M1, M2 e M3]
    h(1fr)
    counter(page).display("1")
  },
)
#set text(lang: "pt", region: "br", size: 10.5pt, hyphenate: true)
#set par(justify: true, leading: 0.62em)
#set heading(numbering: "1.1")
#show heading.where(level: 1): set block(above: 1.5em, below: 0.7em)
#set table(stroke: 0.4pt + luma(160), inset: (x: 4pt, y: 3.5pt))
#show table: set text(size: 8.5pt)
#show table.cell.where(y: 0): set text(hyphenate: false)
#show figure: set text(size: 9pt)
#show figure: set block(breakable: true)

#align(center)[
  #v(2.2cm)
  #text(size: 12pt)[Universidade Federal do ABC]
  #v(0.3cm)
  #text(size: 11pt)[Trabalho de graduação — PGC]
  #v(1.6cm)
  #text(size: 20pt, weight: "bold")[Testes e experimentos do WSRP]
  #v(0.45cm)
  #text(size: 13pt)[M1, M1.a, M2 e M3: protocolo, resultados e análise no catálogo real de São Paulo]
  #v(1.4cm)
  #text(size: 11pt)[18 de outubro de 2026]
  #v(1fr)
  #text(size: 9.5pt)[
    Este texto reúne o protocolo experimental, os resultados computacionais e a análise
    dos testes de escalabilidade e estresse executados em Google Colab para os
    modelos completos M1, M1.a, M2 e M3, registrados em `docs/experiments/complete-models.md`,
    além do registro da suíte de testes automatizados do projeto.
    As formulações matemáticas e notas de decisão estão no relatório complementar de documentação.
  ]
]

#pagebreak()
#outline(depth: 2, title: [Sumário])

= Introdução

O problema de roteamento e agendamento de equipes de corretores (_Workforce Scheduling and Routing Problem_ — WSRP) formulado nos modelos completos M1, M2 e M3 envolve decisões complexas de designação, janelas de atendimento, pausas intrajornada e restrições de duração de jornada e turno.

Para avaliar a viabilidade, escalabilidade e qualidade dos planos gerados, foi realizada uma bateria de experimentos computacionais com o resolvedor Gurobi utilizando dados do catálogo real de aluguéis residenciais da cidade de São Paulo, cobrindo tanto um recorte concentrado de bairro (Moema) quanto a dispersão geográfica da cidade inteira.

Este documento registra:
1. O protocolo experimental compartilhado entre os modelos;
2. As tabelas-resumo de alcance e os maiores casos resolvidos com solução ótima;
3. Os resultados detalhados nas instâncias de Moema e da capital paulista;
4. Os testes de estresse com aumento coordenado de instâncias e frota;
5. A discussão aprofundada dos resultados e o comportamento das funções objetivo e restrições de jornada;
6. A descrição da suíte de testes automatizados de unidade e integração implementada no repositório.

As formulações matemáticas rigorosas, os parâmetros do gerador e as notas de decisão encontram-se documentados no relatório complementar `relatorio-modelos-completos-documentacao.pdf`.

Os números deste relatório são os do Google Colab, em 11 e 12 de outubro de 2026, registrados em `docs/experiments/complete-models.md`. O notebook é `notebooks/ufabc-pgc-wsrp.ipynb`. No Colab, um modelo foi concluído em todos os tamanhos e nos dois lugares, e só então `MODEL_VERSION` mudou. As tabelas abaixo estão agrupadas por número de imóveis, para os quatro modelos da mesma amostra ficarem juntos.

= Protocolo experimental

#figure(
  table(
    columns: (4.2cm, 1fr),
    table.header([Entrada], [Valor]),
    [Conjunto de dados], [`real`, catálogo de aluguéis],
    [Cidade], [São Paulo],
    [Lugares, nesta ordem], [Moema e depois a cidade inteira],
    [Semente], [8],
    [Frota], [3 corretores, fixa],
    [Resolvedor], [`gurobi_direct`, folga MIP 0, `raw = False`, limite de 300 s],
    [Visitas marcadas], [M1 e M1.a testados com agenda 100% marcada (`fixed_ratio = 1`, benchmark base) e regimes flexíveis ($r = 0,5$ e $r = 0$)],
    [Tamanhos], [5, 10, 15, 20, 25, 30, 40 e 50 imóveis],
  ),
  caption: [Entrada compartilhada. O modo impresso pelo notebook para `raw = False` é `default`.],
)

M2 e M3 forçam `fixed_ratio = 1` (`STRICT_TIME_MODELS`), enquanto M1 e M1.a aceitam qualquer `fixed_ratio` em $[0, 1]$. Um modelo para no primeiro tamanho em que a geração falha ou a resolução atinge 300 segundos. Os tamanhos maiores daquele modelo, naquele lugar, não foram executados.

Toda resolução registrada usa `raw = False`. As linhas do M3 são uma chamada de `build_model_m3`, com os três corretores autorizados. Elas não chamam `pareto_front`. Esse auxiliar grava `raw = True` no código, então chamá-lo teria quebrado o protocolo. A frente, uma resolução por tamanho de frota, não foi executada. A célula de objetivo é o que o notebook imprime. As rotas ficam de fora.

= Tabela-resumo e alcance dos modelos

#figure(
  table(
    columns: (2.5cm, 2.3cm, 4.2cm, 1fr),
    table.header([Lugar], [Modelo], [Tamanhos com plano ótimo], [Onde a série parou]),
    [Moema], [M1 ($r=1$)], [5 a 40 imóveis], [50: inviável (presolve)],
    [Moema], [M1.a ($r=1$)], [5 a 40 imóveis], [50: inviável (presolve)],
    [Moema], [M1 ($r=0,5$)], [5 a 20 imóveis], [25: limite de 300 s (gap 0,0032%)],
    [Moema], [M1.a ($r=0,5$)], [5 a 25 imóveis], [30: não executado],
    [Moema], [M1 ($r=0$)], [5, 10 e 15 imóveis], [20: limite de 300 s (gap 0,0035%)],
    [Moema], [M1.a ($r=0$)], [5, 10 e 15 imóveis], [20: limite de 300 s (gap 0,0028%)],
    [Moema], [M2], [5, 10 e 15 imóveis], [20: inviável (presolve)],
    [Moema], [M3], [5 a 40 imóveis], [50: inviável (presolve)],
    [São Paulo], [M1 ($r=1$)], [5 a 25 imóveis], [30: inviável (presolve)],
    [São Paulo], [M1.a ($r=1$)], [5 a 25 imóveis], [30: inviável (presolve)],
    [São Paulo], [M1 ($r=0$)], [5 e 10 imóveis], [15: limite de 300 s],
    [São Paulo], [M2], [5 e 10 imóveis], [15: inviável (presolve)],
    [São Paulo], [M3], [5 a 25 imóveis], [30: inviável (presolve)],
  ),
  caption: [Alcance de cada modelo com 3 corretores, semente 8 e `raw = False`. M1 ($r=1$), M1.a ($r=1$) e M3 param juntos (50 imóveis em Moema e 30 em São Paulo), no teste das 12 horas. M2 para antes, nos turnos rígidos e com um corretor de folga. Sob flexibilidade parcial ($r=0,5$), o M1 (Big-M global) atinge o limite de 300 s em 25 imóveis com gap residual de 0,0032%, enquanto o M1.a (MTZ levantado de Desrochers-Laporte) fecha a otimalidade comprovada até 25 imóveis. Sob flexibilidade total ($r=0$), ambos alcançam até 15 imóveis e esgotam os 300 s em 20 imóveis com gaps residuais inferiores a 0,004%.],
)

O maior caso que cada modelo ainda resolveu, no mesmo protocolo:

#figure(
  table(
    columns: (2.0cm, 2.3cm, 1.4cm, 1.7cm, 1.6cm, 1.4cm, 1.4cm, 1fr),
    table.header([Lugar], [Modelo], [Imóveis], [Tempo (s)], [Corretores], [Atraso], [Extra], [Distância]),
    [Moema], [M1 ($r=1$)], [40], [0,9731], [3 de 3], [0], [452], [293,27],
    [Moema], [M1.a ($r=1$)], [40], [0,6261], [3 de 3], [0], [452], [293,27],
    [Moema], [M1 ($r=0,5$)], [20], [8,8430], [3 de 3], [0], [0], [174,24],
    [Moema], [M1.a ($r=0,5$)], [25], [242,9612], [3 de 3], [0], [11], [113,61],
    [Moema], [M1 ($r=0$)], [15], [1,2526], [3 de 3], [0], [0], [25,06],
    [Moema], [M1.a ($r=0$)], [15], [1,6219], [3 de 3], [0], [0], [25,06],
    [Moema], [M2], [15], [0,2170], [2 de 3], [12], [—], [466,18],
    [Moema], [M3], [40], [1,2645], [3 de 3], [400], [476], [284,52],
    [São Paulo], [M1 ($r=1$)], [25], [0,4059], [3 de 3], [0], [247], [690,63],
    [São Paulo], [M1.a ($r=1$)], [25], [0,2003], [3 de 3], [0], [247], [690,63],
    [São Paulo], [M1 ($r=0$)], [10], [243,0094], [2 de 3], [0], [0], [146,09],
    [São Paulo], [M2], [10], [0,1349], [2 de 3], [4], [—], [756,97],
    [São Paulo], [M3], [25], [0,4821], [3 de 3], [250], [276], [739,78],
  ),
  caption: [Maior instância ótima de cada série. Atraso e hora extra em minutos. Distância em unidades do mapa (4 por km). M1 e M1.a produzem soluções de qualidade e métricas rigorosamente equivalentes em todos os regimes sob $r=1$ e $r=0$. O M2 não imprime hora extra. O M3 é uma resolução, não a frente.],
)

#pagebreak()
= Resultados detalhados em Moema

Três corretores, semente 8, solver no modo `default`. Uma linha em branco no registro original aparece aqui como não executada: o modelo já tinha parado num tamanho menor.

#figure(
  table(
    inset: (x: 3.5pt, y: 1.8pt),
    columns: (1.1cm, 2.3cm, 3.1cm, 1.7cm, 1.4cm, 1.1cm, 1.1cm, 1fr),
    align: (center, center, left, right, center, right, right, right),
    table.header(repeat: true, [Imóveis], [Modelo], [Status], [Tempo (s)], [Usados], [Atraso], [Extra], [Dist.]),
    [5], [M1 ($r=1$)], [ótimo], [0,0940], [2 de 3], [0], [40], [84,45],
    [5], [M1.a ($r=1$)], [ótimo], [0,3375], [2 de 3], [0], [40], [84,45],
    [5], [M1 ($r=0,5$)], [ótimo], [0,1013], [2 de 3], [0], [40], [4,24],
    [5], [M1.a ($r=0,5$)], [ótimo], [0,0997], [2 de 3], [0], [40], [4,24],
    [5], [M1 ($r=0$)], [ótimo], [0,1165], [2 de 3], [0], [0], [4,24],
    [5], [M1.a ($r=0$)], [ótimo], [0,0985], [2 de 3], [0], [0], [4,24],
    [5], [M2], [ótimo], [0,0761], [2 de 3], [0], [—], [312,95],
    [5], [M3], [1 resolução], [0,1120], [3 de 3], [50], [60], [70,72],
    [10], [M1 ($r=1$)], [ótimo], [0,1332], [3 de 3], [0], [10], [151,60],
    [10], [M1.a ($r=1$)], [ótimo], [0,0862], [3 de 3], [0], [10], [151,60],
    [10], [M1 ($r=0,5$)], [ótimo], [0,3247], [2 de 3], [0], [10], [79,74],
    [10], [M1.a ($r=0,5$)], [ótimo], [0,4302], [2 de 3], [0], [10], [79,74],
    [10], [M1 ($r=0$)], [ótimo], [0,4749], [2 de 3], [0], [0], [16,06],
    [10], [M1.a ($r=0$)], [ótimo], [0,6790], [2 de 3], [0], [0], [16,06],
    [10], [M2], [ótimo], [0,1320], [2 de 3], [5], [—], [455,22],
    [10], [M3], [1 resolução], [0,1807], [3 de 3], [100], [60], [160,23],
    [15], [M1 ($r=1$)], [ótimo], [0,1960], [3 de 3], [0], [42], [184,02],
    [15], [M1.a ($r=1$)], [ótimo], [0,1370], [3 de 3], [0], [42], [184,02],
    [15], [M1 ($r=0,5$)], [ótimo], [0,8127], [3 de 3], [0], [0], [175,83],
    [15], [M1.a ($r=0,5$)], [ótimo], [0,7770], [3 de 3], [0], [0], [175,83],
    [15], [M1 ($r=0$)], [ótimo], [1,2526], [3 de 3], [0], [0], [25,06],
    [15], [M1.a ($r=0$)], [ótimo], [1,6219], [3 de 3], [0], [0], [25,06],
    [15], [M2], [ótimo], [0,2170], [2 de 3], [12], [—], [466,18],
    [15], [M3], [1 resolução], [0,2676], [3 de 3], [150], [73], [196,95],
    [20], [M1 ($r=1$)], [ótimo], [0,4829], [3 de 3], [0], [25], [191,55],
    [20], [M1.a ($r=1$)], [ótimo], [0,1981], [3 de 3], [0], [25], [191,55],
    [20], [M1 ($r=0,5$)], [ótimo], [8,8430], [3 de 3], [0], [0], [174,24],
    [20], [M1.a ($r=0,5$)], [ótimo], [6,9170], [3 de 3], [0], [0], [174,23],
    [20], [M1 ($r=0$)], [limite (gap 0,0035%)], [300,03], [—], [—], [—], [—],
    [20], [M1.a ($r=0$)], [limite (gap 0,0028%)], [300,02], [—], [—], [—], [—],
    [20], [M2], [inviável (presolve)], [—], [—], [—], [—], [—],
    [20], [M3], [1 resolução], [0,3585], [3 de 3], [200], [93], [208,32],
    [25], [M1 ($r=1$)], [ótimo], [0,7035], [3 de 3], [0], [57], [211,81],
    [25], [M1.a ($r=1$)], [ótimo], [0,3139], [3 de 3], [0], [57], [211,81],
    [25], [M1 ($r=0,5$)], [limite (gap 0,0032%)], [300,03], [—], [—], [—], [—],
    [25], [M1.a ($r=0,5$)], [ótimo], [242,9612], [3 de 3], [0], [11], [113,61],
    [25], [M1 ($r=0$)], [limite (gap 0,0122%)], [300,02], [—], [—], [—], [—],
    [25], [M1.a ($r=0$)], [limite (gap 0,0167%)], [300,02], [—], [—], [—], [—],
    [25], [M2], [inviável (presolve)], [—], [—], [—], [—], [—],
    [25], [M3], [1 resolução], [0,5436], [3 de 3], [250], [137], [224,79],
    [30], [M1 ($r=1$)], [ótimo], [0,5879], [3 de 3], [8], [169], [247,67],
    [30], [M1.a ($r=1$)], [ótimo], [0,3834], [3 de 3], [8], [169], [247,67],
    [30], [M1 ($r=0,5$)], [não executado], [—], [—], [—], [—], [—],
    [30], [M1.a ($r=0,5$)], [não executado], [—], [—], [—], [—], [—],
    [30], [M1 ($r=0$)], [não executado], [—], [—], [—], [—], [—],
    [30], [M1.a ($r=0$)], [não executado], [—], [—], [—], [—], [—],
    [30], [M2], [inviável (presolve)], [—], [—], [—], [—], [—],
    [30], [M3], [1 resolução], [0,7101], [3 de 3], [300], [171], [255,43],
    [40], [M1 ($r=1$)], [ótimo], [0,9731], [3 de 3], [0], [452], [293,27],
    [40], [M1.a ($r=1$)], [ótimo], [0,6261], [3 de 3], [0], [452], [293,27],
    [40], [M1 ($r=0,5$)], [não executado], [—], [—], [—], [—], [—],
    [40], [M1.a ($r=0,5$)], [não executado], [—], [—], [—], [—], [—],
    [40], [M1 ($r=0$)], [não executado], [—], [—], [—], [—], [—],
    [40], [M1.a ($r=0$)], [não executado], [—], [—], [—], [—], [—],
    [40], [M2], [inviável (presolve)], [—], [—], [—], [—], [—],
    [40], [M3], [1 resolução], [1,2645], [3 de 3], [400], [476], [284,52],
    [50], [M1 ($r=1$)], [inviável (presolve)], [—], [—], [—], [—], [—],
    [50], [M1.a ($r=1$)], [inviável (presolve)], [—], [—], [—], [—], [—],
    [50], [M1 ($r=0,5$)], [não executado], [—], [—], [—], [—], [—],
    [50], [M1.a ($r=0,5$)], [não executado], [—], [—], [—], [—], [—],
    [50], [M1 ($r=0$)], [não executado], [—], [—], [—], [—], [—],
    [50], [M1.a ($r=0$)], [não executado], [—], [—], [—], [—], [—],
    [50], [M2], [inviável (presolve)], [—], [—], [—], [—], [—],
    [50], [M3], [inviável (presolve)], [—], [—], [—], [—], [—],
  ),
  caption: [Moema. Atraso e hora extra em minutos. Distância em unidades do mapa. Os planos de M1 ($r=1$) e M1.a ($r=1$) foram rigorosamente idênticos em todas as instâncias viáveis, com M1.a consistentemente mais rápido para $N >= 10$.],
)

#pagebreak()
= Resultados detalhados em São Paulo (cidade inteira)

A cidade inteira, sem bairro. A amostra é de 6.874 anúncios. O resto do protocolo é o de Moema.

#figure(
  table(
    columns: (1.1cm, 2.3cm, 3.1cm, 1.7cm, 1.4cm, 1.1cm, 1.1cm, 1fr),
    align: (center, center, left, right, center, right, right, right),
    table.header(repeat: true, [Imóveis], [Modelo], [Status], [Tempo (s)], [Usados], [Atraso], [Extra], [Dist.]),
    [5], [M1 ($r=1$)], [ótimo], [0,0760], [2 de 3], [0], [50], [144,91],
    [5], [M1 ($r=0$)], [ótimo], [0,2191], [2 de 3], [0], [0], [85,04],
    [5], [M1.a ($r=1$)], [ótimo], [0,0556], [2 de 3], [0], [50], [144,91],
    [5], [M2], [ótimo], [0,0802], [2 de 3], [0], [—], [513,15],
    [5], [M3], [1 resolução], [0,1243], [2 de 3], [50], [70], [144,91],
    [10], [M1 ($r=1$)], [ótimo], [0,3797], [3 de 3], [0], [33], [242,04],
    [10], [M1 ($r=0$)], [ótimo], [243,0094], [2 de 3], [0], [0], [146,09],
    [10], [M1.a ($r=1$)], [ótimo], [0,0733], [3 de 3], [0], [33], [242,04],
    [10], [M2], [ótimo], [0,1349], [2 de 3], [4], [—], [756,97],
    [10], [M3], [1 resolução], [0,1620], [3 de 3], [100], [101], [258,25],
    [15], [M1 ($r=1$)], [ótimo], [0,2045], [3 de 3], [0], [45], [356,76],
    [15], [M1 ($r=0$)], [limite de 300 s], [—], [—], [—], [—], [—],
    [15], [M1.a ($r=1$)], [ótimo], [0,1281], [3 de 3], [0], [45], [356,76],
    [15], [M2], [inviável (presolve)], [—], [—], [—], [—], [—],
    [15], [M3], [1 resolução], [0,2536], [3 de 3], [150], [75], [407,13],
    [20], [M1 ($r=1$)], [ótimo], [0,4340], [3 de 3], [0], [63], [697,40],
    [20], [M1 ($r=0$)], [não executado], [—], [—], [—], [—], [—],
    [20], [M1.a ($r=1$)], [ótimo], [0,1583], [3 de 3], [0], [63], [697,40],
    [20], [M2], [inviável (presolve)], [—], [—], [—], [—], [—],
    [20], [M3], [1 resolução], [0,3672], [3 de 3], [200], [107], [701,27],
    [25], [M1 ($r=1$)], [ótimo], [0,4059], [3 de 3], [0], [247], [690,63],
    [25], [M1 ($r=0$)], [não executado], [—], [—], [—], [—], [—],
    [25], [M1.a ($r=1$)], [ótimo], [0,2003], [3 de 3], [0], [247], [690,63],
    [25], [M2], [inviável (presolve)], [—], [—], [—], [—], [—],
    [25], [M3], [1 resolução], [0,4821], [3 de 3], [250], [276], [739,78],
    [30], [M1 ($r=1$)], [inviável (presolve)], [—], [—], [—], [—], [—],
    [30], [M1 ($r=0$)], [não executado], [—], [—], [—], [—], [—],
    [30], [M1.a ($r=1$)], [inviável (presolve)], [—], [—], [—], [—], [—],
    [30], [M2], [inviável (presolve)], [—], [—], [—], [—], [—],
    [30], [M3], [inviável (presolve)], [—], [—], [—], [—], [—],
    [40], [M1 ($r=1$)], [inviável (presolve)], [—], [—], [—], [—], [—],
    [40], [M1 ($r=0$)], [não executado], [—], [—], [—], [—], [—],
    [40], [M1.a ($r=1$)], [inviável (presolve)], [—], [—], [—], [—], [—],
    [40], [M2], [inviável (presolve)], [—], [—], [—], [—], [—],
    [40], [M3], [inviável (presolve)], [—], [—], [—], [—], [—],
    [50], [M1 ($r=1$)], [inviável (presolve)], [—], [—], [—], [—], [—],
    [50], [M1 ($r=0$)], [não executado], [—], [—], [—], [—], [—],
    [50], [M1.a ($r=1$)], [inviável (presolve)], [—], [—], [—], [—], [—],
    [50], [M2], [inviável (presolve)], [—], [—], [—], [—], [—],
    [50], [M3], [inviável (presolve)], [—], [—], [—], [—], [—],
  ),
  caption: [São Paulo, sem bairro. Atraso e hora extra em minutos. Distância em unidades do mapa. M1 ($r=1$) e M1.a ($r=1$) geram planos ótimos rigorosamente idênticos, com M1.a sendo mais rápido em todos os tamanhos (até $5,18times$ em 10 imóveis).],
)

= Testes de estresse

Depois da escada de 3 corretores, a frota passa a crescer com os imóveis. Um erro de encaixe significa que a agenda oculta passa de 12 horas, então a tentativa seguinte mantém os imóveis e aumenta os corretores. A tabela ainda tem um único ponto. O lugar dessa execução não foi registrado.

#figure(
  table(
    columns: (2.4cm, 2.2cm, 2cm, 2.2cm, 1fr),
    table.header([Lugar], [Imóveis], [Modelo], [Corretores], [Status]),
    [não registrado], [200], [M3], [16], [não cabe no dia de trabalho mais longo],
  ),
  caption: [Primeiro ponto do teste de estresse. Semente 8, `raw = False`. O restante da sequência ainda não foi preenchido.],
)

= Análise e discussão dos resultados

M1 ($r=1$), M1.a ($r=1$) e M3 compartilham a mesma carga horária da agenda oculta: 40 imóveis ainda cabem em Moema e 50 resultam em infactibilidade provada no pré-resolvedor (presolve) do Gurobi; na cidade de São Paulo, 25 imóveis cabem e a partir de 30 imóveis (30, 40 e 50) as instâncias são provadas infactíveis no presolve em frações de segundo devido ao limite estrito de 12 horas ($J_max = 720$ min). O M2 para antes porque os turnos são rígidos e um corretor está de folga. O M1 com `fixed_ratio = 0` ($r=0$, sem nenhuma visita marcada) não falha na geração, resolvendo em Moema 5, 10 e 15 imóveis (este último em 1,2526 s) e atingindo o limite de 300 s em 20 imóveis; na cidade resolve 5 e 10 imóveis, este em 243,0094 s, e atinge o limite em 15.

== Equivalência matemática e aceleração do M1.a sob agenda fixa ($r = 1$)

A execução completa do M1.a com `fixed_ratio = 1` nos dois recortes territoriais (Moema e cidade de São Paulo) permitiu contrastar diretamente a formulação clássica de Big-M global (M1) com a reformulação MTZ fortalecida e levantada de Desrochers-Laporte (M1.a):

1. *Equivalência rigorosa de soluções*: em ambos os lugares e para todas as instâncias viáveis (5 a 40 imóveis em Moema e 5 a 25 imóveis em São Paulo), M1 e M1.a convergiram para soluções absolutamente idênticas. Distância total percorrida, atrasos, horas extras e corretores utilizados coincidiram até a última casa decimal em cada teste. Além disso, a detecção de infactibilidade pelo pré-resolvedor (`presolve`) ocorreu exatamente no mesmo patamar de corte (50 imóveis em Moema e 30 imóveis em São Paulo), sendo comprovada em frações de segundo (em menos de 0,05 s).
2. *Desempenho computacional em Moema*: com viagens curtas e alta densidade, a reformulação levantada acelerou a resolução para todas as instâncias não triviais ($N >= 10$):
  - 10 imóveis: 0,0862 s contra 0,1332 s ($1,55times$ mais rápido);
  - 15 imóveis: 0,1370 s contra 0,1960 s ($1,43times$ mais rápido);
  - 20 imóveis: 0,1981 s contra 0,4829 s ($2,44times$ mais rápido);
  - 25 imóveis: 0,3139 s contra 0,7035 s ($2,24times$ mais rápido);
  - 30 imóveis: 0,3834 s contra 0,5879 s ($1,53times$ mais rápido);
  - 40 imóveis: 0,6261 s contra 0,9731 s ($1,55times$ mais rápido).
  O M1 só superou o M1.a em 5 imóveis (0,0940 s contra 0,3375 s) pelo custo pontual de geração dos limites levantados.
3. *Desempenho computacional em São Paulo*: na escala dispersa da cidade inteira, o M1.a superou o M1 em *todos* os tamanhos viáveis, sem exceção:
  - 5 imóveis: 0,0556 s contra 0,0760 s ($1,37times$ mais rápido);
  - 10 imóveis: 0,0733 s contra 0,3797 s ($5,18times$ mais rápido);
  - 15 imóveis: 0,1281 s contra 0,2045 s ($1,60times$ mais rápido);
  - 20 imóveis: 0,1583 s contra 0,4340 s ($2,74times$ mais rápido);
  - 25 imóveis: 0,2003 s contra 0,4059 s ($2,03times$ mais rápido).
A eliminação prévia de arcos incompatíveis com as janelas de deslocamento e os coeficientes $M^k_(i j)$ apertados mostram-se decisivos tanto na malha viária local quanto na malha metropolitana.

== Confronto M1 vs. M1.a sob regimes de flexibilidade ($r = 0,5$ e $r = 0$)

A inclusão dos regimes com visitas livres (`fixed_ratio = 0,5` e `fixed_ratio = 0`) em Moema permitiu isolar diretamente a eficácia da formulação levantada de Desrochers-Laporte frente à formulação Big-M global quando o espaço combinatório de sequenciamento é ampliado:

1. *Regime de flexibilidade parcial ($r = 0,5$)*:
  - *Instâncias de 5 a 20 imóveis*: ambos os modelos convergem para planos estritamente idênticos (distância de 4,24 em 5 imóveis; 79,74 em 10; 175,83 em 15; e 174,24 em 20 imóveis), com atraso e hora extra nulos. Em 20 imóveis, o M1.a já demonstra superioridade de tempo (6,9170 s contra 8,8430 s, sendo $1,28times$ mais veloz).
  - *Ruptura de escalabilidade em 25 imóveis*: ao atingir 25 imóveis, a formulação clássica de Big-M do M1 sofre com a fraca relaxação linear decorrente da constante global única $M$, acumulando 59.229 nós na árvore de branch-and-bound e atingindo o limite de 300 segundos com gap residual de $0,0032\%$ (`maxTimeLimit`). Em contrapartida, o M1.a, amparado pelos coeficientes $M^k_(i j)$ apertados e pela eliminação de arcos incompatíveis por janelas de tempo, explorou a árvore com eficiência e alcançou a otimalidade global comprovada em 242,9612 s.

2. *Regime de flexibilidade total ($r = 0$)*:
  - *Instâncias de 5 a 15 imóveis*: ambos os modelos encontram rigorosamente o mesmo valor ótimo de objetivo (distância de 4,24 em 5 imóveis; 16,06 em 10; e 25,06 em 15 imóveis), com atraso e horas extras rigorosamente nulos. O M1.a supera o M1 em 5 imóveis (0,0985 s contra 0,1165 s), enquanto em 10 e 15 imóveis os tempos mantêm-se na mesma magnitude (0,6790 s contra 0,4749 s em 10; 1,6219 s contra 1,2526 s em 15).
  - *Limite combinatório em 20 e 25 imóveis*: com todas as janelas completamente abertas ($[0, 540]$ min), o pré-processamento de janelas do M1.a não pode podar arcos por incompatibilidade temporal ($a_i + d_i + t_(i j) > b_j$), deixando o resolvedor diante da explosão fatorial pura do sequenciamento ($20! approx 2,43 times 10^(18)$ permutações). Em 20 imóveis, o M1 atinge os 300 s com 137.580 nós e gap de $0,0035\%$, enquanto o M1.a processou 158.075 nós e reduziu o gap a apenas $0,0028\%$ (incumbent de 56.729,02 contra cota inferior de 56.727,45). Em 25 imóveis, ambos também atingiram o tempo limite de 300 s, encerrando com gaps estreitos de $0,0122\%$ no M1 (91.913 nós) e $0,0167\%$ no M1.a (117.333 nós).

Essa comparação evidencia a mecânica teórica central da reformulação: a presença de janelas temporais — mesmo que parciais ($r=0,5$) — potencializa dramaticamente o levantamento MTZ de Desrochers-Laporte, permitindo eliminar arcos inviáveis e cruzar a barreira de 25 imóveis onde o Big-M global colapsa. Quando a flexibilidade é total ($r=0$), a formulação levantada ainda oferece cortes mais justos e maior rendimento de nós, reduzindo o gap a patamares praticamente nulos.

== Comportamento dos demais modelos e regimes flexíveis

O atraso impresso do M3, nos dois lugares, é 10 minutos vezes o número de imóveis: 50, 100, 150, e assim por diante, até 400 em 40 imóveis. A resolução única minimiza $f_2$, o custo dos corretores em minutos fora dos turnos, na folga e na viagem extra de almoço. O atraso da agência não entra nesse objetivo, e a tolerância permite até 10 minutos por visita. O notebook ainda imprime atraso, hora extra e distância, porque o impressor é o das rotas abertas do M1. Esses três números não são $f_2$, e $f_2$ não foi impresso. A hora extra impressa também não é o objetivo da resolução.

A distância do M2 fica acima da do M1 no mesmo tamanho. O M2 paga a viagem até o destino de cada turno, a casa ou o ponto de almoço, e os horários marcados são outros, porque a agenda foi encaixada nos turnos. A distância do M1 não conta a volta para casa nem as pernas virtuais do almoço.

Nos modelos M1 e M1.a sob `fixed_ratio = 0` ($r=0$), a hora extra impressa é zero em todos os casos ótimos, e a distância cai substancialmente em relação à agenda rígida ($r=1$) da mesma amostra (por exemplo, 4,24 contra 84,45 em cinco imóveis de Moema, e 85,04 contra 144,91 em cinco imóveis na cidade). Sem horário marcado, os modelos ganham liberdade total para reordenar as visitas. A comparação de distância com o regime $r=1$ continua sendo desempate de planos que já empataram em tempo, não um custo em reais.

O M1.a, com pré-processamento de janelas e limites levantados de Desrochers-Laporte, supera radicalmente a degradação de tempo enfrentada pelo M1 sob flexibilidade e Big-M global. Enquanto no M1 a ausência de horários fixos impõe uma explosão combinatória que leva ao esgotamento do tempo limite de 300 s (em 20 imóveis sob $r=0$ e em 25 imóveis sob $r=0,5$ em Moema; e em 15 imóveis sob $r=0$ na capital), o M1.a sob flexibilidade ($r=0,5$) escala com consistência: resolve 5 imóveis em 0,0997 s, 10 imóveis em 0,4302 s, 15 imóveis em 0,7770 s, 20 imóveis em 6,9170 s e atinge a otimalidade global comprovada em 25 imóveis (242,9612 s), comprovando a eficácia do corte de arcos inviáveis e dos coeficientes $M^k_(i j)$ individualizados.

Reexecutar o mesmo tamanho de M1 e de M2 em Moema manteve o plano impresso e mudou só o tempo de parede. A tabela guarda o tempo da última execução.



= Suíte de testes automatizados

Além dos experimentos computacionais no catálogo real, a integridade matemática das formulações e a robustez do pipeline de dados são verificadas por uma suíte de testes unitários e de integração implementada em Python (`unittest`), localizada no diretório `tests/`.

A suíte contém 75 testes automatizados cobrindo os seguintes componentes:

1. *Infactibilidade no pré-resolvedor (presolve)*: testes em `test_hidden_schedule.py` confirmam que as restrições lineares aditivas de duração de rota e frota (`route_duration_constraint` e `fleet_duration_constraint`) adicionadas aos modelos M1, M1.a, M2 e M3 permitem ao pré-resolvedor do Gurobi detectar imediatamente instâncias cuja carga horária total de visitas excede o tempo útil disponível dos corretores, provando infactibilidade na etapa de presolve sem entrar na relaxação linear ou árvore de branch-and-bound.
2. *Agenda oculta e limites de jornada*: verificação de que a agenda oculta de referência aloca as visitas sem sobreposição e rejeita dias que extrapolam o limite máximo estrito de 12 horas ($J_max = 720$ min).
3. *Modelos M1, M1.a, M2 e M3*: testes em `test_model_1_a.py`, `test_model_2.py` e `test_model_3.py` validam a correta construção das variáveis, funções objetivo e restrições de cada formulação, a reformulação MTZ fortalecida de Desrochers-Laporte em M1.a, bem como o tratamento de visitas com horários fixos e flexíveis em M1 e M1.a (`STRICT_TIME_MODELS = ('m2', 'm3')`).
4. *Catálogo real e dados espaciais*: testes em `test_real_catalog.py` e `test_real_instances.py` garantem a consistência na leitura, filtragem e amostragem do catálogo real de aluguéis de São Paulo (6.874 anúncios) e a correta alocação dos domicílios dos corretores dentro da área delimitada pelos anúncios.
5. *Rede viária e tempos de deslocamento*: testes em `test_travel.py` e `test_travel_objective.py` validam os caminhos mínimos sobre o grafo direcionado do OpenStreetMap, o desvio em linha reta para outras cidades, os multiplicadores de congestionamento e a eliminação de arcos proibidos (mão única).
6. *Distribuição de horários de visita*: testes em `test_visit_times.py`, `test_area_visit_duration.py`, `test_auto_brokers.py` e `test_city_broker_homes.py` confirmam que os inícios das visitas seguem estatísticas de ordem uniformes sobre o tempo livre e respeitam o parâmetro `fixed_ratio`.


= Referências citadas

As referências completas, com DOI, estão em `docs/decisions/capacity.md`, `docs/decisions/travel.md` e nas páginas `docs/models/m1.md`, `m1.a.md`, `m2.md` e `m3.md`. As citadas ou pertinentes aos experimentos e testes são:

- Ballou, Rahardja e Sakai (2002), fatores de circuidade.
- Bektaş e Laporte (2011), problema de roteamento com poluição.
- Boeing (2017), OSMnx: Python for street networks.
- Boscoe, Henry e Zdeb (2012), distância de direção contra linha reta.
- Laporte, Desrochers e Nobert (1984), VRP restrito por distância e limite de jornada.
- OpenStreetMap contributors, rede viária de direção da cidade de São Paulo (outubro de 2026).
- Paraskevopoulos, Laporte, Repoussis e Tarantilis (2017), roteamento restrito por recurso.
- Taş, Dellaert, van Woensel e de Kok (2013), tempos de viagem estocásticos.
- TomTom Traffic Index 2025, relatório de tráfego e índice de congestionamento de São Paulo.
- Preço do etanol: média ANP da cidade de São Paulo, semana de 4 a 10 de outubro de 2026. Consumo: tabela PBEV do Inmetro, 14 de agosto de 2026, Volkswagen Polo 1.0 MPI, ciclo urbano, etanol.

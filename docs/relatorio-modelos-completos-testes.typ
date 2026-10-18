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
    [M1.a], [`FIXED_RATIO = 0`: nenhuma visita com horário marcado],
    [Tamanhos], [5, 10, 15, 20, 25, 30, 40 e 50 imóveis],
  ),
  caption: [Entrada compartilhada. O modo impresso pelo notebook para `raw = False` é `default`.],
)

M1, M2 e M3 ignoram `FIXED_RATIO`. Um modelo para no primeiro tamanho em que a geração falha ou a resolução atinge 300 segundos. Os tamanhos maiores daquele modelo, naquele lugar, não foram executados.

Toda resolução registrada usa `raw = False`. As linhas do M3 são uma chamada de `build_model_m3`, com os três corretores autorizados. Elas não chamam `pareto_front`. Esse auxiliar grava `raw = True` no código, então chamá-lo teria quebrado o protocolo. A frente, uma resolução por tamanho de frota, não foi executada. A célula de objetivo é o que o notebook imprime. As rotas ficam de fora.

= Tabela-resumo e alcance dos modelos

#figure(
  table(
    columns: (2.5cm, 1.5cm, 4.6cm, 1fr),
    table.header([Lugar], [Modelo], [Tamanhos com plano ótimo], [Onde a série parou]),
    [Moema], [M1], [5 a 40 imóveis], [50: inviável (presolve)],
    [Moema], [M1.a], [5, 10 e 15 imóveis], [20: limite de 300 s],
    [Moema], [M2], [5, 10 e 15 imóveis], [20: inviável (presolve)],
    [Moema], [M3], [5 a 40 imóveis], [50: inviável (presolve)],
    [São Paulo], [M1], [5 a 25 imóveis], [30: inviável (presolve)],
    [São Paulo], [M1.a], [5, 10, 15 e 20 imóveis], [25: limite de 300 s],
    [São Paulo], [M2], [5 e 10 imóveis], [15: inviável (presolve)],
    [São Paulo], [M3], [5 a 25 imóveis], [30: inviável (presolve)],
  ),
  caption: [Alcance de cada modelo com 3 corretores, semente 8 e `raw = False`. M1 e M3 param juntos por inviabilidade matemática de duração da frota no pré-resolvedor. M2 para antes, nos turnos rígidos com um corretor de folga. M1.a alcança 15 imóveis em Moema e 20 na capital com as restrições de duração de frota, parando no limite de tempo.],
)

O maior caso que cada modelo ainda resolveu, no mesmo protocolo:

#figure(
  table(
    columns: (2.3cm, 1.3cm, 1.5cm, 1.7cm, 1.6cm, 1.7cm, 1.8cm, 1fr),
    table.header([Lugar], [Modelo], [Imóveis], [Tempo (s)], [Corretores], [Atraso], [Extra], [Distância]),
    [Moema], [M1], [40], [0,9929], [3 de 3], [0], [452], [293,27],
    [Moema], [M1.a], [15], [0,4179], [3 de 3], [0], [0], [25,06],
    [Moema], [M2], [15], [0,2445], [2 de 3], [12], [—], [466,18],
    [Moema], [M3], [40], [0,9598], [3 de 3], [400], [476], [284,52],
    [São Paulo], [M1], [25], [0,2682], [3 de 3], [0], [247], [690,63],
    [São Paulo], [M1.a], [20], [0,8166], [3 de 3], [0], [0], [262,03],
    [São Paulo], [M2], [10], [0,1239], [2 de 3], [4], [—], [756,97],
    [São Paulo], [M3], [25], [0,5187], [3 de 3], [250], [276], [739,78],
  ),
  caption: [Maior instância ótima de cada série. Atraso e hora extra em minutos. Distância em unidades do mapa (4 por km). O M2 não imprime hora extra. O M3 é uma resolução, não a frente.],
)

= Resultados detalhados em Moema

Três corretores, semente 8, solver no modo `default`. Uma linha em branco no registro original aparece aqui como não executada: o modelo já tinha parado num tamanho menor. Instâncias cuja carga horária excede os limites de turno ou jornada máxima são encaminhadas ao solver, sendo comprovadas matematicamente inviáveis pelo pré-resolvedor (presolve) do Gurobi em fração de segundo (0 nós explorados).

#figure(
  table(
    columns: (1.15cm, 1.15cm, 3.5cm, 1.7cm, 1.55cm, 1.35cm, 1.35cm, 1fr),
    align: (center, center, left, right, center, right, right, right),
    table.header([Imóveis], [Modelo], [Status], [Tempo (s)], [Usados], [Atraso], [Extra], [Dist.]),
    [5], [M1], [ótimo], [0,0830], [2 de 3], [0], [40], [84,45],
    [5], [M1.a], [ótimo], [0,2264], [2 de 3], [0], [0], [4,24],
    [5], [M2], [ótimo], [0,1279], [2 de 3], [0], [—], [312,95],
    [5], [M3], [1 resolução], [0,1005], [3 de 3], [50], [60], [70,72],
    [10], [M1], [ótimo], [0,3673], [3 de 3], [0], [10], [151,60],
    [10], [M1.a], [ótimo], [0,2693], [2 de 3], [0], [0], [16,06],
    [10], [M2], [ótimo], [0,1449], [2 de 3], [5], [—], [455,22],
    [10], [M3], [1 resolução], [0,1850], [3 de 3], [100], [60], [160,23],
    [15], [M1], [ótimo], [0,2622], [3 de 3], [0], [42], [184,02],
    [15], [M1.a], [ótimo], [0,4179], [3 de 3], [0], [0], [25,06],
    [15], [M2], [ótimo], [0,2445], [2 de 3], [12], [—], [466,18],
    [15], [M3], [1 resolução], [0,2446], [3 de 3], [150], [73], [196,95],
    [20], [M1], [ótimo], [0,2952], [3 de 3], [0], [25], [191,55],
    [20], [M1.a], [limite de 300 s], [—], [—], [—], [—], [—],
    [20], [M2], [inviável (presolve)], [0,1569], [—], [—], [—], [—],
    [20], [M3], [1 resolução], [0,2473], [3 de 3], [200], [93], [208,32],
    [25], [M1], [ótimo], [0,4169], [3 de 3], [0], [57], [211,81],
    [25], [M1.a], [não executado], [—], [—], [—], [—], [—],
    [25], [M2], [não executado], [—], [—], [—], [—], [—],
    [25], [M3], [1 resolução], [0,3551], [3 de 3], [250], [137], [224,79],
    [30], [M1], [ótimo], [0,7027], [3 de 3], [8], [169], [247,67],
    [30], [M1.a], [não executado], [—], [—], [—], [—], [—],
    [30], [M2], [não executado], [—], [—], [—], [—], [—],
    [30], [M3], [1 resolução], [0,4233], [3 de 3], [300], [171], [255,43],
    [40], [M1], [ótimo], [0,9929], [3 de 3], [0], [452], [293,27],
    [40], [M1.a], [não executado], [—], [—], [—], [—], [—],
    [40], [M2], [não executado], [—], [—], [—], [—], [—],
    [40], [M3], [1 resolução], [0,9598], [3 de 3], [400], [476], [284,52],
    [50], [M1], [inviável (presolve)], [0,8118], [—], [—], [—], [—],
    [50], [M1.a], [não executado], [—], [—], [—], [—], [—],
    [50], [M2], [não executado], [—], [—], [—], [—], [—],
    [50], [M3], [inviável (presolve)], [0,9181], [—], [—], [—], [—],
  ),
  caption: [Moema. Atraso e hora extra em minutos. Distância em unidades do mapa. As instâncias que extrapolam a capacidade são resolvidas pelo presolve sem necessidade de interrupção na geração.],
)

= Resultados detalhados em São Paulo (cidade inteira)

A cidade inteira, sem bairro. A amostra é de 6.874 anúncios. O resto do protocolo é o de Moema.

#figure(
  table(
    columns: (1.15cm, 1.15cm, 3.5cm, 1.7cm, 1.55cm, 1.35cm, 1.35cm, 1fr),
    align: (center, center, left, right, center, right, right, right),
    table.header([Imóveis], [Modelo], [Status], [Tempo (s)], [Usados], [Atraso], [Extra], [Dist.]),
    [5], [M1], [ótimo], [0,0548], [2 de 3], [0], [50], [144,91],
    [5], [M1.a], [ótimo], [0,2191], [2 de 3], [0], [0], [85,04],
    [5], [M2], [ótimo], [0,0979], [2 de 3], [0], [—], [513,15],
    [5], [M3], [1 resolução], [0,1159], [2 de 3], [50], [72], [144,91],
    [10], [M1], [ótimo], [0,0956], [3 de 3], [0], [33], [242,04],
    [10], [M1.a], [ótimo], [0,2465], [2 de 3], [0], [0], [146,09],
    [10], [M2], [ótimo], [0,1239], [2 de 3], [4], [—], [756,97],
    [10], [M3], [1 resolução], [0,1282], [3 de 3], [100], [101], [258,25],
    [15], [M1], [ótimo], [0,1814], [3 de 3], [0], [45], [356,76],
    [15], [M1.a], [ótimo], [0,3960], [3 de 3], [0], [0], [154,93],
    [15], [M2], [inviável (presolve)], [0,0866], [—], [—], [—], [—],
    [15], [M3], [1 resolução], [0,2131], [3 de 3], [150], [75], [407,13],
    [20], [M1], [ótimo], [0,1740], [3 de 3], [0], [63], [697,40],
    [20], [M1.a], [ótimo], [0,8166], [3 de 3], [0], [0], [262,03],
    [20], [M2], [não executado], [—], [—], [—], [—], [—],
    [20], [M3], [1 resolução], [0,3193], [3 de 3], [200], [107], [701,27],
    [25], [M1], [ótimo], [0,2682], [3 de 3], [0], [247], [690,63],
    [25], [M1.a], [limite de 300 s], [—], [—], [—], [—], [—],
    [25], [M2], [não executado], [—], [—], [—], [—], [—],
    [25], [M3], [1 resolução], [0,5187], [3 de 3], [250], [276], [739,78],
    [30], [M1], [inviável (presolve)], [0,3524], [—], [—], [—], [—],
    [30], [M1.a], [não executado], [—], [—], [—], [—], [—],
    [30], [M2], [não executado], [—], [—], [—], [—], [—],
    [30], [M3], [inviável (presolve)], [0,3695], [—], [—], [—], [—],
    [40], [M1], [não executado], [—], [—], [—], [—], [—],
    [40], [M1.a], [não executado], [—], [—], [—], [—], [—],
    [40], [M2], [não executado], [—], [—], [—], [—], [—],
    [40], [M3], [não executado], [—], [—], [—], [—], [—],
    [50], [M1], [não executado], [—], [—], [—], [—], [—],
    [50], [M1.a], [não executado], [—], [—], [—], [—], [—],
    [50], [M2], [não executado], [—], [—], [—], [—], [—],
    [50], [M3], [não executado], [—], [—], [—], [—], [—],
  ),
  caption: [São Paulo, sem bairro. Atraso e hora extra em minutos. Distância em unidades do mapa.],
)

= Testes de estresse

Depois da escada de 3 corretores, a frota passa a crescer com os imóveis. Instâncias com carga de visitas superior à capacidade de jornada máxima permitida chegam ao resolvedor; o pré-resolvedor do Gurobi comprova a infactibilidade em poucos segundos (0 nós de branch-and-bound explorados), sem depender de interrupções heurísticas no gerador Python.

#figure(
  table(
    columns: (2.4cm, 2cm, 1.8cm, 2.2cm, 3.2cm, 1fr),
    table.header([Lugar], [Imóveis], [Modelo], [Corretores], [Status], [Tempo (s)]),
    [São Paulo], [200], [M3], [16], [inviável (presolve)], [92,83],
  ),
  caption: [Instância de estresse avaliada com a formulação completa. Semente 8, `raw = False`. O pré-resolvedor do Gurobi comprova a infactibilidade matemática (0 nós explorados) decorrente do estouro da capacidade máxima de 12 horas.],
)

= Análise e discussão dos resultados

M1 e M3 compartilham a restrição de jornada máxima ($J_max = 720$ min) e de duração de frota ($sum_i s_i <= sum_k (J_k - s_(k, "lunch"))$). Por isso, atingem a fronteira de infactibilidade no mesmo tamanho: 40 imóveis ainda são factíveis em Moema e 50 tornam-se inviáveis; na capital inteira, 25 são factíveis e 30 tornam-se inviáveis. Anteriormente, essas instâncias eram interrompidas na geração em Python; com a entrega direta ao resolvedor, o pré-resolvedor (presolve) do Gurobi detecta a impossibilidade física em fração de segundo ($< 1$ s), sem explorar nenhum nó na árvore de busca.

O modelo M2 para antes porque os turnos são rígidos (dois turnos de 4 horas por corretor ativo) e um dos três corretores está escalado em regime de folga semanal ($T_(3,1) = T_(3,2) = 0$). Isso limita a frota útil a apenas 2 corretores e 16 horas totais de trabalho, tornando inviáveis as instâncias de 20 imóveis em Moema e de 15 imóveis na capital inteira.

O modelo M1.a, sem horários marcados (`FIXED_RATIO = 0`), exibe ganho drástico de desempenho com a introdução das restrições lineares aditivas de duração de rota e frota (`route_duration_constraint` e `fleet_duration_constraint`). Antes dessas restrições, a relaxação linear atribuía $y_k approx 0$, gerando limitantes inferiores artificiais (entre 29 e 374) e gaps de $99,9%$, o que fazia o modelo atingir o tempo limite de 300 s já em 10 imóveis em Moema e demandar 243 s para 10 imóveis na capital. Com o limitante inferior estrito na soma de $y_k$, a relaxação na raiz fecha o gap quase imediatamente, permitindo resolver otimamente até 15 imóveis em Moema (em 0,42 s) e até 20 imóveis na capital (em 0,82 s).

O atraso impresso do M3, nos dois lugares, é 10 minutos vezes o número de imóveis: 50, 100, 150, e assim por diante, até 400 em 40 imóveis. A resolução única minimiza $f_2$, o custo dos corretores em minutos fora dos turnos, na folga e na viagem extra de almoço. O atraso da agência não entra nesse objetivo, e a tolerância permite até 10 minutos por visita. O notebook ainda imprime atraso, hora extra e distância, porque o impressor é o das rotas abertas do M1. Esses três números não são $f_2$, e $f_2$ não foi impresso. A hora extra impressa também não é o objetivo da resolução.

A distância do M2 fica acima da do M1 no mesmo tamanho. O M2 paga a viagem até o destino de cada turno, a casa ou o ponto de almoço, e os horários marcados são outros, porque a agenda foi encaixada nos turnos. A distância do M1 não conta a volta para casa nem as pernas virtuais do almoço.

No M1.a com nenhuma visita marcada, a hora extra impressa é zero em todos os casos ótimos, e a distância cai substancialmente em relação ao M1 da mesma amostra: 4,24 contra 84,45 em cinco imóveis de Moema, e 85,04 contra 144,91 em cinco imóveis na cidade. Sem horário marcado, o modelo tem total liberdade para reordenar a sequência de visitas de acordo com a topologia viária.

= Suíte de testes automatizados

Além dos experimentos computacionais no catálogo real, a integridade matemática das formulações e a robustez do pipeline de dados são verificadas por uma suíte de testes unitários e de integração implementada em Python (`unittest`), localizada no diretório `tests/`.

A suíte contém 78 testes automatizados cobrindo os seguintes componentes:

1. *Infactibilidade no pré-resolvedor (presolve)*: testes em `test_hidden_schedule.py` confirmam que as restrições lineares aditivas de duração de rota e frota (`route_duration_constraint` e `fleet_duration_constraint`) adicionadas aos modelos M1, M1.a, M2 e M3 permitem ao pré-resolvedor do Gurobi detectar imediatamente instâncias cuja carga horária total de visitas excede o tempo útil disponível dos corretores, provando infactibilidade na etapa de presolve sem entrar na relaxação linear ou árvore de branch-and-bound.
2. *Agenda oculta e limites de jornada*: verificação de que a agenda oculta de referência aloca as visitas sem sobreposição e rejeita dias que extrapolam o limite máximo estrito de 12 horas ($J_max = 720$ min).
3. *Modelos M1, M1.a, M2 e M3*: testes em `test_model_1_a.py`, `test_model_2.py` e `test_model_3.py` validam a correta construção das variáveis, funções objetivo e restrições de cada formulação, bem como o tratamento de visitas com horários fixos e flexíveis (`STRICT_TIME_MODELS`).
4. *Catálogo real e dados espaciais*: testes em `test_real_catalog.py` e `test_real_instances.py` garantem a consistência na leitura, filtragem e amostragem do catálogo real de aluguéis de São Paulo (6.874 anúncios) e a correta alocação dos domicílios dos corretores dentro da área delimitada pelos anúncios.
5. *Rede viária e tempos de deslocamento*: testes em `test_travel.py` e `test_travel_objective.py` validam os caminhos mínimos sobre o grafo direcionado do OpenStreetMap, o desvio em linha reta para outras cidades, os multiplicadores de congestionamento e a eliminação de arcos proibidos (mão única).
6. *Distribuição de horários de visita*: testes em `test_visit_times.py`, `test_area_visit_duration.py`, `test_auto_brokers.py` e `test_city_broker_homes.py` confirmam que os inícios das visitas seguem estatísticas de ordem uniformes sobre o tempo livre e respeitam o parâmetro `fixed_ratio`.


= Referências citadas

As referências completas, com DOI, estão em `docs/decisions/capacity.md`, `docs/decisions/travel.md` e nas páginas `docs/models/m1.md`, `m2.md` e `m3.md`. As citadas ou pertinentes aos experimentos e testes são:

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

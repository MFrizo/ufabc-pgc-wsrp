#set document(
  title: "Documentação dos modelos completos M1, M2 e M3",
  author: "UFABC — PGC — WSRP",
  date: datetime(year: 2026, month: 10, day: 18),
)
#set page(
  paper: "a4",
  margin: (x: 1.7cm, y: 1.9cm),
  footer: context {
    if counter(page).get().first() == 1 { return }
    set text(size: 8.5pt)
    [Documentação dos modelos completos M1, M2 e M3]
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
  #text(size: 20pt, weight: "bold")[Modelos completos do WSRP]
  #v(0.45cm)
  #text(size: 13pt)[M1, M2 e M3: formulação, gerador de instâncias e decisões de modelagem]
  #v(1.4cm)
  #text(size: 11pt)[18 de outubro de 2026]
  #v(1fr)
  #text(size: 9.5pt)[
    Este texto reúne as páginas dos modelos, as notas de decisão e a documentação do
    gerador de instâncias. As formulações seguem o código em `src/models/`.
    Os testes e experimentos computacionais no catálogo real estão documentados
    no relatório de testes em separado.
  ]
]

#pagebreak()
#outline(depth: 2, title: [Sumário])

= Introdução

O problema tratado neste projeto é um _Workforce Scheduling and Routing Problem_ (WSRP): a agência precisa designar corretores a visitas de imóveis e ordenar o dia de cada um. Os modelos M0.0 a M0.6 são subpassos. Cada um acrescenta um recurso, e juntos chegam ao M1, o primeiro modelo completo. O M2 olha o mesmo dia pelo lado do corretor. O M3 guarda o conjunto de planos em que melhorar um lado não piora o outro.

Este documento descreve os três modelos como estão implementados, resume o gerador de instâncias com ênfase no cálculo das distâncias do catálogo real e registra as decisões que estão em `docs/decisions/`. Os testes computacionais e experimentos de entrada compartilhada executados no Google Colab estão documentados no relatório complementar de testes (`relatorio-modelos-completos-testes.pdf`) e em `docs/experiments/complete-models.md`.

O tempo é contado em minutos a partir das 8h, de modo que 0 é 8h, 540 é 17h e 600 é 18h. A distância $c_(i j)$ está nas unidades do mapa do gerador, 4 por quilômetro: uma unidade vale 0,25 km. O mesmo mapa de $100 times 100$ unidades, cerca de 25 km de lado, serve às instâncias sintéticas e à projeção dos anúncios reais.

= M1 — ponto de vista da agência

O M1 é o MO-DOMDVRPTW-SD: roteamento de veículos aberto, com vários depósitos, janelas de tempo flexíveis e dependência de local, sob mais de um critério. O construtor é `build_model_m1`, em `src/models/model_1.py`.

Cada corretor que trabalha sai da própria casa, faz uma pausa de almoço de uma hora com início entre 11h e 14h, e encerra o dia na última visita, sem voltar para casa. Uma visita pode começar até 10 minutos antes ou depois do horário marcado, e cada minuto de atraso é penalizado. O dia pode passar das 17h como hora extra, também penalizada, e nunca dura mais de 12 horas contadas da saída de casa. O número de corretores é minimizado primeiro. Depois entra uma soma ponderada de tempo de viagem, atraso e hora extra. A distância só separa dois planos com o mesmo tempo.

O modelo otimiza o começo do dia. Rodá-lo de novo a partir da posição atual dos corretores, quando as visitas mudam, fica com quem chama o modelo. O modelo em si é estático.

A configuração padrão de instância é `num_brokers = 3`, `fixed_ratio = 1.0`, `service_time_variation = 30`, velocidade `NORMAL_SPEED`, `start_at_homes = True`, almoço $(180, 360, 60)$ e `max_day_length = 720`. A semente padrão do M1 é 8. Por padrão toda visita está marcada (`fixed_ratio = 1.0`), mas `fixed_ratio` (ou `--fixed-ratio` em `main.py`) pode assumir qualquer valor em $[0, 1]$ para repartir os imóveis entre visitas marcadas ($C_h$) e visitas flexíveis ($C_w$). M2 e M3 permanecem em `STRICT_TIME_MODELS` e marcam todas as visitas.

== Conjuntos

#figure(
  table(
    columns: (4.6cm, 2.6cm, 1fr),
    table.header([Símbolo], [Pyomo], [Definição]),
    [$K = {1, dots, m}$], [`model.K`], [Corretores],
    [$C = {1, dots, n}$], [`model.C`], [Imóveis a visitar],
    [$C_h subset.eq C$], [`model.C_h`], [Visitas marcadas (`fixed_visits`), com início $h_i$],
    [$C_w = C backslash C_h$], [`model.C_w`], [Visitas flexíveis, com janela $[e_i, l_i]$],
    [$D = {d_k : k in K}$], [`model.D`], [Casa do corretor $k$, com $d_k = n + k$],
    [$F = {f_k : k in K}$], [`model.F`], [Fim virtual do dia de $k$, com $f_k = n + m + k$],
    [$A = {a_k : k in K}$], [`model.A`], [Almoço virtual de $k$, com $a_k = n + 2m + k$],
    [$V = C union D union F union A$], [`model.V`], [Todos os nós],
    [$cal(A)$], [`model.ARCS`], [Arcos $(i, j, k)$ que o corretor $k$ pode percorrer],
  ),
  caption: [Conjuntos do M1.],
)

O nó 0, a agência, não entra nas rotas. Os arcos do corretor $k$ saem da casa dele para um imóvel ou para o almoço, de um imóvel para outro imóvel, para o almoço ou para o fim do dia, e do almoço para um imóvel ou para o fim do dia:

$
cal(A) = union.big_(k in K) (
  {(d_k, j, k) : j in C union {a_k}} \
  union {(i, j, k) : i in C, j in C union {a_k, f_k}, j != i} \
  union {(a_k, j, k) : j in C union {f_k}}
)
$

Há dois grafos, e os dois são direcionados. O grafo de ruas é a rede de direção do OpenStreetMap. Ele entra uma vez, antes do modelo, para medir o caminho mínimo de um anúncio a outro. O grafo de visitas é o que o M1, o M2 e o M3 roteiam. Os nós são as paradas da instância: cada imóvel, a casa do corretor, o almoço virtual e o fim virtual do dia. Um arco é a decisão de ir de uma parada à seguinte.

No grafo de visitas, $(i, j, k)$ e $(j, i, k)$ são arcos diferentes. A distância e o tempo que entram no objetivo e no relógio são os da direção percorrida, $c_(i j)$ e $t_(i j)$. Numa instância de São Paulo esses comprimentos são os caminhos de rua daquele sentido, então uma mão única os separa. Se não há caminho de carro de $i$ para $j$, esse arco do grafo de visitas sai: a variável fica fixa em zero, e o retorno continua se o caminho existir. Numa instância sintética não há grafo de ruas, então os dois sentidos do grafo de visitas coincidem, cada um a reta vezes o fator de desvio. A casa e o ponto de almoço são pontos sorteados, então essas pernas ficam em linha reta nos dois sentidos mesmo em São Paulo.

== Parâmetros

#figure(
  table(
    columns: (2.1cm, 3.2cm, 1fr),
    table.header([Símbolo], [Pyomo], [Definição]),
    [$c^k_(i j)$], [`model.distance`], [Distância do arco $(i, j, k)$],
    [$t^k_(i j)$], [`model.travel_time`], [Tempo de viagem do arco, no único período],
    [$s_i$], [`model.service`], [Duração no nó $i$],
    [$h_i$], [`model.scheduled`], [Início marcado da visita $i in C_h$],
    [$e_i$, $l_i$], [`earliest`, `latest`], [Janela $[e_i, l_i]$ da visita flexível $i in C_w$],
    [$tau$], [`model.tolerance`], [Tolerância de 10 minutos, antes ou depois],
    [$E_k$, $L_k$], [`shift_start`, `shift_end`], [Início e fim regular do dia: 8h e 17h],
    [$J_max$], [`model.max_day_length`], [Dia mais longo, 720 minutos],
    [$P_(i k)$], [`model.eligibility`], [1 se o corretor $k$ pode visitar o imóvel $i$],
    [$[underline(lambda), overline(lambda)]$], [`LUNCH_WINDOW`], [Janela do início do almoço, $[180, 360]$],
    [$H$], [limites de `model.w`], [Último instante de início de qualquer nó],
    [$M$], [`model.big_m`], [Constante Big-M],
    [$W_"frota"$], [`model.fleet_weight`], [Peso de cada corretor que trabalha],
    [$W_"tempo"$], [`model.travel_weight`], [Peso de cada minuto ao volante; padrão 1],
    [$W_"dist"$], [`model.distance_weight`], [Peso de desempate da distância],
    [$W_"atraso"$], [`model.delay_weight`], [Peso de cada minuto de atraso; padrão 10],
    [$W_"extra"$], [`model.overtime_weight`], [Peso de cada minuto de hora extra; padrão 100],
  ),
  caption: [Parâmetros do M1.],
)

As viagens de ida e volta dos nós virtuais não custam nada:

$
c^k_(i j) = cases(
  c_(i j) & "se os dois extremos são imóveis",
  c^"casa"_(k j) & "se o arco sai da casa de " k " para um imóvel",
  0 & "se o arco entra ou sai do almoço, ou entra no fim do dia"
)
$

$t^k_(i j)$ segue os mesmos casos com os tempos de viagem do único período. A duração é $s_i$ para $i in C$, 60 minutos no almoço e 0 em $d_k$ e em $f_k$.

Os limites e os pesos calculados a partir dos dados são

$
H = max( max_(i in C_h) (h_i + tau + s_i), thin max_(i in C_w) (l_i + s_i), thin overline(lambda) + 60, thin max_(k in K) E_k )
$
$
M = H + max_(i in V) s_i + max_((i, j, k) in cal(A)) t^k_(i j)
$
$
U = (n + m) max_((i, j, k) in cal(A)) c^k_(i j)
$
$
W_"dist" = 1 / (U + 1)
$

salvo quando `distance_weight` é informado. $U$ limita a distância de qualquer plano: no máximo uma viagem paga por imóvel e por casa. Com esse peso, a distância inteira de um plano vale menos que um minuto de direção, e por isso só separa planos com o mesmo tempo de viagem, o mesmo atraso e a mesma hora extra.

$
W_"frota" = (n + m) (max_((i, j, k) in cal(A)) t^k_(i j)) W_"tempo" + U W_"dist"
$
$
+ |C_h| tau W_"atraso" + (sum_(k in K) max(0, H - L_k)) W_"extra" + 1
$

Esse peso é maior que tempo de viagem, distância, atraso e hora extra de qualquer plano somados. Um corretor a menos vem sempre primeiro.

== Variáveis de decisão

#figure(
  table(
    columns: (1.5cm, 2.8cm, 3.4cm, 1fr),
    table.header([Símbolo], [Pyomo], [Domínio], [Significado]),
    [$x_(i j k)$], [`model.x`], [${0, 1}$], [1 se $k$ vai direto de $i$ a $j$],
    [$y_k$], [`model.y`], [${0, 1}$], [1 se $k$ trabalha no dia],
    [$w_i$], [`model.w`], [$[0, H]$], [Início no nó $i$],
    [$delta_i$], [`model.delay`], [$RR_(>= 0)$], [Minutos de atraso da visita $i$ ($0$ para $i in C_w$)],
    [$o_k$], [`model.overtime`], [$RR_(>= 0)$], [Minutos de hora extra do corretor $k$],
  ),
  caption: [Variáveis do M1. $w_(d_k)$ é a saída de casa e $w_(f_k)$ é o fim do dia.],
)

== Função objetivo

Minimizar primeiro os corretores que trabalham, depois tempo de viagem, atraso e hora extra, com a distância como desempate:

$
min thin W_"frota" sum_(k in K) y_k
+ W_"tempo" sum_((i, j, k) in cal(A)) t^k_(i j) thin x_(i j k)
+ W_"dist" sum_((i, j, k) in cal(A)) c^k_(i j) thin x_(i j k)
+ W_"atraso" sum_(i in C_h) delta_i
+ W_"extra" sum_(k in K) o_k
$

== Restrições

As somas em $j$ ou em $i$ percorrem só os arcos de $cal(A)$.

* (1) Atendimento único.* Cada imóvel é deixado exatamente uma vez, por exatamente um corretor:

$ sum_(k in K) sum_(j : (i, j, k) in cal(A)) x_(i j k) = 1 quad forall i in C $

* (2) Compatibilidade.* O corretor só atende um imóvel que lhe esteja permitido:

$ sum_(j : (i, j, k) in cal(A)) x_(i j k) <= P_(i k) quad forall i in C, k in K $

* (3) Saída de casa.* Quem trabalha sai de casa uma vez:

$ sum_(j : (d_k, j, k) in cal(A)) x_(d_k j k) = y_k quad forall k in K $

* (4) Fim do dia.* Quem trabalha encerra o dia uma vez:

$ sum_(i : (i, f_k, k) in cal(A)) x_(i f_k k) = y_k quad forall k in K $

* (5) Conservação de fluxo.* O corretor deixa todo imóvel, e o próprio almoço, em que entra:

$ sum_(i : (i, h, k) in cal(A)) x_(i h k) - sum_(j : (h, j, k) in cal(A)) x_(h j k) = 0 quad forall k in K, h in C union {a_k} $

* (6) Fluxo de tempo.*

$ w_i + s_i + t^k_(i j) - M (1 - x_(i j k)) <= w_j quad forall (i, j, k) in cal(A) $

* (7a) Janelas brandas das visitas marcadas.* A visita marcada começa no máximo $tau$ minutos antes ou depois do horário marcado, e os minutos depois desse horário são o atraso:

$ w_i >= h_i - tau, quad w_i <= h_i + delta_i, quad delta_i <= tau quad forall i in C_h $

* (7b) Janelas das visitas flexíveis.* A visita flexível começa em qualquer instante de sua janela no dia e não tem atraso:

$ e_i <= w_i <= l_i, quad delta_i = 0 quad forall i in C_w $

* (8) Jornada.* O corretor não sai de casa antes do início do dia. O que passar do fim regular é hora extra. O dia inteiro não passa do limite legal, tanto no relógio quanto na soma de serviços e viagens da rota e da frota:

$ w_(d_k) >= E_k, quad w_(f_k) <= L_k + o_k, quad w_(f_k) - w_(d_k) <= J_max quad forall k in K $

$ sum_((i, j) : (i, j, k) in cal(A)) (s_i + t^k_(i j)) thin x_(i j k) <= J_max thin y_k quad forall k in K $

$ sum_(i in C) s_i + sum_((i, j, k) in cal(A)) t^k_(i j) thin x_(i j k) <= sum_(k in K) (J_max - s_(a_k)) thin y_k $

* (9) Almoço.* Quem trabalha passa pelo nó de almoço, e o início fica dentro da janela:

$ sum_(i : (i, a_k, k) in cal(A)) x_(i a_k k) = y_k, quad underline(lambda) <= w_(a_k) <= overline(lambda) quad forall k in K $

== Observações que mudam a leitura do plano

As rotas são abertas. O dia termina no fim da última visita, ou do almoço se ele for o último. $f_k$ é virtual, então a volta para casa não entra no tempo nem na distância.

O almoço também é um nó virtual. Os arcos que entram e saem de $a_k$ têm distância zero e tempo zero. A viagem do último imóvel antes do almoço até o primeiro depois dele, portanto, não é cronometrada nem contada. Se o almoço é a primeira parada, a viagem de casa até a primeira visita também fica livre. A agenda oculta do gerador, ao contrário, conta a viagem depois do almoço a partir do último imóvel anterior.

A parcela de visitas marcadas ($C_h$) vem de `fixed_ratio` (padrão `1.0`, configurável por `--fixed-ratio`). Para $i in C_h$, os dois extremos da janela do gerador coincidem em $h_i$, e começar até $tau$ minutos adiantado não custa nada; para $i in C_w$, a visita pode começar em qualquer instante de $[e_i, l_i]$ sem atraso. A hora extra é branda depois das 17h e rígida em 12 horas a partir da saída de casa. Um corretor com $y_k = 0$ não usa arcos; os horários da casa, do fim do dia e do almoço dele continuam existindo e continuam satisfazendo a jornada e a janela de almoço.

Os pesos de tempo, atraso e hora extra multiplicam minutos. O peso da distância multiplica unidades do mapa e fica abaixo de um minuto de direção em qualquer plano viável. Um preço em reais por quilômetro é o objetivo do M2. O M1 permanece em minutos, num único período de tempo de viagem. Os horários de pico ficam nos modelos M0.5 e M0.6.

== M1.a, reformulação sem Big-M global

O M1.a (`build_model_m1_a`, em `src/models/model_1_a.py`) mantém exatamente o conjunto viável e o objetivo do M1 para qualquer `fixed_ratio`, mas substitui a constante global $M$ da restrição (6) por três fortalecimentos da relaxação linear:

1. *Pré-processamento das janelas $[a_i, b_i]$ (redução de domínio)* por propagação iterativa de alcançabilidade para frente e para trás até convergir:

$ a_j <- max(a_j, min_((i, j, k) in cal(A)_"ativo") (a_i + s_i + t^k_(i j))), quad b_i <- min(b_i, max_((i, j, k) in cal(A)_"ativo") (b_j - s_i - t^k_(i j))) $

Todo arco com $a_i + s_i + t^k_(i j) > b_j$ é fixado em $x_(i j k) = 0$.

2. *Coeficientes $M^k_(i j)$ por arco e agregação entre corretores:*

$ M^k_(i j) = max(0, b_i + s_i + t^k_(i j) - a_j) $

Para pares de imóveis $(i, j) in C times C$ ($i != j$), como no máximo um corretor percorre $(i, j)$, as $|K|$ linhas por corretor são substituídas por uma única desigualdade agregada:

$ w_i - w_j + sum_(k in K) M^k_(i j) thin x_(i j k) <= b_i - a_j quad forall i, j in C, i != j $

3. *Limites de janela levantados de Desrochers e Laporte (1991) e eliminação de 2-ciclos:*

$ w_i >= a_i + sum_((j, i, k) in cal(A)) max(0, a_j + s_j + t^k_(j i) - a_i) thin x_(j i k) quad forall i in C union A $

$ w_i <= b_i - sum_((i, j, k) in cal(A)) max(0, b_i - (b_j - s_i - t^k_(i j))) thin x_(i j k) quad forall i in C union A $

$ sum_(k in K) (x_(i j k) + x_(j i k)) <= 1 quad forall i, j in C, i < j $

O termo reverso $(b_i - a_j - s_j - t^k_(j i)) thin x_(j i k)$ da equação (11) de Desrochers e Laporte (1991) não é somado diretamente em $w_i - w_j <= b_i - a_j$: como demonstraram Yuan, Cattaruzza, Ogier e Semet (2020), quando $x_(j i k) = 1$ esse coeficiente força $w_i <= w_j + s_j + t^k_(j i)$, proibindo espera no nó $i$.

= M2 — ponto de vista do corretor

O M2 é o HC-DOMDVRPTW-SD: a mesma família de roteamento do M1, com a jornada do corretor no centro do modelo. O construtor é `build_model_m2`, em `src/models/model_2.py`.

Cada corretor que trabalha tem o próprio turno da manhã, da casa até o lugar que escolheu para o almoço, e o próprio turno da tarde, desse lugar de volta para casa. Nenhuma visita pode terminar depois do fim do seu turno. O corretor de folga não trabalha. As visitas podem começar até 10 minutos antes ou depois. O objetivo é o combustível que os corretores pagam. O corretor é pago quando um negócio se fecha, então um minuto do tempo dele não tem preço. O atraso e o maior tempo em que um corretor que trabalha fica fora só separam planos com o mesmo combustível. O combustível inclui a viagem da última visita de cada turno até o destino desse turno.

Como no M1, o modelo otimiza o começo do dia. A configuração traz `num_brokers = 3`, `fixed_ratio = 1.0`, `service_time_variation = 30`, `NORMAL_SPEED`, `days_off = 1` e `split_shifts = True`. Toda visita está marcada.

== Conjuntos

Cada turno de um corretor que trabalha é uma rota $r$. O turno da manhã, rótulo A, vai da casa até o ponto de almoço. O turno da tarde, rótulo B, vai do ponto de almoço de volta para casa. Os turnos se nomeiam pelo corretor e pelo rótulo, por exemplo `1A` e `1B`. Um corretor de folga não tem turnos.

#figure(
  table(
    columns: (2.4cm, 2.6cm, 1fr),
    table.header([Símbolo], [Pyomo], [Definição]),
    [$K = {1, dots, m}$], [`model.K`], [Corretores],
    [$R$], [`model.R`], [Turnos, dois por corretor que trabalha],
    [$C = {1, dots, n}$], [`model.C`], [Imóveis a visitar],
    [$D = {d_r}$], [`model.D`], [Origem do turno $r$, $d_r = n + r$],
    [$F = {f_r}$], [`model.F`], [Fim virtual do turno, $f_r = n + |R| + r$],
    [$V = C union D union F$], [`model.V`], [Todos os nós],
    [$cal(A)$], [`model.ARCS`], [Arcos $(i, j, r)$ do turno $r$],
  ),
  caption: [Conjuntos do M2.],
)

A agência, de novo, não é usada. Um turno sai da origem para um imóvel, de um imóvel para outro, e de um imóvel para o fim do turno:

$
cal(A) = union.big_(r in R) (
  {(d_r, j, r) : j in C} \
  union {(i, j, r) : i in C, j in C union {f_r}, j != i}
)
$

== Parâmetros

#figure(
  table(
    columns: (2.2cm, 3.4cm, 1fr),
    table.header([Símbolo], [Pyomo], [Definição]),
    [$kappa(r)$], [`model.route_broker`], [Corretor do turno $r$],
    [$c^r_(i j)$], [`model.distance`], [Distância do arco $(i, j, r)$],
    [$t^r_(i j)$], [`model.travel_time`], [Tempo de viagem do arco],
    [$s_i$], [`model.service`], [Duração no nó $i$; 0 na origem e no fim],
    [$h_i$], [`model.scheduled`], [Início marcado da visita],
    [$tau$], [`model.tolerance`], [Tolerância de 10 minutos],
    [$E_r$, $L_r$], [`model.shift_start`, `shift_end`], [Início e fim rígido do turno $r$],
    [$P_(i r)$], [`model.eligibility`], [1 se o corretor do turno pode visitar $i$],
    [$alpha$], [`model.fuel_cost`], [Reais por unidade do mapa],
    [$W_"atraso"$], [`model.delay_weight`], [Peso de desempate do atraso],
    [$W_"justo"$], [`model.fairness_weight`], [Peso de desempate da maior jornada],
  ),
  caption: [Parâmetros do M2.],
)

Com $"orig"_r$ e $"dest"_r$ a origem e o destino do turno (a casa ou o ponto de almoço do corretor $kappa(r)$), a viagem até o fim do turno é a viagem até o destino:

$
c^r_(i j) = cases(
  c_(i j) & "se os dois extremos são imóveis",
  c_("orig"_r)_(j) & "se o arco sai da origem do turno para um imóvel",
  c_("dest"_r)_(i) & "se o arco vai de um imóvel ao fim do turno"
)
$

$P_(i r) = 1$ quando o imóvel $i$ não tem corretor marcado ou o corretor marcado é $kappa(r)$.

O gerador sorteia os turnos em `MORNING_SHIFT` e `AFTERNOON_SHIFT`. A manhã começa entre 8h e 9h e termina entre 11h30 e 12h30. A tarde começa entre 13h e 14h e termina entre 17h e 18h. O intervalo entre os dois é o almoço.

Na ausência de um preço informado,

$ alpha = 3,91 / (9,3 times 4) $

reais por unidade do mapa. O numerador é o preço médio do etanol na cidade de São Paulo na semana de 4 a 10 de outubro de 2026, R\$ 3,91 por litro em 209 postos (ANP). A média do estado naquela semana foi R\$ 3,86, e o modelo usa a da cidade. O 9,3 km/L é o consumo urbano no etanol do Volkswagen Polo 1.0 MPI, tabela PBEV do Inmetro de 14 de agosto de 2026. O fator 4 converte quilômetros em unidades do mapa. O etanol estava mais barato por quilômetro que a gasolina naquela semana: a gasolina custava R\$ 6,34/L e o mesmo carro faz 13,5 km/L nela, e $3,91 / 6,34$ fica abaixo de $9,3 / 13,5$. O Polo foi o automóvel de passageiros mais vendido no ranking Fenabrave de setembro de 2026. A líder geral, a Fiat Strada, é uma picape.

Um custo completo $alpha c_(i j) + beta t_(i j)$, como no problema de roteamento com poluição (Bektaş e Laporte, 2011), também pediria um salário em reais por minuto. A comissão de um negócio fechado não fornece esse salário, então não há $beta$.

Sem pesos informados, cada minuto de atraso e cada minuto do dia mais longo, juntos, valem menos que o combustível de 0,01 unidade do mapa. $W_"justo" = 0$ desliga o termo de justiça.

== Variáveis e objetivo

Além dos arcos $x_(i j r)$ e dos inícios $w_i$, o M2 tem o atraso $delta_i$, a duração $sigma_r$ em que o corretor fica fora no turno $r$ (da saída de $d_r$ até a chegada em $f_r$), a carga $omega_k$ do corretor (soma das durações dos turnos dele; a folga vale 0) e $Omega$, a maior carga entre os corretores que trabalham.

$
min thin alpha sum_((i, j, r) in cal(A)) c^r_(i j) thin x_(i j r)
+ W_"atraso" sum_(i in C) delta_i
+ W_"justo" thin Omega
$

== Restrições

* (1) Atendimento único.* Cada imóvel é deixado exatamente uma vez, em exatamente um turno.

* (2) Compatibilidade.* O turno só atende um imóvel permitido ao seu corretor.

* (3) Saída da origem.* Cada turno sai da origem no máximo uma vez.

* (4) Fim do turno.* Um turno que sai da origem termina no destino.

* (5) Conservação de fluxo* em cada imóvel e em cada turno.

* (6) Fluxo de tempo,* com Big-M, como no M1.

* (7) Janelas flexíveis,* as mesmas do M1: no máximo $tau$ minutos antes, atraso limitado por $tau$.

* (8) Limites rígidos do turno.* O turno não sai da origem antes de $E_r$, e a última visita termina até $L_r$, tanto no relógio quanto na soma de serviços e viagens até imóveis:

$
w_(d_r) >= E_r quad forall r in R
$
$
w_i + s_i - M (1 - x_(i f_r r)) <= L_r quad forall i in C, r in R
$
$
sum_((i, j) : (i, j, r) in cal(A)) s_i thin x_(i j r) + sum_((i, j) : (i, j, r) in cal(A), j in C) t^r_(i j) thin x_(i j r) <= L_r - E_r quad forall r in R
$
$
sum_(i in C) s_i + sum_((i, j, r) in cal(A), j in C) t^r_(i j) thin x_(i j r) <= sum_(r in R) (L_r - E_r)
$

A restrição (8) vale para o fim da última visita. A viagem até o destino entra na distância e em $w_(f_r)$, e pode terminar depois de $L_r$.

* (9) Duração do turno.* O tempo fora num turno que de fato sai; um turno que permanece na origem não contribui:

$
sigma_r >= w_(f_r) - w_(d_r) - M (1 - sum_(j in C) x_(d_r j r)) quad forall r in R
$

* (10) Carga de trabalho.* $omega_k$ é a soma das durações dos turnos de $k$, ou zero na folga.

* (11) Maior carga.* $Omega >= omega_k$ só para corretores que têm turnos. A folga não entra, então o zero dela não puxa os outros para baixo.

== Observações

Os corretores entram nas rotas só pelos turnos. Quem está de folga não tem turno e não faz visita. $K$ serve à carga de trabalho, não às rotas.

O almoço é o vão entre os dois turnos e não tem duração própria. Nada liga a chegada da manhã ao ponto de almoço com a saída da tarde desse ponto. A saída da tarde só respeita $E_r$.

Não há minimização de frota, hora extra nem limite rígido de 12 horas. Os turnos são o único limite rígido do dia. A carga é o tempo em que o corretor está fora, não o número de visitas. Ela inclui viagem, visitas, espera entre visitas e a viagem até o destino. O vão do almoço fica de fora. Um turno sem visitas contribui 0.

A justiça é a medida min-max de Matl, Hartl e Vidal (2018): $Omega$ é o maior tempo em que um corretor que trabalha fica fora. Com os pesos padrão ela só separa planos de mesmo combustível, porque um minuto desse dia não tem preço. Ela não eleva de propósito o dia mais leve.

= M3 — frente entre a agência e os corretores

O construtor é `build_model_m3` e a frente é `pareto_front`, ambos em `src/models/model_3.py`. A instância é a do M1 mais `days_off = 1`. Toda visita está marcada.

M1 e M2 não compartilham o conjunto viável, então um par das soluções deles não é uma frente de Pareto. Uma rota legal num modelo pode ser ilegal no outro. O M3 guarda as regras de que nenhum dos lados abre mão e transforma em objetivo as preferências de cada lado.

As regras que permanecem como restrições são as do M1: cada visita atendida uma vez, uma visita já designada feita pelo seu corretor, as janelas flexíveis, o dia de 12 horas e a pausa de almoço. O objetivo da agência é o do M1. O objetivo dos corretores são as regras do M2 que o M1 não impõe: minutos da rota fora dos turnos do próprio corretor, um dia trabalhado na folga, e a viagem extra até o ponto de almoço que ele escolheu.

`main.py --model m3` não devolve um plano. Devolve a frente. Os experimentos computacionais registrados no relatório de testes não chamaram `pareto_front`. Chamaram `build_model_m3` uma vez, com os três corretores autorizados a trabalhar.

== Dados que o M1 não lê

Os conjuntos, as distâncias e os tempos de viagem são os do M1. Duas listas vêm do gerador e o M1 não as lê: quem tem turno e quem está de folga (`shifts`), e o início e o fim de cada turno do corretor. O parâmetro `fleet_cap` é o máximo de corretores que podem trabalhar naquela resolução. Uma resolução da frente usa cada valor de 1 até $|K|$. Sem o argumento, todos podem trabalhar.

Às variáveis do M1 o M3 acrescenta $o_(k s)$, os minutos da rota de $k$ que caem dentro do turno $s$; $u_k$, os minutos dessa rota fora de todos os turnos dele; e $z_(i j k)$, que vale 1 quando o almoço de $k$ fica entre os nós $i$ e $j$.

== Objetivos

O objetivo da agência, $f_1$, é o do M1: corretores que trabalham, depois tempo de viagem, atraso e hora extra. Ele não é minimizado dentro de uma resolução. É lido de cada plano resolvido, e o número de corretores é o que a frente restringe.

O objetivo dos corretores, $f_2$, em minutos, é

$
f_2 = sum_(k in K_"trabalha") u_k
+ J_max sum_(k in K_"folga") y_k
+ sum_((i, j, k)) (max(0, ell_(i j k)) / v) thin z_(i j k)
$

$J_max = 720$, então um corretor que trabalha na folga custa tanto quanto ficar fora o dia inteiro. $ell_(i j k)$ é a distância extra de ir de $i$ ao ponto de almoço dele e seguir para $j$, em vez de ir de $i$ a $j$. A velocidade $v = 2$ unidades do mapa por minuto é a do M1. O fim virtual do dia não tem viagem adiante, então a distância extra é só a ida ao ponto. O termo são esses minutos extras, não a distância crua até o ponto.

A conta de combustível do M2 é outro objetivo. O M2 precifica quilômetros, e nele os turnos são restrições rígidas. No M3 os turnos, a folga e o ponto de almoço escolhido são as regras do M2 que o M1 deixa livres, então o M3 as pontua em minutos. Uma visita entre o turno da manhã e o da tarde cai fora dos dois. Contar só um início antes do primeiro turno e um fim depois do último trataria essa visita como coberta. $o_(k s)$ é a interseção da rota com o turno $s$, e $u_k$ é o resto da rota.

Uma resolução minimiza $f_2$. Um desempate no tempo de viagem é menor que um minuto de $f_2$, então nunca compra um minuto fora de um turno.

== A frente

O número de corretores toma poucos valores inteiros, então um MILP por tamanho de frota é o método da $epsilon$-restrição (Mavrotas, 2009):

$ min f_2 quad "sujeito a" quad sum_(k in K) y_k <= m, quad m = 1, dots, |K| $

Um tamanho em que as visitas não cabem é pulado. Um plano é descartado quando outro usa no máximo os mesmos corretores e custa no máximo o mesmo aos corretores, e é estritamente melhor num dos dois. O que resta é a frente, ordenada pelo número de corretores. Ela pode ser um único plano quando a instância não força uma troca. Isso é um resultado, não um ponto que faltou.

Uma soma ponderada de $f_1$ e $f_2$ não é usada. Numa frente inteira ela só encontra o casco convexo (Mavrotas, 2009). AUGMECON é a forma usual da $epsilon$-restrição. O método da caixa balanceada é uma alternativa exata para dois objetivos (Boland, Charkhgard e Savelsbergh, 2015). Levantamentos de roteamento multiobjetivo, e a frente aplicada mais próxima, são Jozefowiez, Semet e Talbi (2008) e Braekers, Hartl, Parragh e Tricoire (2016). O artigo de cuidado domiciliar é o modelo do capítulo: uma frente entre o custo operacional e o incômodo de quem é atendido. Cada uma dessas resoluções é tão difícil quanto o M1. O `setObjectiveN` do Gurobi devolve um ponto lexicográfico ou misturado por execução, não a frente.

== Restrições acrescentadas

As restrições (1) a (9) do M1 permanecem.

* (10) No máximo $m$ corretores:* $sum_(k in K) y_k <= m$.

* (11) Interseção com um turno.* Para um corretor que trabalha, $o_(k s)$ é o comprimento da interseção da rota $[w_(d_k), w_(f_k)]$ com o turno $[E_(k s), L_(k s)]$, e $u_k$ é a parte da rota que sobra:

$
u_k >= w_(f_k) - w_(d_k) - sum_s o_(k s) - M (1 - y_k) quad forall k in K_"trabalha"
$

* (12) Onde o almoço fica.*

$
sum_(i, j) z_(i j k) = y_k, quad
sum_j z_(i j k) = x_(i, a_k, k), quad
sum_i z_(i j k) = x_(a_k, j, k)
$

A menor frota é o lado da agência neste modelo: menos corretores, com tempo de viagem, atraso e hora extra do M1 lidos do plano. Uma frota maior permanece na frente só quando reduz $f_2$. Nenhum dos extremos precisa coincidir com a solução do M1 ou com a do M2. A viagem do almoço continua livre no relógio, como no M1, e é paga em $f_2$.

Escolher um plano é outra decisão. A frente é o conjunto de trocas. Três escolhas usuais são o ponto de compromisso (o mais próximo do ponto ideal, depois de normalizar), o joelho (onde uma perda pequena de um lado deixa de comprar muito do outro) e a barganha de Nash (o produto do ganho de cada lado sobre o seu pior resultado). O M3 devolve a frente e não escolhe.

= Gerador de instâncias

Os três modelos leem a mesma função, `generate_wsrp_instance`, em `src/core/data_generator.py`. Uma chamada monta a instância inteira. Cada modelo usa só as chaves de que precisa. Cada recurso sorteia no próprio fluxo, derivado da semente: o grafo usa a semente pura, e janelas, designações, durações, casas, pontos de almoço, turnos e frota automática usam `default_rng([semente, fluxo])`. Acrescentar um recurso não desloca os números dos anteriores.

Uma instância real não sorteia os imóveis nesse mapa. `instance_from_catalog`, em `src/core/listings.py`, filtra o catálogo `data/real.csv` pela cidade e, se houver, pelo bairro, e `sample_listings` tira `num_properties` linhas com `default_rng(semente)`, sem reposição. A mesma semente e o mesmo lugar devolvem os mesmos imóveis, na ordem do sorteio. Por isso M1, M1.a, M2 e M3, com a mesma semente, a mesma cidade e o mesmo número de imóveis, visitam as mesmas casas. O que muda é a agenda e, no M2, o encaixe nos turnos.

== O que cada modelo pede ao gerador

#figure(
  table(
    columns: (2.2cm, 1fr, 1fr, 1fr),
    table.header([Ajuste], [M1], [M2], [M3]),
    [Corretores], [3], [3, um de folga], [3, um de folga nos dados de turno],
    [Visitas marcadas], [todas], [todas], [todas],
    [Duração da visita], [pela área, de 30 a 90 min], [idem], [idem],
    [Velocidade], [2 unidades/min], [2 unidades/min], [2 unidades/min],
    [Saída], [da própria casa], [da casa na manhã e do almoço na tarde], [da própria casa],
    [Almoço], [pausa de 60 min, início em [180, 360]], [vão entre os turnos], [a pausa do M1],
    [Limite do dia], [720 min], [fim rígido de cada turno], [720 min],
  ),
  caption: [Ajustes de `INSTANCE_SETTINGS` que os experimentos usaram, além do padrão do gerador.],
)

O padrão que esses ajustes não cobrem continua valendo. O horizonte alvo é 600 minutos. A parcela de visitas já designadas a um corretor é 0,4: esses imóveis ficam com o corretor que os atende na agenda oculta, o que preserva a factibilidade; os demais podem ser feitos por qualquer corretor. Os experimentos não alteraram essa parcela.

A duração de uma visita real não é sorteada. Ela cresce em linha com a área útil, de 30 minutos em 0 m² até 90 minutos em 1.000 m², e permanece em 90 para áreas maiores. O teto de 1.000 m² é a maior área que o catálogo limpo conserva.

== Agenda oculta

As janelas nascem de uma agenda de referência que deixa a instância factível quando a carga horária cabe na jornada dos corretores. Uma permutação dos imóveis é repartida entre os corretores que trabalham. Dentro do tempo livre de cada um, o início de cada visita segue uma uniforme contínua, com folgas ociosas espalhadas entre as visitas.

No M1 e no M3 a agenda não recebe os turnos. O dia de cada corretor é partido ao meio para o almoço: a primeira metade vai antes da pausa, ou menos visitas se elas não terminam até o início mais tarde do almoço (14h), e o resto vai depois. O horizonte é estendido até caber o corretor mais carregado. No M2 a agenda recebe os turnos: a manhã é feita a partir de casa e a tarde a partir do ponto de almoço, alocando as visitas que cabem nos turnos de cada corretor ativo (com um dos três corretores em regime de folga).

No comportamento original do gerador, quando as visitas extrapolavam o limite de 720 minutos ou não cabiam nos turnos dos corretores, a rotina interrompia preventivamente a execução disparando um erro em Python (`ValueError`). Com a implementação das restrições lineares aditivas de duração de rota e frota e o fortalecimento das restrições de fluxo temporal MTZ, o gerador passou a adotar `raise_on_fit_failure = false` por padrão. Sob essa configuração, instâncias sobrecarregadas recebem o sinalizador `schedule_overflow = true`, emitem aviso informativo em log e chegam diretamente ao modelo matemático; o pré-resolvedor (presolve) do Gurobi detecta e comprova a impossibilidade matemática em fração de segundo (0 nós explorados), eliminando a necessidade de filtros manuais na geração.

No caso do dimensionamento automático de frota (`--brokers auto`), a busca em `_auto_fleet_instance` inspeciona explicitamente a flag `schedule_overflow` e a duração máxima do dia para cada tamanho candidato, garantindo que o menor número de corretores viável (`schedule_brokers`) seja incrementado até que toda a carga de visitas caiba de forma factível, antes de sortear o tamanho final da frota.

Depois da agenda, a parcela `fixed_ratio` das visitas fica com início fixo igual ao da referência. As outras podem começar em qualquer instante que ainda as termine dentro do horizonte. M2 e M3 forçam a parcela em 1 (`STRICT_TIME_MODELS`). M1 e M1.a aceitam qualquer `fixed_ratio` em $[0, 1]$, com padrão 1,0 em `INSTANCE_SETTINGS`. A agenda do M1 e a do M1.a coincidem quando a mesma parcela é usada: o que muda entre os dois é apenas a formulação matemática de propagação de tempo e eliminação de subciclos.

== Distâncias na instância real de São Paulo

A decisão e a medição estão em `docs/decisions/travel.md`. O código é `src/core/travel.py` e a montagem do grafo é `_house_graph`.

Uma instância de São Paulo usa distância de rede viária e duração em fluxo livre, as duas como caminhos mínimos no grafo de direção do OpenStreetMap. A rede foi baixada com OSMnx 2.1.1 em 10 de outubro de 2026 (Boeing, 2017). Os dados do mapa são de OpenStreetMap contributors. O índice comprometido no repositório é o retrato dessa data: `data/travel/sao_paulo.json`, com a matriz em `data/travel/sao_paulo.npz`. Reconstruir o índice pode mudar os números. A semente da instância não muda.

O índice guarda toda coordenada distinta de anúncio em São Paulo, arredondada a seis casas decimais, cerca de 0,1 m. São 6.874 anúncios e 3.354 coordenadas. Moema tem 619 anúncios. Qualquer amostra da cidade usa o índice quando cada imóvel é uma dessas coordenadas, com ou sem bairro. Uma cidade que não seja São Paulo não está no índice e permanece na distância em linha reta.

Cada anúncio e a agência são presos ao nó do grafo mais próximo. Um encaixe além de 400 m é recusado. A distância é o comprimento do caminho mínimo, em metros. A duração é o caminho mínimo sob o tempo de fluxo livre, em segundos. Os dois pesos podem escolher caminhos diferentes. O grafo de ruas é direcionado, e o grafo de visitas também, como na formulação do M1. Cada sentido entre duas paradas é um arco, com a distância e o tempo daquele caminho de rua. Uma rua de mão única faz $(i, j)$ diferir de $(j, i)$, e as duas direções ficam guardadas.

Os metros viram unidades do mapa, 4 por quilômetro, arredondadas a duas casas, para a distância de rua sentar no mesmo mapa $100 times 100$ de uma instância sintética. Os segundos viram minutos, arredondados a quatro casas. A projeção que posiciona os nós é equirretangular, centrada no centroide dos imóveis da amostra, com 110,574 km por grau de latitude e 111,320 km por grau de longitude. A agência, nó 0, fica nesse centroide, no ponto $(50, 50)$ do mapa. M1, M2 e M3 não roteiam a partir dela.

13.406 pares direcionados não têm caminho de carro. Eles não são arcos: a matriz guarda 0 e o modelo fixa a variável do arco em zero, sem distância substituta. Esses pares saem de quatro anúncios. O maior componente fortemente conexo tem 191.489 dos 191.955 cruzamentos. Três anúncios caem num bolsão de 15 cruzamentos a oeste da cidade cujas ruas de mão única não levam de volta para fora. O quarto cai num cruzamento sem aresta de saída. O resto da cidade ainda entra. Nada sai. Uma rota aberta pode terminar nessa casa. Uma rota que precise deixá-la não tem arco viável.

O grafo cobre a caixa envolvente de todos os anúncios de São Paulo, com uma folga de 0,03 grau.

== Tempo de viagem que o MILP lê

O tempo que o solver vê é um número inteiro de minutos, calculado antes do modelo. M1, M1.a, M2 e M3 têm um período só, `NORMAL_SPEED`, 2 unidades do mapa por minuto, cerca de 30 km/h. Esse período é o do meio do dia.

Quando a matriz de duração em fluxo livre existe, cada minuto livre é multiplicado pelo fator de congestionamento do período e arredondado para cima. Duração zero permanece zero. O fator do período único é o do meio do dia, 1,796. Ele vem do TomTom Traffic Index 2025 para o centro de São Paulo, a série horária do centro e não a metropolitana. O nível de congestionamento do TomTom é o tempo extra em relação ao fluxo livre, então o multiplicador é $1 + c / 100$. O número do período é a média de segunda a sexta das horas daquele período, arredondada a uma casa antes de formar o multiplicador.

#figure(
  table(
    columns: (3.2cm, 3.6cm, 3.4cm, 2.4cm),
    table.header([Partida], [Horas na média], [Congestionamento], [Fator]),
    [8h–10h], [8 e 9], [85,91% para 85,9%], [1,859],
    [10h–17h], [10 a 16], [79,59% para 79,6%], [1,796],
    [a partir das 17h], [17 e 18], [100,52% para 100,5%], [2,005],
  ),
  caption: [Fatores de congestionamento de São Paulo. M1, M2 e M3 usam só o do meio do dia.],
)

A velocidade de cada aresta no OSMnx vem da etiqueta `maxspeed`. Onde ela falta, entra o padrão do tipo de via. O tempo de fluxo livre é o comprimento dividido por essa velocidade. Não é um tempo medido. Os fatores da manhã e da noite existem para M0.5 e M0.6, que têm três períodos. Os modelos completos não os usam.

Sem duração em cache, o tempo seria $ceil(c_(i j) / v)$. É o que vale para a casa do corretor e para o ponto de almoço, e para qualquer cidade sem índice.

== Casas, almoço e o que não está no índice

Casas e pontos de almoço são pontos sorteados, não anúncios, então não entram na matriz de ruas. Numa instância real o fator de desvio é 1: a distância permanece a reta entre as coordenadas do mapa, arredondada a duas casas, e o tempo é $ceil(c / v)$ com $v = 2$. Numa instância sintética a mesma reta é multiplicada pelo fator de desvio.

A casa de cada corretor é sorteada de modo uniforme no casco convexo dos anúncios da cidade, na mesma projeção da amostra. O ponto de almoço é sorteado no quadrado $100 times 100$. A nota de distâncias registra os dois como pontos fora do índice, com distância em linha reta na instância real. O gerador separa o lugar do sorteio: a casa fica no casco da cidade e o almoço no mapa unitário.

A agenda oculta usa, em cada perna, o maior tempo entre os períodos. Com um período só, esse máximo é o próprio tempo. A agenda do M1 e do M3 toma a primeira perna a partir da casa. A do M2 toma a manhã a partir da casa e a tarde a partir do ponto de almoço.

== Instância sintética, para contraste

Um ponto no mapa $100 times 100$ não é um endereço, então não há caminho a calcular. A distância é a reta vezes um fator de desvio, arredondado a duas casas. O fator é a mediana da razão entre metros de rua e metros em linha reta, medida em 24 pares não ordenados de coordenadas distintas de Moema, nas duas direções, 48 razões. O sorteio usa a semente 20261010, que não é semente de instância. Nenhuma razão foi descartada. A mediana, a quatro casas, é 1,3671, gravada em `data/travel/detour_factor.json`. Ela vale para todo mapa sintético, inclusive casas e pontos de almoço. A mesma semente de instância continua colocando os nós nas mesmas coordenadas. As distâncias mudam, e as janelas mudam com elas, porque o tempo de viagem sintético é $ceil(c_(i j) / v)$ sobre a distância nova.

Dois números publicados servem de conferência, não de valor copiado. Ballou, Rahardja e Sakai (2002) reportam uma circuidade média de 1,23 para o Brasil, numa rede rodoviária nacional. Boscoe, Henry e Zdeb (2012) estimam 1,417 para viagens a hospitais comunitários nos Estados Unidos. A mediana medida em Moema fica entre os dois.

A matriz fica pronta antes do MILP. Uma API de rotas ao vivo, um rastro de GPS ou um sorteio do tempo de viagem mudaria $c_(i j)$ ou $t_(i j)$ entre execuções, e o solver estaria resolvendo outra instância. Tráfego ao vivo, rastros e tempo aleatório ficam para depois. A referência para o tempo estocástico é Taş, Dellaert, van Woensel e de Kok (2013).

= Decisões registradas na pasta docs

A pasta `docs/decisions/` tem duas notas. `capacity.md` decide a capacidade. `travel.md` decide distâncias e tempos. As páginas dos modelos guardam as decisões de objetivo que saíram da mesma discussão: o que entra na função, o que só desempata, e o que permanece restrição.

== Sem capacidade de carga

M1 e M2 não recebem uma capacidade de carga no sentido do CVRP. Um corretor que mostra um imóvel não transporta demanda, então um $q_i$ não tem significado aqui. O que uma rota consegue atender já é limitado pelo tempo, e o tempo é o recurso escasso na literatura de escala e roteamento de mão de obra. A mesma redação cobre M1.a e M3, que copiam o limite de jornada do M1. Nenhuma restrição de capacidade foi acrescentada ao código.

Os modelos são descritos como restritos por recurso, com o tempo no papel de recurso. Não são descritos como capacitados. Em roteamento de veículos, capacitado significa um limite de carga $sum q_i <= Q$, e quem lê essa palavra procura $Q$.

Um teto no número de visitas por corretor permanece opcional. Ele só entra se $Q_k$ vier de dado real, por exemplo quantas visitas um corretor faz num dia. Com janelas de $plus.minus 10$ minutos em torno de cada visita marcada, o relógio já limita quantas visitas cabem. Um teto acima desse limite nunca fica ativo e não muda os resultados.

Duas funções da capacidade do CVRP já são feitas pelo tempo. A primeira é quanto uma rota atende. Sem algum limite, um problema de roteamento cai num caixeiro-viajante múltiplo. O M1 limita o dia de cada corretor a $J_max = 720$ minutos, da saída de casa ao fim da última visita. Isso é um VRP restrito por duração (Laporte, Desrochers e Nobert, 1984). O fim regular $L_k$ é brando: o que passa dele é hora extra. Só $J_max$ é rígido. O M2 limita cada turno pelo fim rígido $L_r$: a última visita do turno termina até $L_r$. A segunda função é eliminar subciclos. Na formulação de carga de Miller–Tucker–Zemlin a carga ao longo da rota é a variável de ordem. Aqui os inícios $w_i$, com as restrições de fluxo de tempo em Big-M, fazem esse papel desde o M0.1.

Os levantamentos de WSRP tratam o tempo do trabalhador como o recurso escasso: regras de jornada, pausas, turnos, habilidades e janelas (Castillo-Salazar, Landa-Silva e Qu, 2016; Paraskevopoulos, Laporte, Repoussis e Tarantilis, 2017). O mesmo vale para o roteamento de cuidado domiciliar (Fikar e Hirsch, 2017; Cissé et al., 2017). Uma carga física aparece quando o trabalhador carrega alguma coisa, como um técnico com ferramentas e peças (Kovacs, Parragh, Doerner e Hartl, 2012). Esse é outro problema.

Vários dos nomes usados no projeto, na definição canônica, incluem capacidade: VRPTW, rotas abertas, múltiplos depósitos, dependência de local e frota mista. A nota registra a omissão no texto, que é a opção usada. Todo modelo é o caso sem capacidade, $Q_k >= n$, e o dia de 12 horas no M1 e os turnos rígidos no M2 são as restrições de recurso da rota. As desigualdades lineares de duração por rota e na frota em (8) expõem a parte aditiva desse limite diretamente em $x$ e $y$, sem depender do Big-M, de modo que o pré-resolvedor rejeita de imediato instâncias cuja soma das durações excede o tempo disponível dos corretores. Ficaram de lado um teto opcional de visitas e tratar assentos no carro do corretor. Levar o cliente entre imóveis seria um problema de coleta e entrega, fora do escopo.

A analogia com a carga para na geração de colunas, onde carga e tempo são o mesmo tipo de objeto: uma quantidade que acumula ao longo da rota e para num limite. O tempo é um recurso menos organizado, e o texto deve dizer isso. A espera por uma janela faz o relógio saltar para a abertura. A carga só soma. O M1 limita um intervalo, da saída de casa ao fim da última visita, não uma soma de demandas. O M2 tem dois limites por corretor, manhã e tarde, em vez de uma capacidade diária única.

A redação guardada para o texto é: os modelos não são capacitados no sentido clássico do CVRP. Quanto cada rota atende é limitado por restrições de tempo, jornada e turnos, então eles pertencem à família de VRP restrito por duração e por recurso, na qual o tempo faz o papel que a capacidade de carga faz no CVRP.

== Distâncias, tempos e o que ficou de fora

A nota de viagem fixa quatro escolhas.

A primeira é a rede. São Paulo usa caminho mínimo no grafo de direção do OpenStreetMap, com duração de fluxo livre depois escalada pelo congestionamento do período de partida. Uma instância sintética conserva a reta vezes o fator 1,3671 medido em Moema. Modelos sem perfil de velocidade, M0.1 a M0.4, conservam o tempo constante de 30 minutos em toda viagem, inclusive numa instância real em cache.

A segunda é a matriz pronta. O MILP tem de ser o mesmo modelo toda vez que uma semente roda. Ficaram de lado um OSRM auto-hospedado, o servidor público de demonstração do OSRM, e uma calibração avulsa contra uma API comercial de rotas. O congestionamento vem de um índice publicado, então o multiplicador pode ser refeito a partir da página. Copiar 1,23 ou 1,417 para dentro do gerador também ficou de lado: os dois descrevem outras redes. O fator no cache é a mediana medida nos pares de Moema.

A terceira é o período único dos modelos completos. M1, M1.a, M2 e M3 usam o fator do meio do dia, 1,796, porque a velocidade normal deles é a do meio do perfil de pico. M0.5 e M0.6 multiplicam a duração livre pelo fator do período de partida. M0.0 a M0.4 minimizam distância. M0.5 minimiza o tempo fora da agência, e M0.6 a frota e depois esse tempo. M1 e M1.a minimizam tempo de viagem, com um peso de distância pequeno demais para valer um minuto de direção. M2 minimiza combustível, precificado a partir da distância.

A quarta é a função de tempo em degraus de M0.5 e M0.6, o modelo de Malandraki e Daskin (1992). Um degrau para baixo na fronteira de um período pode fazer uma saída mais tarde chegar mais cedo, e isso quebra a regra de primeiro a entrar, primeiro a sair. Ichoua, Gendreau e Potvin (2003) mantêm a velocidade constante dentro do período e a integram ao longo da viagem, de modo que o tempo fica afim no minuto exato de saída. Usar essa forma muda o coeficiente do instante de partida nas desigualdades de fluxo de tempo. Ela não cabe na formulação atual sem uma reescrita, então não foi implementada. Com os fatores de São Paulo, o degrau que pode quebrar a regra é o da manhã para o meio do dia, de 1,859 para 1,796. O fator da noite, 2,005, é maior que o do meio do dia, então essa fronteira não quebra.

O que o texto pode afirmar: uma instância de São Paulo é roteada na rede de direção do OpenStreetMap dos anúncios da cidade, com tempos de fluxo livre escalados pelo congestionamento de dia de semana. Qualquer amostra desses anúncios está coberta. Uma instância sintética usa um fator de desvio medido na mesma rede, conferido contra as razões publicadas, e o fator é fixo para uma semente. Os modelos não consultam um mapa na hora da resolução e não sorteiam o tempo de viagem.

== Decisões de objetivo

Três decisões de objetivo estão nas páginas dos modelos e valem para interpretar os experimentos.

No M1 a hierarquia é rígida por construção dos pesos. Um corretor a menos vale mais que qualquer combinação de tempo, distância, atraso e hora extra. Entre planos com a mesma frota, um minuto de direção vale mais que a distância inteira. O atraso pesa 10 e a hora extra pesa 100, ambos por minuto, salvo peso informado. A distância não é um custo em reais.

No M2 o custo é o combustível. Atraso e dia mais longo só desempatam, e um minuto deles não compra 0,01 unidade de mapa de combustível. Não há termo de salário. A maior jornada é uma medida de justiça min-max e não um segundo objetivo em pé de igualdade com o combustível.

No M3 a troca entre os lados não é uma soma ponderada. Cada tamanho de frota é uma resolução que minimiza o custo dos corretores com um teto no número de corretores. A frente pode ter um único ponto. Escolher um ponto da frente fica fora do modelo.

O nome dinâmico nos três títulos não significa reotimização dentro do MILP. O modelo resolve o começo do dia. Quem quiser reagir a uma visita que mudou chama o modelo de novo.


= Referências citadas nas notas

As referências completas, com DOI, estão em `docs/decisions/capacity.md`, `docs/decisions/travel.md` e nas páginas `docs/models/m1.md`, `m1.a.md`, `m2.md` e `m3.md`. As que este texto nomeia são:

- Ballou, Rahardja e Sakai (2002), fatores de circuidade.
- Bektaş e Laporte (2011), problema de roteamento com poluição.
- Boeing (2017), OSMnx.
- Boland, Charkhgard e Savelsbergh (2015), método da caixa balanceada.
- Boscoe, Henry e Zdeb (2012), distância de direção contra linha reta.
- Braekers, Hartl, Parragh e Tricoire (2016), frente entre custo e incômodo no cuidado domiciliar.
- Castillo-Salazar, Landa-Silva e Qu (2016), levantamento de WSRP.
- Cissé et al. (2017) e Fikar e Hirsch (2017), roteamento de cuidado domiciliar.
- Desrochers e Laporte (1991), fortalecimento (lifting) das restrições MTZ e janelas de tempo.
- Ichoua, Gendreau e Potvin (2003), tempos de viagem que preservam FIFO.
- Jozefowiez, Semet e Talbi (2008), roteamento multiobjetivo.
- Kovacs, Parragh, Doerner e Hartl (2012), técnico com carga.
- Laporte, Desrochers e Nobert (1984), VRP restrito por distância.
- Malandraki e Daskin (1992), tempo de viagem em degraus.
- Matl, Hartl e Vidal (2018), equidade de carga em roteamento.
- Mavrotas (2009), método da $epsilon$-restrição.
- OpenStreetMap contributors, rede baixada em 10 de outubro de 2026.
- Paraskevopoulos, Laporte, Repoussis e Tarantilis (2017), roteamento restrito por recurso.
- Taş, Dellaert, van Woensel e de Kok (2013), tempo de viagem estocástico.
- TomTom Traffic Index 2025, relatório de São Paulo.
- Yuan, Cattaruzza, Ogier e Semet (2020), nota sobre a validade das restrições MTZ levantadas com espera.

Preço do etanol: média ANP da cidade de São Paulo, semana de 4 a 10 de outubro de 2026. Consumo: tabela PBEV do Inmetro, 14 de agosto de 2026, Volkswagen Polo 1.0 MPI, ciclo urbano, etanol.

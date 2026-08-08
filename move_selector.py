"""
Selection de coup du bot, combinant trois signaux comme demande :

1. Qualite objective de la position (% de victoire selon Stockfish, formule Lichess -- voir
   elo_common.py) : le signal dominant, toujours present.

2. Ajustement selon l'ELO estime de l'adversaire ("est-ce que ca le met dans une bonne situation
   FACE A l'ELO de l'adversaire") : pour chaque coup candidat, on regarde aussi les meilleures
   reponses possibles de l'adversaire (mini-recherche a la reponse). Si sa meilleure reponse est
   nettement meilleure que ses autres options, le coup est "piegeux" -- risque pour l'adversaire
   de ne pas trouver la bonne suite. Plus l'ELO estime de l'adversaire est bas, plus ce potentiel
   de piege pese dans la decision (un joueur fort trouve la bonne reponse, un joueur faible non).
   Plus l'ELO est haut, plus on retombe sur le coup objectivement le plus solide.

3. Bonus de style en fin de partie ("si c'est en fin de partie, la note de ressemblance, mais ca
   c'est juste un bonus pour departager") : utilise le profil de l'adversaire construit en
   ouverture/milieu (style_profile.py) pour orienter LEGEREMENT le choix, seulement quand les
   coups sont proches en score. Proxy simple : si l'adversaire a un taux eleve de
   "hangs_material" (laisse souvent du materiel en prise), on privilegie legerement les positions
   complexes (beaucoup de captures/echecs possibles) ou il est statistiquement plus susceptible
   de se tromper.

Le choix final se fait par un tirage softmax avec temperature sur les scores des N meilleurs
coups (pas sur tous les coups legaux) : temperature basse = quasi-deterministe (le meilleur
coup gagne presque toujours), temperature haute = plus d'exploration/varete.

Limite assumee : la recherche de "piege" ne regarde qu'un seul coup de reponse adverse (pas une
vraie analyse multi-coups), et le bonus de style est une heuristique de complexite de position,
pas une prediction comportementale validee. C'est un prototype de mecanique, pas un moteur fiable.
"""

import math
import random
import chess
import chess.engine

from elo_common import win_percent, cp_capped
from style_profile import classify_move, is_endgame


CANDIDATE_MULTIPV = 4
CANDIDATE_DEPTH = 20   # "20 coups a l'avance" demande -- couteux, voir commentaire timing plus bas
REPLY_MULTIPV = 3
REPLY_DEPTH = 16
TRAP_WEIGHT_MAX = 4.0    # poids max du bonus piege (en points de %), pour l'adversaire le plus faible
STYLE_WEIGHT = 3.0        # poids max du bonus de style (petit -- c'est un simple depart-age)
WIN_PCT_TOLERANCE = 6.0   # un coup n'entre dans la course "piege/style" que s'il est a moins de
                           # ca du meilleur coup objectif -- le piege ne peut jamais repecher un
                           # coup nettement pire, seulement departager entre des coups deja bons


def opponent_skill_factor(opponent_elo: float) -> float:
    """0 = adversaire au plancher (1320), 1 = adversaire au plafond (3190).
    Plus c'est proche de 1, plus on suppose qu'il trouve la meilleure reponse."""
    return max(0.0, min(1.0, (opponent_elo - 1320) / (3190 - 1320)))


def complexity_score(board: chess.Board) -> int:
    """Proxy grossier de complexite tactique d'une position : nb de captures + nb de coups
    donnant echec, parmi les coups legaux du joueur au trait."""
    n = 0
    for move in board.legal_moves:
        if board.is_capture(move):
            n += 1
        else:
            b2 = board.copy()
            b2.push(move)
            if b2.is_check():
                n += 1
    return n


def trap_bonus_for(engine: chess.engine.SimpleEngine, board_after_move: chess.Board,
                    opponent_color: chess.Color) -> float:
    """Ecart (en % de victoire, POV adversaire) entre sa meilleure reponse et la moyenne de ses
    autres bonnes reponses. Positif = coup piegeux (facile de mal repondre)."""
    if board_after_move.is_game_over():
        return 0.0
    legal_count = board_after_move.legal_moves.count()
    multipv = min(REPLY_MULTIPV, max(1, legal_count))
    infos = engine.analyse(board_after_move, chess.engine.Limit(depth=REPLY_DEPTH), multipv=multipv)
    if not isinstance(infos, list):
        infos = [infos]
    wps = [win_percent(cp_capped(i["score"], opponent_color)) for i in infos]
    if len(wps) < 2:
        return 0.0
    best = wps[0]
    avg_others = sum(wps[1:]) / len(wps[1:])
    return max(0.0, best - avg_others)


def style_bonus_for(board: chess.Board, move: chess.Move, color: chess.Color,
                     opponent_profile: dict) -> float:
    if not opponent_profile:
        return 0.0
    after = board.copy()
    after.push(move)
    comp = complexity_score(after)  # complexite de ce que l'adversaire va devoir gerer
    hangs_rate = opponent_profile.get("hangs_material", 0.0)
    # normalise grossierement (0-10 coups tactiques -> 0-1)
    comp_norm = min(1.0, comp / 10.0)
    return comp_norm * hangs_rate


def softmax_pick(items_with_scores, temperature: float):
    if temperature <= 1e-6:
        return max(items_with_scores, key=lambda t: t[1])[0]
    scores = [s for _, s in items_with_scores]
    m = max(scores)
    weights = [math.exp((s - m) / temperature) for s in scores]
    total = sum(weights)
    r = random.random() * total
    acc = 0.0
    for (item, _), w in zip(items_with_scores, weights):
        acc += w
        if r <= acc:
            return item
    return items_with_scores[-1][0]


def choose_move(engine: chess.engine.SimpleEngine, board: chess.Board, bot_color: chess.Color,
                 opponent_elo: float, opponent_profile: dict = None, temperature: float = 0.5,
                 verbose: bool = False):
    infos = engine.analyse(board, chess.engine.Limit(depth=CANDIDATE_DEPTH), multipv=CANDIDATE_MULTIPV)
    if not isinstance(infos, list):
        infos = [infos]

    skill = opponent_skill_factor(opponent_elo)
    trap_weight = (1.0 - skill) * TRAP_WEIGHT_MAX
    endgame = is_endgame(board)

    # win% objectif de chaque candidat, calcule d'abord et separement -- sert de filtre avant
    # meme de regarder piege/style, pour qu'un coup nettement pire ne puisse jamais l'emporter.
    base = []
    for info in infos:
        move = info["pv"][0]
        wp = win_percent(cp_capped(info["score"], bot_color))
        base.append((move, wp))
    best_wp = max(wp for _, wp in base)

    scored = []
    for move, wp in base:
        if best_wp - wp > WIN_PCT_TOLERANCE:
            if verbose:
                print(f"    candidat {move.uci():<6} winpct={wp:5.1f}  EXCLU (trop loin du meilleur coup objectif)")
            continue

        after = board.copy()
        after.push(move)
        trap = trap_bonus_for(engine, after, not bot_color) if not after.is_game_over() else 0.0

        style = 0.0
        if endgame and opponent_profile:
            style = style_bonus_for(board, move, bot_color, opponent_profile)

        total = wp + trap_weight * trap + STYLE_WEIGHT * style
        scored.append((move, total))
        if verbose:
            print(f"    candidat {move.uci():<6} winpct={wp:5.1f}  piege={trap:5.1f}(x{trap_weight:.1f})  "
                  f"style={style:4.2f}(x{STYLE_WEIGHT})  total={total:6.2f}")

    if not scored:  # filet de securite, ne devrait pas arriver (le meilleur coup passe toujours le filtre)
        scored = [(base[0][0], base[0][1])]

    chosen = softmax_pick(scored, temperature)
    return chosen

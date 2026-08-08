"""
Prototype : estimation d'ELO en direct a partir de la qualite des coups joues.

Principe :
- Un adversaire "cible" joue avec un ELO impose par Stockfish (UCI_LimitStrength / UCI_Elo),
  ce qui sert de verite terrain (Stockfish est calibre sur de vraies parties humaines pour ce mode).
- Un moteur d'analyse (Stockfish plein potentiel) evalue, a CHAQUE coup de l'adversaire,
  l'ecart entre le meilleur coup possible et le coup reellement joue (perte en centipawns, "ACPL").
- L'ACPL cumule est converti en estimation d'ELO via une courbe de calibration empirique.
- On affiche l'estimation apres chaque coup pour voir si/quand elle converge vers le vrai ELO.

C'est le meme principe que le modele utilise par la FIDE/Kenneth Regan et par le detecteur
de triche de Lichess, en version tres simplifiee (pas de ponderation par complexite de position).
"""

import os
import math
import chess
import chess.engine

from elo_common import expected_loss

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SF = ["node", os.path.join(SCRIPT_DIR, "stockfish", "stockfish-18-lite-single.js")]

# Regression log-lineaire ajustee sur ~26 parties simulees (calibrate.py), ELO cible de 1320 a
# 3190, hors coups d'ouverture. Metrique = perte moyenne en % de victoire (pas l'ACPL brut, voir
# elo_common.py). R2 pondere ~0.84 sur les moyennes par palier d'ELO. Voir calibration_data.csv.
CALIB_A = 2881.0
CALIB_B = -981.4

def acpl_to_elo(expected_loss_avg: float) -> int:
    el = max(expected_loss_avg, 0.05)  # eviter ln(0)
    elo = CALIB_A + CALIB_B * math.log(el)
    return round(max(1320, min(3190, elo)))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Estime l'ELO d'un adversaire simule coup par coup.")
    parser.add_argument("--elo", type=int, default=1320,
                         help="ELO impose a l'adversaire simule (verite terrain). Min 1320, max 3190. Defaut: 1320")
    parser.add_argument("--moves", type=int, default=25, help="Nombre de coups (pleins) max a jouer. Defaut: 25")
    parser.add_argument("--depth", type=int, default=10, help="Profondeur d'analyse de l'analyseur. Defaut: 10")
    parser.add_argument("--skip-opening", type=int, default=6,
                         help="Nombre de coups d'ouverture de l'adversaire a exclure du calcul ACPL (bruit theorie). Defaut: 6")
    args = parser.parse_args()

    TARGET_ELO = max(1320, min(3190, args.elo))
    MAX_FULL_MOVES = args.moves
    ANALYZER_DEPTH = args.depth
    SKIP_OPENING = args.skip_opening
    ANALYZER_LIMIT = chess.engine.Limit(depth=ANALYZER_DEPTH, time=0.3)
    MOVE_TIME = 0.08

    opponent = chess.engine.SimpleEngine.popen_uci(SF)
    opponent.configure({"UCI_LimitStrength": True, "UCI_Elo": TARGET_ELO})

    PARTNER_ELO = min(3190, TARGET_ELO + 300)  # coherent avec calibrate.py
    partner = chess.engine.SimpleEngine.popen_uci(SF)
    partner.configure({"UCI_LimitStrength": True, "UCI_Elo": PARTNER_ELO})

    analyzer = chess.engine.SimpleEngine.popen_uci(SF)

    import time as _time
    t_start = _time.time()
    TIME_BUDGET = 30  # secondes, garde-fou dur

    board = chess.Board()
    losses = []  # centipawn loss de l'adversaire, coup par coup
    OPP_COLOR = chess.WHITE

    print(f"Adversaire simule a {TARGET_ELO} ELO (verite terrain, impose via Stockfish).")
    print(f"Partenaire (sparring) a {PARTNER_ELO} ELO. Analyseur en pleine puissance, profondeur {ANALYZER_DEPTH}.\n")

    move_no = 0
    while not board.is_game_over() and move_no < MAX_FULL_MOVES * 2 and _time.time() - t_start < TIME_BUDGET:
        mover_color = board.turn
        if mover_color == OPP_COLOR:
            score_before = analyzer.analyse(board, ANALYZER_LIMIT)["score"]
            result = opponent.play(board, chess.engine.Limit(time=MOVE_TIME))
            move = result.move
            board.push(move)
            score_after = analyzer.analyse(board, ANALYZER_LIMIT)["score"]
            loss = expected_loss(score_before, score_after, mover_color)
            losses.append(loss)

            usable = losses[SKIP_OPENING:]
            if usable:
                acpl = sum(usable) / len(usable)
                est_elo = acpl_to_elo(acpl)
                tag = f"ELO estime={est_elo}"
            else:
                acpl = sum(losses) / len(losses)
                tag = f"(ouverture, ignore -- estimation dispo apres coup {SKIP_OPENING + 1})"
            print(f"coup {len(losses):>2} ({move.uci():<5}) perte={loss:5.1f}%pts  "
                  f"perte moy cumulee={acpl:5.2f}%pts  {tag}")
        else:
            result = partner.play(board, chess.engine.Limit(time=MOVE_TIME))
            board.push(result.move)

        move_no += 1

    usable = losses[SKIP_OPENING:]
    print(f"\n--- Resultat final apres {len(losses)} coups analyses de l'adversaire "
          f"({len(usable)} retenus, {SKIP_OPENING} d'ouverture exclus) ---")
    final_acpl = sum(usable) / len(usable) if usable else 0
    print(f"Perte moyenne (%pts de victoire) : {final_acpl:.2f}")
    print(f"ELO estime : {acpl_to_elo(final_acpl)}")
    print(f"ELO reel (verite terrain) : {TARGET_ELO}")

    opponent.quit()
    partner.quit()
    analyzer.quit()


if __name__ == "__main__":
    main()

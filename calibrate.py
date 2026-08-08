"""
Genere de vraies donnees (ELO impose -> perte moyenne en % de victoire) pour calibrer
acpl_to_elo(). A lancer plusieurs fois avec des listes d'ELO differentes (le budget temps
d'un run est limite), les resultats s'accumulent dans calibration_data.csv.

Metrique : "expected loss" (EL), pas l'ACPL brut. Voir elo_common.py pour le pourquoi.
"""
import os
import sys
import time
import chess
import chess.engine

from elo_common import expected_loss

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SF = ["node", os.path.join(SCRIPT_DIR, "stockfish", "stockfish-18-lite-single.js")]
CSV_PATH = os.path.join(SCRIPT_DIR, "calibration_data.csv")

MOVES = 30          # coups pleins max
SKIP_OPENING = 6    # on ignore les N premiers coups de l'adversaire (bruit theorie/ouverture)
ANALYZER_LIMIT = chess.engine.Limit(depth=9, time=0.25)
MOVE_TIME = 0.06


def play_one(target_elo):
    opponent = chess.engine.SimpleEngine.popen_uci(SF)
    opponent.configure({"UCI_LimitStrength": True, "UCI_Elo": target_elo})
    partner = chess.engine.SimpleEngine.popen_uci(SF)
    partner.configure({"UCI_LimitStrength": True, "UCI_Elo": min(3190, target_elo + 300)})
    analyzer = chess.engine.SimpleEngine.popen_uci(SF)

    board = chess.Board()
    losses = []
    OPP = chess.WHITE
    move_no = 0
    while not board.is_game_over() and move_no < MOVES * 2:
        mover = board.turn
        if mover == OPP:
            score_before = analyzer.analyse(board, ANALYZER_LIMIT)["score"]
            res = opponent.play(board, chess.engine.Limit(time=MOVE_TIME))
            board.push(res.move)
            score_after = analyzer.analyse(board, ANALYZER_LIMIT)["score"]
            losses.append(expected_loss(score_before, score_after, mover))
        else:
            res = partner.play(board, chess.engine.Limit(time=MOVE_TIME))
            board.push(res.move)
        move_no += 1

    opponent.quit()
    partner.quit()
    analyzer.quit()

    usable = losses[SKIP_OPENING:]
    if not usable:
        return None
    return sum(usable) / len(usable)


def main():
    elos = [int(x) for x in sys.argv[1:]]
    if not elos:
        print("usage: python3 calibrate.py ELO1 ELO2 ...")
        return

    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a") as f:
        if not file_exists:
            f.write("elo,expected_loss\n")
        for elo in elos:
            t0 = time.time()
            el = play_one(elo)
            dt = time.time() - t0
            if el is None:
                print(f"elo={elo}: pas assez de coups exploitables, skip")
                continue
            f.write(f"{elo},{el:.3f}\n")
            f.flush()
            print(f"elo={elo:5d}  expected_loss={el:6.2f}  ({dt:.1f}s)")


if __name__ == "__main__":
    main()

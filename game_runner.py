"""
10 parties : le bot (Stockfish plein potentiel + move_selector.choose_move) joue les blancs
contre un adversaire simule a un ELO fixe, une fois SANS le bonus (piege+style desactives),
une fois AVEC (actifs), pour chaque palier d'ELO adverse.

"Sans bonus" est obtenu en appelant choose_move avec opponent_elo=3190 (skill=1 -> trap_weight=0)
et sans profil de style -- ce qui revient exactement au coup objectivement le plus solide,
temperature=0. "Avec bonus" utilise le vrai ELO adverse pour ponderer le piege (le style reste
desactive ici : pas de profil d'adversaire pre-existant a fournir dans ce test isole).

Temperature=0 des deux cotes pour isoler l'effet du bonus (sinon on ne distingue pas "le bonus a
change le resultat" de "le hasard du tirage a change le resultat").
"""
import os
import sys
import time
import chess
import chess.engine

from move_selector import choose_move
from style_profile import SF

MAX_FULL_MOVES = 80
BOT_TIME_BUDGET = 35  # secondes, garde-fou par partie


def play_game(opponent_elo: int, use_bonus: bool):
    bot_engine = chess.engine.SimpleEngine.popen_uci(SF)  # plein potentiel, pas de limite
    opponent = chess.engine.SimpleEngine.popen_uci(SF)
    opponent.configure({"UCI_LimitStrength": True, "UCI_Elo": opponent_elo})

    board = chess.Board()
    move_no = 0
    t0 = time.time()
    effective_elo_for_selector = 3190 if not use_bonus else opponent_elo

    while not board.is_game_over(claim_draw=True) and move_no < MAX_FULL_MOVES * 2 \
            and time.time() - t0 < BOT_TIME_BUDGET:
        if board.turn == chess.WHITE:
            move = choose_move(bot_engine, board, chess.WHITE,
                                opponent_elo=effective_elo_for_selector,
                                opponent_profile=None, temperature=0.0)
            board.push(move)
        else:
            res = opponent.play(board, chess.engine.Limit(time=0.08))
            board.push(res.move)
        move_no += 1

    result = board.result(claim_draw=True) if board.is_game_over(claim_draw=True) else "1/2-1/2 (limite coups atteinte)"
    dt = time.time() - t0

    bot_engine.quit()
    opponent.quit()
    return result, move_no, dt


def main():
    elos = [int(x) for x in sys.argv[1:]]
    if not elos:
        print("usage: python3 game_runner.py ELO1 ELO2 ...")
        return

    for elo in elos:
        for use_bonus in (False, True):
            label = "AVEC bonus" if use_bonus else "SANS bonus"
            result, moves, dt = play_game(elo, use_bonus)
            outcome = {"1-0": "bot GAGNE", "0-1": "bot PERD", "1/2-1/2": "NULLE"}.get(result, result)
            print(f"elo_adverse={elo:5d}  {label}  ->  {outcome:20s}  ({moves} demi-coups, {dt:.1f}s)  [{result}]")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

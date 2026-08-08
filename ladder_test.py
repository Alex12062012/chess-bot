"""
Bot (profondeur 20, avec bonus) contre l'echelle complete UCI_Elo de Stockfish (1320 a 3190,
son maximum). Chaque partie est trop longue pour tenir dans un seul appel a cette profondeur
(~5s par coup du bot rien que pour choisir) -- donc l'etat de la partie est sauvegarde dans un
fichier texte (liste de coups UCI) et repris a chaque execution, jusqu'a ce qu'elle se termine.

usage: python3 ladder_test.py ELO [moves_budget] [time_budget_sec]
Relancer la meme commande plusieurs fois jusqu'a ce qu'elle affiche "TERMINE".
"""
import os
import sys
import time
import chess
import chess.engine

from move_selector import choose_move
from style_profile import SF

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def state_path(elo):
    return os.path.join(SCRIPT_DIR, f"ladder_state_{elo}.txt")


def load_moves(elo):
    p = state_path(elo)
    if not os.path.exists(p):
        return []
    content = open(p).read().strip()
    return content.split() if content else []


def save_moves(elo, moves):
    with open(state_path(elo), "w") as f:
        f.write(" ".join(moves))


def main():
    elo = int(sys.argv[1])
    moves_budget = int(sys.argv[2]) if len(sys.argv) > 2 else 6   # demi-coups a jouer cette execution
    time_budget = float(sys.argv[3]) if len(sys.argv) > 3 else 38.0

    moves = load_moves(elo)
    board = chess.Board()
    for u in moves:
        board.push(chess.Move.from_uci(u))

    if board.is_game_over(claim_draw=True):
        print(f"[{elo}] deja TERMINE apres {len(moves)} demi-coups : {board.result(claim_draw=True)}")
        return

    bot_engine = chess.engine.SimpleEngine.popen_uci(SF)
    opponent = chess.engine.SimpleEngine.popen_uci(SF)
    opponent.configure({"UCI_LimitStrength": True, "UCI_Elo": elo})

    t0 = time.time()
    added = 0
    while not board.is_game_over(claim_draw=True) and added < moves_budget and time.time() - t0 < time_budget:
        if board.turn == chess.WHITE:
            move = choose_move(bot_engine, board, chess.WHITE, opponent_elo=elo,
                                opponent_profile=None, temperature=0.0)
        else:
            res = opponent.play(board, chess.engine.Limit(time=0.08))
            move = res.move
        board.push(move)
        moves.append(move.uci())
        added += 1

    save_moves(elo, moves)
    bot_engine.quit()
    opponent.quit()

    if board.is_game_over(claim_draw=True):
        print(f"[{elo}] TERMINE apres {len(moves)} demi-coups : {board.result(claim_draw=True)}  "
              f"({time.time()-t0:.1f}s cette execution)")
    else:
        print(f"[{elo}] en cours... {len(moves)} demi-coups joues au total "
              f"({time.time()-t0:.1f}s cette execution, relancer pour continuer)")


if __name__ == "__main__":
    main()

"""
Bot (profondeur 20, avec bonus) contre Stockfish en FORCE NATIVE (pas de UCI_LimitStrength du
tout -- sa vraie puissance, celle mesuree autour de 3600-3800 sur les classements CCRL/CEGT),
a profondeur 20 egalement cote adversaire pour que le temps de reflexion soit comparable des
deux cotes (dans tous les tests precedents, l'adversaire ne reflechissait que 80ms/coup, ce qui
biaisait en faveur du bot -- corrige ici).

Meme systeme de reprise par fichier que ladder_test.py (une partie ne tient pas dans un seul
appel a cette profondeur).

Avec temperature > 0, le choix du bot n'est plus deterministe (tirage softmax parmi les
candidats proches du meilleur coup) -- donc ce n'est plus un miroir parfait Stockfish-vs-Stockfish
rejouable a l'identique. L'adversaire (Stockfish natif) reste deterministe, seul le bot varie.

usage: python3 bot_vs_max_stockfish.py [moves_budget] [time_budget_sec] [temperature] [state_file]
"""
import os
import sys
import time
import chess
import chess.engine

from move_selector import choose_move
from style_profile import SF

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OPPONENT_DEPTH = 20  # meme profondeur que le bot, pour un temps de reflexion comparable


def load_moves(state_path):
    if not os.path.exists(state_path):
        return []
    content = open(state_path).read().strip()
    return content.split() if content else []


def save_moves(state_path, moves):
    with open(state_path, "w") as f:
        f.write(" ".join(moves))


def main():
    moves_budget = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    time_budget = float(sys.argv[2]) if len(sys.argv) > 2 else 38.0
    temperature = float(sys.argv[3]) if len(sys.argv) > 3 else 0.6
    state_file = sys.argv[4] if len(sys.argv) > 4 else "bot_vs_max_state_temp.txt"
    state_path = os.path.join(SCRIPT_DIR, state_file)

    moves = load_moves(state_path)
    board = chess.Board()
    for u in moves:
        board.push(chess.Move.from_uci(u))

    if board.is_game_over(claim_draw=True):
        print(f"deja TERMINE apres {len(moves)} demi-coups : {board.result(claim_draw=True)}")
        return

    bot_engine = chess.engine.SimpleEngine.popen_uci(SF)
    opponent = chess.engine.SimpleEngine.popen_uci(SF)  # AUCUNE limitation -- force native

    t0 = time.time()
    added = 0
    while not board.is_game_over(claim_draw=True) and added < moves_budget and time.time() - t0 < time_budget:
        if board.turn == chess.WHITE:  # le bot
            move = choose_move(bot_engine, board, chess.WHITE, opponent_elo=3190,
                                opponent_profile=None, temperature=temperature)
        else:  # Stockfish force native, meme profondeur que le bot
            res = opponent.play(board, chess.engine.Limit(depth=OPPONENT_DEPTH))
            move = res.move
        board.push(move)
        moves.append(move.uci())
        added += 1

    save_moves(state_path, moves)
    bot_engine.quit()
    opponent.quit()

    if board.is_game_over(claim_draw=True):
        print(f"TERMINE apres {len(moves)} demi-coups : {board.result(claim_draw=True)}  "
              f"({time.time()-t0:.1f}s cette execution)")
    else:
        print(f"en cours... {len(moves)} demi-coups joues au total "
              f"({time.time()-t0:.1f}s cette execution, relancer pour continuer)")


if __name__ == "__main__":
    main()

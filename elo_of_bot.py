"""
Estime l'ELO reel du bot (pas de l'adversaire) : sans bonus vs avec bonus.

Meme methode que elo_estimator.py, appliquee cette fois aux coups du BOT plutot qu'a un
adversaire simule. Un analyseur INDEPENDANT, plus profond (depth=14) que la recherche de
candidats du bot (depth=10), mesure l'ecart de qualite entre ce que le bot joue et le meilleur
coup objectif, puis on convertit via la meme courbe de calibration.

Limite importante, a lire avant de croire le chiffre : la courbe de calibration a ete ajustee sur
des parties Stockfish brides entre 1320 et 3190 ELO -- si le bot est meilleur que 3190 (probable,
vu qu'il s'appuie sur Stockfish), le chiffre sera plafonne a 3190 et sous-estimera sa vraie force.
C'est une mesure de la PERTE DE QUALITE induite par le bonus par rapport au coup objectif, pas un
ELO FIDE au sens strict.
"""
import os
import sys
import chess
import chess.engine

from move_selector import choose_move
from elo_estimator import acpl_to_elo
from elo_common import expected_loss
from style_profile import SF

ANALYZER_LIMIT = chess.engine.Limit(depth=24)  # plus profond que le choix de coup du bot (depth=20)
SKIP_OPENING = 2  # reduit vu le budget limite a profondeur 20 (voir discussion cout/volume)
SPARRING_ELO = 2200


def measure(use_bonus: bool, n_games: int, max_moves: int):
    all_losses = []
    for g in range(n_games):
        bot_engine = chess.engine.SimpleEngine.popen_uci(SF)
        analyzer = chess.engine.SimpleEngine.popen_uci(SF)
        partner = chess.engine.SimpleEngine.popen_uci(SF)
        partner.configure({"UCI_LimitStrength": True, "UCI_Elo": SPARRING_ELO})

        board = chess.Board()
        losses = []
        move_no = 0
        while not board.is_game_over() and move_no < max_moves * 2:
            if board.turn == chess.WHITE:
                score_before = analyzer.analyse(board, ANALYZER_LIMIT)["score"]
                elo_for_selector = 3190 if not use_bonus else SPARRING_ELO
                move = choose_move(bot_engine, board, chess.WHITE,
                                    opponent_elo=elo_for_selector, opponent_profile=None,
                                    temperature=0.0)
                board.push(move)
                score_after = analyzer.analyse(board, ANALYZER_LIMIT)["score"]
                losses.append(expected_loss(score_before, score_after, chess.WHITE))
            else:
                res = partner.play(board, chess.engine.Limit(time=0.08))
                board.push(res.move)
            move_no += 1

        bot_engine.quit()
        analyzer.quit()
        partner.quit()

        usable = losses[SKIP_OPENING:]
        all_losses.extend(usable)
        if usable:
            print(f"  partie {g+1}/{n_games} : {len(usable)} coups retenus, "
                  f"perte moy = {sum(usable)/len(usable):.2f}%pts")

    if not all_losses:
        return None, 0
    avg = sum(all_losses) / len(all_losses)
    return avg, len(all_losses)


def main():
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    max_moves = int(sys.argv[2]) if len(sys.argv) > 2 else 25

    print(f"=== SANS bonus ({n_games} parties, sparring {SPARRING_ELO} ELO) ===")
    avg_no, n_no = measure(False, n_games, max_moves)
    elo_no = acpl_to_elo(avg_no) if avg_no is not None else None
    print(f"--> perte moyenne = {avg_no:.2f}%pts sur {n_no} coups -> ELO estime = {elo_no}"
          f"{' (plafond de calibration -- vraie force probablement superieure)' if elo_no == 3190 else ''}\n")

    print(f"=== AVEC bonus ({n_games} parties, sparring {SPARRING_ELO} ELO) ===")
    avg_yes, n_yes = measure(True, n_games, max_moves)
    elo_yes = acpl_to_elo(avg_yes) if avg_yes is not None else None
    print(f"--> perte moyenne = {avg_yes:.2f}%pts sur {n_yes} coups -> ELO estime = {elo_yes}"
          f"{' (plafond de calibration -- vraie force probablement superieure)' if elo_yes == 3190 else ''}\n")

    print("=== Cout objectif du bonus ===")
    print(f"Perte moyenne SANS bonus : {avg_no:.2f}%pts de victoire par coup")
    print(f"Perte moyenne AVEC bonus : {avg_yes:.2f}%pts de victoire par coup")
    print(f"Surcout du bonus         : {avg_yes - avg_no:+.2f}%pts par coup")


if __name__ == "__main__":
    main()

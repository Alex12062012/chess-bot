"""
Variante de elo_of_bot.py qui accumule les pertes coup par coup dans un CSV, pour pouvoir
lancer plusieurs petites parties sur plusieurs appels (profondeur 20 = trop lent pour tout
faire d'un coup) et agreger les resultats a la fin.

usage: python3 elo_of_bot_chunk.py [sans|avec] n_games max_moves
"""
import os
import sys
import chess
import chess.engine

from elo_of_bot import measure, ANALYZER_LIMIT, SKIP_OPENING, SPARRING_ELO

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "bot_elo_depth20.csv")


def main():
    label = sys.argv[1]  # "sans" ou "avec"
    n_games = int(sys.argv[2])
    max_moves = int(sys.argv[3])
    use_bonus = (label == "avec")

    avg, n = measure(use_bonus, n_games, max_moves)
    if avg is None:
        print("aucun coup exploitable")
        return

    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a") as f:
        if not file_exists:
            f.write("label,avg_loss,n_moves\n")
        f.write(f"{label},{avg:.4f},{n}\n")

    print(f"[{label}] ajoute : perte moy={avg:.2f}%pts sur {n} coups")


if __name__ == "__main__":
    main()

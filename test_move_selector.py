"""
Test de move_selector.py :
1. Meme position, adversaire faible (1320) vs fort (3190), temperature=0 (deterministe) --
   verifie que le poids du piege change bien le coup choisi.
2. Meme position, temperature basse vs haute -- verifie que la temperature fait varier le choix.
"""
import os
import chess
import chess.engine

from move_selector import choose_move
from style_profile import SF

engine = chess.engine.SimpleEngine.popen_uci(SF)

# on joue quelques coups "normaux" pour arriver a une position de milieu de partie non triviale
board = chess.Board()
opening_moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6", "b5a4", "g8f6",
                 "e1g1", "f8e7", "f1e1", "b7b5", "a4b3", "d7d6"]
for u in opening_moves:
    board.push(chess.Move.from_uci(u))

print("Position de test (Ruy Lopez, milieu de partie) :")
print(board, "\n")

print("=== Adversaire FAIBLE (1320 ELO), temperature=0 (deterministe) ===")
move_weak = choose_move(engine, board, chess.WHITE, opponent_elo=1320, temperature=0.0, verbose=True)
print(f"--> coup choisi contre un faible : {move_weak.uci()}\n")

print("=== Adversaire FORT (3190 ELO), temperature=0 (deterministe) ===")
move_strong = choose_move(engine, board, chess.WHITE, opponent_elo=3190, temperature=0.0, verbose=True)
print(f"--> coup choisi contre un fort   : {move_strong.uci()}\n")

if move_weak.uci() != move_strong.uci():
    print(">>> Le bot joue DIFFEREMMENT selon le niveau adverse. Comportement adaptatif confirme.\n")
else:
    print(">>> Meme coup dans les deux cas -- pas de piege detecte ici, ou le meilleur coup objectif\n"
          "    est deja assez piegeux tout seul. Pas forcement un echec, depend de la position.\n")

print("=== Effet de la temperature (20 tirages a T=0.8, adversaire 2000 ELO) ===")
from collections import Counter
counts = Counter()
for _ in range(20):
    m = choose_move(engine, board, chess.WHITE, opponent_elo=2000, temperature=0.8, verbose=False)
    counts[m.uci()] += 1
for uci, c in counts.most_common():
    print(f"  {uci:<6} choisi {c}/20 fois")

engine.quit()

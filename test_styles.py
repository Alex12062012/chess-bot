"""
Test de sanite pour style_profile.py : deux bots aux styles opposes, construits en biaisant
le choix de coup parmi les meilleurs candidats de Stockfish (MultiPV), pour verifier que le
profil detecte bien la difference. Stockfish n'a pas d'option "personnalite" native (pas de
Contempt sur cette build) -- le style est donc simule ici en re-classant les N meilleurs coups
via les memes tags que classify_move(), et en gardant celui qui colle le plus au style voulu.

Bot AGGRESSIF : favorise captures, echecs, avancees, et n'evite pas les coups qui laissent du
materiel en prise (proxy sacrifice).
Bot PRUDENT   : favorise les retraits, evite les echecs et les captures qui exposent du materiel.

Le partenaire (sparring) est un Stockfish normal, sans biais, identique pour les deux tests afin
que seule la variable "style du bot teste" change.
"""

import os
import chess
import chess.engine

from style_profile import (
    classify_move, is_endgame, StyleTracker, describe, SF
)

CANDIDATE_MULTIPV = 5
CANDIDATE_DEPTH = 9
MAX_EVAL_LOSS_CP = 150  # on ne considere que des coups pas trop mauvais par rapport au meilleur

AGGRESSIVE_WEIGHTS = {
    "capture": 1.0, "check": 2.0, "advances": 1.0, "hangs_material": 1.5,
    "trade_favorable": 0.5, "retreats": -2.0, "central_square": 0.5,
}
CAUTIOUS_WEIGHTS = {
    "retreats": 2.0, "check": -1.0, "hangs_material": -2.5, "capture": -0.3,
    "advances": -1.0, "trade_unfavorable": -1.0,
}


def style_score(tags: dict, weights: dict) -> float:
    return sum(weights.get(k, 0.0) * (1 if v else 0) for k, v in tags.items())


def pick_biased_move(board: chess.Board, engine: chess.engine.SimpleEngine, weights: dict):
    infos = engine.analyse(board, chess.engine.Limit(depth=CANDIDATE_DEPTH), multipv=CANDIDATE_MULTIPV)
    if not isinstance(infos, list):
        infos = [infos]
    best_cp = infos[0]["score"].pov(board.turn).score(mate_score=100000)

    candidates = []
    for info in infos:
        cp = info["score"].pov(board.turn).score(mate_score=100000)
        if best_cp - cp > MAX_EVAL_LOSS_CP:
            continue
        move = info["pv"][0]
        tags = classify_move(board, move, board.turn)
        candidates.append((style_score(tags, weights), move, tags))

    if not candidates:
        move = infos[0]["pv"][0]
        return move, classify_move(board, move, board.turn)

    candidates.sort(key=lambda x: x[0], reverse=True)
    _, move, tags = candidates[0]
    return move, tags


def run_game(bot_weights: dict, bot_label: str, moves: int = 40, partner_elo: int = 2000):
    bot = chess.engine.SimpleEngine.popen_uci(SF)  # pleine puissance, biaise par re-classement
    partner = chess.engine.SimpleEngine.popen_uci(SF)
    partner.configure({"UCI_LimitStrength": True, "UCI_Elo": partner_elo})

    board = chess.Board()
    BOT_COLOR = chess.WHITE
    tracker = StyleTracker(min_baseline=10, window=8)
    move_no = 0

    while not board.is_game_over() and move_no < moves * 2:
        if is_endgame(board):
            break
        if board.turn == BOT_COLOR:
            move, tags = pick_biased_move(board, bot, bot_weights)
            tracker.add(tags)
            board.push(move)
        else:
            res = partner.play(board, chess.engine.Limit(time=0.08))
            board.push(res.move)
        move_no += 1

    bot.quit()
    partner.quit()

    print(f"\n===== Bot {bot_label} -- {len(tracker.moves)} coups analyses =====")
    print(describe(tracker.baseline_profile()))
    return tracker.baseline_profile()


def main():
    p_aggr = run_game(AGGRESSIVE_WEIGHTS, "AGGRESSIF (sacrifie/attaque)")
    p_caut = run_game(CAUTIOUS_WEIGHTS, "PRUDENT (recule/evite)")

    print("\n===== Comparaison directe (aggressif vs prudent) =====")
    keys = ["capture", "check", "hangs_material", "advances", "retreats",
            "trade_favorable", "central_square"]
    for k in keys:
        a = p_aggr.get(k, 0) * 100
        c = p_caut.get(k, 0) * 100
        print(f"{k:<20}  aggressif={a:5.1f}%   prudent={c:5.1f}%   ecart={a-c:+6.1f}pts")


if __name__ == "__main__":
    main()

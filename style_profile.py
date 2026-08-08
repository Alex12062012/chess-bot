"""
Profil de style comportemental de l'adversaire, calcule sur l'ouverture + le milieu de partie
(la fin de partie -- materiel non-pion faible des deux cotes -- est exclue de la collecte).

Deux etages :

1. TAGS PAR COUP (classify_move) : deduits directement du plateau, aucun appel moteur, donc
   rapide et deterministe. Volontairement detaille : type de piece qui bouge, resultat de
   l'echange si capture, echec, materiel laisse en prise (proxy de sacrifice), avancee/retrait,
   developpement, roque, sortie de dame precoce, occupation du centre, pions doubles crees.

2. NOTE DE CORRESPONDANCE 0-1 (StyleTracker) : PAS une comparaison a un joueur externe -- une
   comparaison du style RECENT de l'adversaire (les WINDOW derniers coups) au style ETABLI
   (tout ce qui a ete observe avant cette fenetre). Sert a detecter un changement de comportement
   en cours de partie. Ne demarre que lorsque le profil de reference a assez de coups pour ne pas
   etre du bruit pur (MIN_BASELINE), pas a un moment fixe de la partie -- c'est le bot qui juge
   l'echantillon suffisant, comme demande.

Limite assumee : "hangs_material" est une heuristique de sacrifice/gaffe, pas une verification de
compensation positionnelle reelle (ca demanderait de rappeler le moteur, comme pour le module ELO).
La note de similarite est une moyenne des ecarts absolus de taux entre les deux fenetres -- simple
et lisible, mais pas un test statistique rigoureux (pas de p-value, pas d'intervalle de confiance).
"""

import os
import chess
import chess.engine

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SF = ["node", os.path.join(SCRIPT_DIR, "stockfish", "stockfish-18-lite-single.js")]

VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0,
}

TAG_LABELS = {
    "capture": "Taux de captures",
    "trade_even": "  dont echanges equilibres",
    "trade_favorable": "  dont captures avantageuses (petite piece prend grosse)",
    "trade_unfavorable": "  dont captures 'chères' (grosse piece prend petite)",
    "check": "Echecs donnes",
    "hangs_material": "Materiel laisse en prise (proxy sacrifice/gaffe)",
    "advances": "Coups vers le camp adverse",
    "retreats": "Coups en retrait",
    "castles": "Roques",
    "develops_minor": "Developpement de piece mineure",
    "queen_move_early": "Sorties de dame precoces (< coup 7)",
    "central_square": "Coups vers une case centrale (d4/d5/e4/e5)",
    "creates_doubled_pawn": "Coups qui doublent un pion",
    "pawn_move": "Coups de pion",
    "knight_move": "Coups de cavalier",
    "bishop_move": "Coups de fou",
    "rook_move": "Coups de tour",
    "queen_move": "Coups de dame",
    "king_move": "Coups de roi (hors roque)",
}


def non_pawn_material(board: chess.Board, color: chess.Color) -> int:
    return sum(len(board.pieces(pt, color)) * VALUES[pt]
               for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN))


def is_endgame(board: chess.Board, threshold: int = 13) -> bool:
    return non_pawn_material(board, chess.WHITE) <= threshold and \
           non_pawn_material(board, chess.BLACK) <= threshold


def doubled_pawn_count(board: chess.Board, color: chess.Color) -> int:
    files = [chess.square_file(sq) for sq in board.pieces(chess.PAWN, color)]
    return sum(max(0, files.count(f) - 1) for f in set(files))


HOME_SQUARES_MINOR = {
    chess.WHITE: {chess.B1, chess.C1, chess.F1, chess.G1},
    chess.BLACK: {chess.B8, chess.C8, chess.F8, chess.G8},
}


def classify_move(board: chess.Board, move: chess.Move, color: chess.Color) -> dict:
    """board = position AVANT le coup. Retourne les tags du coup joue par `color`."""
    moving_piece = board.piece_at(move.from_square)
    pt = moving_piece.piece_type
    is_capture = board.is_capture(move)

    trade_even = trade_favorable = trade_unfavorable = False
    if is_capture:
        if board.is_en_passant(move):
            captured_value = VALUES[chess.PAWN]
        else:
            captured = board.piece_at(move.to_square)
            captured_value = VALUES.get(captured.piece_type, 0) if captured else 0
        moving_value = VALUES.get(pt, 0)
        diff = captured_value - moving_value
        trade_even = abs(diff) <= 1
        trade_favorable = diff > 1
        trade_unfavorable = diff < -1

    doubled_before = doubled_pawn_count(board, color)

    after = board.copy()
    after.push(move)
    check = after.is_check()

    hangs_material = False
    attackers = after.attackers(not color, move.to_square)
    if attackers:
        min_attacker_value = min(VALUES.get(after.piece_at(sq).piece_type, 0) for sq in attackers)
        moving_value = VALUES.get(pt, 0)
        defenders = after.attackers(color, move.to_square)
        hangs_material = (min_attacker_value <= moving_value) and not defenders

    to_rank = chess.square_rank(move.to_square)
    from_rank = chess.square_rank(move.from_square)
    if color == chess.WHITE:
        advances = to_rank >= 4
        retreats = to_rank < from_rank
    else:
        advances = to_rank <= 3
        retreats = to_rank > from_rank

    fullmove_no = board.fullmove_number
    return {
        "capture": is_capture,
        "trade_even": trade_even,
        "trade_favorable": trade_favorable,
        "trade_unfavorable": trade_unfavorable,
        "check": check,
        "hangs_material": hangs_material,
        "advances": advances,
        "retreats": retreats,
        "castles": board.is_castling(move),
        "develops_minor": pt in (chess.KNIGHT, chess.BISHOP) and move.from_square in HOME_SQUARES_MINOR[color],
        "queen_move_early": pt == chess.QUEEN and fullmove_no < 7,
        "central_square": move.to_square in (chess.D4, chess.D5, chess.E4, chess.E5),
        "creates_doubled_pawn": pt == chess.PAWN and doubled_pawn_count(after, color) > doubled_before,
        "pawn_move": pt == chess.PAWN,
        "knight_move": pt == chess.KNIGHT,
        "bishop_move": pt == chess.BISHOP,
        "rook_move": pt == chess.ROOK,
        "queen_move": pt == chess.QUEEN,
        "king_move": pt == chess.KING and not board.is_castling(move),
    }


def profile_of(tagged_moves: list) -> dict:
    n = len(tagged_moves)
    if n == 0:
        return {}
    keys = tagged_moves[0].keys()
    return {k: sum(t[k] for t in tagged_moves) / n for k in keys}


def similarity(profile_a: dict, profile_b: dict) -> float:
    """1 - ecart moyen absolu entre deux profils. 1 = identiques, 0 = opposes sur tout."""
    if not profile_a or not profile_b:
        return None
    keys = profile_a.keys()
    mean_abs_diff = sum(abs(profile_a[k] - profile_b[k]) for k in keys) / len(keys)
    return max(0.0, 1.0 - mean_abs_diff)


class StyleTracker:
    """Accumule les coups de l'adversaire et calcule, a partir du moment ou il y a assez de
    donnees, une note 0-1 comparant chaque nouvelle fenetre de coups au style etabli avant elle."""

    def __init__(self, min_baseline: int = 15, window: int = 10):
        self.min_baseline = min_baseline
        self.window = window
        self.moves = []

    def add(self, tags: dict):
        self.moves.append(tags)

    def ready(self) -> bool:
        return len(self.moves) >= self.min_baseline + self.window

    def current_score(self):
        """Retourne (score 0-1, profil_baseline, profil_fenetre) ou (None, None, None) si pas assez de donnees."""
        if not self.ready():
            return None, None, None
        baseline_moves = self.moves[:-self.window]
        window_moves = self.moves[-self.window:]
        p_base = profile_of(baseline_moves)
        p_win = profile_of(window_moves)
        return similarity(p_base, p_win), p_base, p_win

    def baseline_profile(self) -> dict:
        return profile_of(self.moves)


def describe(profile: dict) -> str:
    if not profile:
        return "Pas assez de coups pour un profil."
    lines = []
    for key, label in TAG_LABELS.items():
        if key in profile:
            lines.append(f"{label:<55}: {profile[key]*100:5.1f}%")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Profil de style (ouverture+milieu) + note de correspondance.")
    parser.add_argument("--elo", type=int, default=1800, help="ELO impose a l'adversaire simule.")
    parser.add_argument("--moves", type=int, default=50, help="Nombre de coups pleins max.")
    parser.add_argument("--min-baseline", type=int, default=15, help="Coups mini avant de calculer une note.")
    parser.add_argument("--window", type=int, default=10, help="Taille de la fenetre recente comparee au style etabli.")
    args = parser.parse_args()

    target_elo = max(1320, min(3190, args.elo))
    partner_elo = min(3190, target_elo + 100)

    opponent = chess.engine.SimpleEngine.popen_uci(SF)
    opponent.configure({"UCI_LimitStrength": True, "UCI_Elo": target_elo})
    partner = chess.engine.SimpleEngine.popen_uci(SF)
    partner.configure({"UCI_LimitStrength": True, "UCI_Elo": partner_elo})

    board = chess.Board()
    OPP = chess.WHITE
    tracker = StyleTracker(min_baseline=args.min_baseline, window=args.window)
    move_no = 0
    endgame_reached = False

    print(f"Adversaire simule a {target_elo} ELO. Note de correspondance dispo a partir de "
          f"{args.min_baseline + args.window} coups (baseline {args.min_baseline} + fenetre {args.window}).\n")

    while not board.is_game_over() and move_no < args.moves * 2:
        mover = board.turn
        if is_endgame(board):
            endgame_reached = True
            break

        if mover == OPP:
            result = opponent.play(board, chess.engine.Limit(time=0.08))
            move = result.move
            tags = classify_move(board, move, mover)
            tracker.add(tags)
            board.push(move)

            score, _, _ = tracker.current_score()
            n = len(tracker.moves)
            if score is not None:
                print(f"coup {n:>2} ({move.uci():<5})  note de correspondance au style etabli = {score:.2f}")
            else:
                remaining = (args.min_baseline + args.window) - n
                print(f"coup {n:>2} ({move.uci():<5})  (pas encore assez de donnees, "
                      f"{remaining} coup(s) avant la 1ere note)")
        else:
            result = partner.play(board, chess.engine.Limit(time=0.08))
            board.push(result.move)
        move_no += 1

    opponent.quit()
    partner.quit()

    print(f"\n--- Profil de style final ({len(tracker.moves)} coups d'ouverture/milieu"
          f"{', fin de partie atteinte' if endgame_reached else ''}) ---")
    print(describe(tracker.baseline_profile()))


if __name__ == "__main__":
    main()

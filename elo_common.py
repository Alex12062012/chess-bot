"""
Fonctions communes a elo_estimator.py et calibrate.py.

Metrique retenue : "expected points lost" (EL) plutot que l'ACPL brut, sur la recommandation
du projet open source ianfab/chess-analysis (https://github.com/ianfab/chess-analysis), qui
documente les faiblesses connues de l'ACPL brut :
  - un seul coup catastrophique peut ecraser toute la moyenne (poids non borne),
  - deux positions avec le meme delta de centipawns ne representent pas la meme gravite
    d'erreur selon qu'on est proche de l'equilibre ou dans une position deja tres decidee.

La solution standard (utilisee par Lichess pour son "accuracy%") est de convertir chaque
evaluation en pourcentage de victoire via une sigmoide, puis de mesurer la perte en points
de pourcentage plutot qu'en centipawns. Un coup qui fait passer une position de +900cp a
+600cp (toujours totalement gagnante) perd presque 0 point de %, alors qu'un coup qui fait
passer +50cp a -50cp (equilibre -> perdant) perd beaucoup -- ce qui correspond a l'intuition
humaine de la gravite d'une erreur.
"""

import chess


def win_percent(cp: int) -> float:
    """Formule de Lichess : centipawns (POV du joueur) -> % de chances de gagner (0-100)."""
    return 50 + 50 * (2 / (1 + pow(2.718281828, -0.00368208 * cp)) - 1)


def cp_capped(score: chess.engine.PovScore, color: chess.Color, cap: int = 1000) -> int:
    val = score.pov(color).score(mate_score=cap)
    return max(-cap, min(cap, val))


def expected_loss(score_before: chess.engine.PovScore, score_after: chess.engine.PovScore,
                   color: chess.Color) -> float:
    """Perte en points de % de victoire (0-100) entre avant et apres le coup, POV du joueur qui a bouge."""
    wp_before = win_percent(cp_capped(score_before, color))
    wp_after = win_percent(cp_capped(score_after, color))
    return max(0.0, wp_before - wp_after)

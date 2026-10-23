# chess-bot

Un **prototype de bot d'échecs « malin »**. Il ne cherche pas seulement le meilleur coup, il essaie aussi de **jouer contre l'adversaire qu'il a en face** :

1. **Il estime l'ELO de l'adversaire en direct**, à partir de la qualité de ses coups. C'est le même principe que la FIDE (modèle de K. Regan) ou le détecteur de triche de Lichess, en simplifié.
2. **Il tend des pièges aux joueurs faibles** : il préfère les coups où l'adversaire n'a qu'une bonne réponse. Plus l'adversaire est faible, plus ce critère compte. Contre un joueur fort, il revient au coup le plus solide.
3. **Il dresse un profil de style** de l'adversaire en ouverture et en milieu de partie : captures, échecs, matériel laissé en prise, développement… Il s'en sert en fin de partie pour départager des coups proches.

Le coup final est tiré au sort parmi les meilleurs, avec une « température ». À 0, il joue toujours le meilleur coup ; plus elle est haute, plus il varie.

## Exemple (test réel)

```
=== Effet de la temperature (20 tirages a T=0.8, adversaire 2000 ELO) ===
  c2c3   choisi 11/20 fois
  d2d3   choisi 6/20 fois
  a2a4   choisi 2/20 fois
  h2h3   choisi 1/20 fois
```

## Les fichiers

| Fichier | Rôle |
|---|---|
| `move_selector.py` | choix du coup : qualité, piège selon l'ELO, bonus de style, température |
| `elo_estimator.py` | estimation de l'ELO adverse coup après coup |
| `style_profile.py` | tags de chaque coup et note de « changement de style » |
| `elo_common.py` | formules communes (% de victoire façon Lichess, perte attendue) |
| `calibrate.py`, `calibration_data.csv` | courbe ELO ↔ perte moyenne, mesurée sur Stockfish bridé de 1320 à 3190 ELO |
| `ladder_test.py`, `ladder_state_*.txt` | parties du bot contre Stockfish à différents ELO, qu'on peut reprendre si elles s'arrêtent |
| `bot_vs_max_stockfish.py` | le bot contre Stockfish à pleine puissance |
| `elo_of_bot.py`, `elo_of_bot_chunk.py`, `bot_elo_depth20.csv` | mesure de la perte de qualité causée par les pièges |
| `game_runner.py` | 10 parties avec et sans le bonus, pour comparer |
| `test_move_selector.py`, `test_styles.py` | tests de bon sens (le piège change-t-il le coup ? le profil voit-il la différence entre un bot agressif et un bot prudent ?) |
| `stockfish/` | Stockfish 18 lite (WebAssembly), lancé avec Node.js |

## Lancer

Il faut **Python 3** avec [python-chess](https://python-chess.readthedocs.io), et **Node.js** pour faire tourner Stockfish.

```bash
pip install chess
python test_move_selector.py          # le piège et la température en action
python test_styles.py                 # le profil de style
python ladder_test.py 1900            # une partie contre Stockfish à 1900 ELO (relancer jusqu'à « TERMINE »)
```

## Limites (écrites aussi dans le code)

- La recherche de piège ne regarde qu'**une seule** réponse adverse.
- Le bonus de style est une heuristique, pas une prédiction validée.
- La calibration ELO s'arrête à 3190 : au-delà, l'estimation est plafonnée.

C'est un prototype pour expérimenter, pas un moteur d'échecs fiable.

Stockfish est un logiciel libre sous licence GPL-3.0 (voir `stockfish/LICENSE.txt`).

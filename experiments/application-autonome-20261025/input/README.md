# Projet de validation du parcours applicatif

Programme C++ de somme des nombres premiers jusqu'à la borne entière fournie.
Entrées valides : 0 à 200000 inclus. Une entrée hors de ces bornes renvoie le code 2.
La sortie valide est la somme décimale suivie d'un saut de ligne.

Compilation : `g++ -O2 -std=c++17 main.cpp -o program`.
Vérification : `python3 tests/check.py ./program`.
Mesure : `./program 20000`.
Seul `main.cpp` peut être modifié. Les tests et les arguments restent fixes.

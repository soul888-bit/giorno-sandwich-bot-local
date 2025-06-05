# Giorno Sandwich Bot (Local)

## Étapes pour faire tourner le bot en local :

1. Assure-toi d'avoir Python installé (version 3.10+).
2. Ouvre un terminal dans ce dossier.
3. Crée un fichier `.env` en copiant le contenu de `.env.example` et en renseignant tes valeurs.
4. Installe les dépendances :

    pip install -r requirements.txt

5. Lance le bot (démarre un serveur FastAPI sur le port 8000) :

    python main.py

   # Optionnel : tu peux aussi utiliser directement uvicorn
   
    uvicorn main:app --reload

Tu peux ensuite interagir avec lui sur Telegram avec la commande /start.

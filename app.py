import os
import json
import urllib.request
import urllib.error

from flask import Flask, request, render_template_string

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024

GEMINI_MODEL = "gemini-3.8-flash"

PAGE = r"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0a0820">

<title>GENIUS APP AI</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    padding: 20px 14px;
    background: #0a0820;
    color: white;
    font-family: Arial, sans-serif;
}

.container {
    max-width: 760px;
    margin: 0 auto;
}

header {
    text-align: center;
    padding: 24px 8px;
}

.logo {
    font-size: 42px;
}

h1 {
    color: #c5a3ff;
    font-size: 29px;
    margin: 12px 0;
}

.subtitle {
    color: #c4bddb;
    line-height: 1.6;
}

.card {
    background: #191537;
    border: 1px solid #37305e;
    border-radius: 18px;
    padding: 20px;
    margin: 18px 0;
}

label {
    display: block;
    margin: 18px 0 9px;
    font-weight: bold;
}

textarea, select {
    width: 100%;
    border: 1px solid #554786;
    border-radius: 10px;
    padding: 14px;
    background: #0e0b29;
    color: white;
    font-size: 16px;
}

textarea {
    min-height: 160px;
    resize: vertical;
}

button {
    width: 100%;
    border: none;
    border-radius: 12px;
    padding: 16px 12px;
    margin-top: 20px;
    background: #7c00ff;
    color: white;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
}

button:disabled {
    opacity: 0.6;
}

.note {
    color: #c4bddb;
    font-size: 13px;
    line-height: 1.7;
}

.result {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    line-height: 1.65;
    font-size: 15px;
}

.success {
    color: #83ffd0;
}

.error {
    color: #ffaaa9;
}

footer {
    text-align: center;
    color: #aaa1ca;
    font-size: 12px;
    padding: 20px 8px;
}
</style>
</head>

<body>
<div class="container">

<header>
    <div class="logo">🧠</div>
    <h1>GENIUS APP AI</h1>
    <p class="subtitle">
        Décris ton idée. L'intelligence artificielle t'aide
        à préparer ton projet.
    </p>
</header>

<section class="card">
    <form method="POST" action="/" onsubmit="document.getElementById('submit').disabled=true; document.getElementById('submit').textContent='⏳ L’IA RÉFLÉCHIT...';">

        <label for="description">
            ✍️ Décris l'application que tu veux créer
        </label>

        <textarea
            id="description"
            name="description"
            maxlength="12000"
            required
            placeholder="Exemple : Je veux créer un jeu de football en 3D avec deux équipes de 11 joueurs, un ballon, des buts et un bouton pour tirer."
        >{{ description }}</textarea>

        <label for="platform">
            📱 Choisis la plateforme
        </label>

        <select id="platform" name="platform">
            <option value="Android" {% if platform == "Android" %}selected{% endif %}>
                Application Android (APK)
            </option>

            <option value="Web" {% if platform == "Web" %}selected{% endif %}>
                Application Web
            </option>
        </select>

        <button id="submit" type="submit">
            🚀 DEMANDER À L'IA
        </button>

    </form>

    <p class="note">
        Première version expérimentale : l'IA propose une architecture
        et du code. La compilation automatique des APK sera ajoutée
        dans une prochaine étape.
    </p>
</section>

{% if result %}
<section class="card">
    <h2 class="success">✅ Réponse de GENIUS APP AI</h2>
    <div class="result">{{ result }}</div>
</section>
{% endif %}

{% if error %}
<section class="card">
    <h2 class="error">⚠️ Un problème est survenu</h2>
    <div class="result">{{ error }}</div>
</section>
{% endif %}

<footer>
    GENIUS APP AI — Créons tes idées, étape par étape.
</footer>

</div>
</body>
</html>
"""


def ask_gemini(description, platform):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "La clé API Gemini n'est pas configurée sur le serveur."
        )

    if platform == "Android":
        instructions = """
Tu es l'assistant technique de GENIUS APP AI.
L'utilisateur veut créer une application Android.

Réponds en français simple et organise ta réponse ainsi :
1. Résumé de l'application.
2. Fonctionnalités principales.
3. Technologies et architecture recommandées.
4. Organisation des fichiers du projet.
5. Premier exemple de code utile et cohérent.
6. Étapes suivantes pour construire et tester le projet.

Fournis du code lisible et indique le nom du fichier auquel il correspond.
Ne prétends jamais qu'un APK a été compilé ou testé si ce n'est pas vrai.
Si la demande est trop grande, propose une première version réalisable.
"""
    else:
        instructions = """
Tu es l'assistant technique de GENIUS APP AI.
L'utilisateur veut créer une application Web.

Réponds en français simple et organise ta réponse ainsi :
1. Résumé de l'application.
2. Fonctionnalités principales.
3. Technologies et architecture recommandées.
4. Organisation des fichiers du projet.
5. Premier exemple de code utile et cohérent.
6. Étapes suivantes pour construire et tester le projet.

Fournis du code lisible et indique le nom du fichier auquel il correspond.
Ne prétends jamais qu'un projet a été testé si ce n'est pas vrai.
Si la demande est trop grande, propose une première version réalisable.
"""

    payload = {
        "systemInstruction": {
            "parts": [
                {"text": instructions}
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": description}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 4096
        }
    }

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + GEMINI_MODEL
        + ":generateContent"
    )

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")

        if exc.code == 400:
            raise RuntimeError(
                "La requête a été refusée. Vérifie la description "
                "et le modèle Gemini configuré."
            )

        if exc.code == 401 or exc.code == 403:
            raise RuntimeError(
                "Google a refusé l'accès à l'API. Vérifie la clé "
                "API et les autorisations du projet."
            )

        if exc.code == 429:
            raise RuntimeError(
                "La limite de requêtes Gemini est atteinte, "
                "ou le quota disponible est épuisé. Réessaie plus tard."
            )

        print("Erreur API Gemini :", exc.code, details[:1500])

        raise RuntimeError(
            "Le service Gemini a rencontré une erreur HTTP "
            + str(exc.code)
            + ". Consulte les journaux du serveur pour plus de détails."
        )

    except urllib.error.URLError:
        raise RuntimeError(
            "Impossible de joindre Google Gemini. Vérifie la connexion "
            "du serveur et réessaie."
        )

    candidates = data.get("candidates", [])

    if not candidates:
        raise RuntimeError(
            "Gemini n'a pas renvoyé de réponse exploitable. Réessaie."
        )

    parts = candidates[0].get("content", {}).get("parts", [])

    answer = "\n".join(
        part["text"]
        for part in parts
        if isinstance(part, dict) and "text" in part
    ).strip()

    if not answer:
        raise RuntimeError(
            "La réponse de Gemini est vide. Réessaie avec une autre demande."
        )

    return answer


@app.route("/", methods=["GET", "POST"])
def home():
    description = ""
    platform = "Android"
    result = ""
    error = ""

    if request.method == "POST":
        description = request.form.get("description", "").strip()
        platform = request.form.get("platform", "Android").strip()

        if platform not in ("Android", "Web"):
            platform = "Android"

        if not description:
            error = "Décris ton application avant de continuer."

        elif len(description) > 12000:
            error = "La description est trop longue."

        else:
            try:
                result = ask_gemini(description, platform)

            except RuntimeError as exc:
                error = str(exc)

            except Exception:
                app.logger.exception("Erreur inattendue")
                error = (
                    "Une erreur inattendue est survenue. "
                    "Réessaie dans quelques instants."
                )

    return render_template_string(
        PAGE,
        description=description,
        platform=platform,
        result=result,
        error=error
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

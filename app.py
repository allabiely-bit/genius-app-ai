from flask import Flask, request, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GENIUS APP AI</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #0a0820;
            color: white;
        }
        header {
            text-align: center;
            padding: 35px 15px 20px;
        }
        .logo {
            font-size: 38px;
            margin-bottom: 10px;
        }
        h1 {
            color: #b99aff;
            font-size: 28px;
            margin: 10px 0;
        }
        .subtitle {
            color: #c8c4db;
            line-height: 1.6;
        }
        main {
            max-width: 650px;
            margin: 15px auto;
            padding: 20px;
        }
        .card {
            background: #191537;
            border: 1px solid #393064;
            border-radius: 18px;
            padding: 22px;
        }
        label {
            display: block;
            font-weight: bold;
            margin: 18px 0 10px;
        }
        textarea, select {
            width: 100%;
            padding: 14px;
            border-radius: 10px;
            border: 1px solid #55468b;
            background: #0e0b27;
            color: white;
            font-size: 16px;
        }
        textarea {
            min-height: 140px;
            resize: vertical;
        }
        button {
            width: 100%;
            margin-top: 22px;
            padding: 16px;
            border: none;
            border-radius: 12px;
            background: #7c00ff;
            color: white;
            font-size: 17px;
            font-weight: bold;
        }
        .result {
            margin-top: 20px;
            padding: 16px;
            border-radius: 12px;
            background: #102d38;
            border: 1px solid #35cfff;
            overflow-wrap: anywhere;
        }
        .note {
            color: #c8c4db;
            font-size: 13px;
            line-height: 1.6;
            margin-top: 20px;
        }
        footer {
            text-align: center;
            color: #aaa3c8;
            padding: 25px 10px;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">🧠</div>
        <h1>GENIUS APP AI</h1>
        <p class="subtitle">
            Imagine ton application.<br>
            Prépare-toi à la construire.
        </p>
    </header>

    <main>
        <section class="card">
            <h2>✨ Crée ton application</h2>
            <p>Décris simplement l'application que tu veux créer.</p>

            <form method="POST">
                <label for="description">
                    1. Quelle application veux-tu ?
                </label>
                <textarea
                    id="description"
                    name="description"
                    placeholder="Exemple : Je veux créer un jeu de football avec des équipes, un terrain en 3D et des matchs."
                    required
                >{{ description }}</textarea>

                <label for="platform">
                    2. Choisis la plateforme
                </label>
                <select id="platform" name="platform">
                    <option value="Android"
                        {% if platform == "Android" %}selected{% endif %}>
                        Application Android (APK)
                    </option>
                    <option value="Web"
                        {% if platform == "Web" %}selected{% endif %}>
                        Site web
                    </option>
                </select>

                <button type="submit">
                    🚀 PRÉPARER MON PROJET
                </button>
            </form>

            {% if submitted %}
            <div class="result">
                <h3>✅ Ton projet est enregistré dans cette session !</h3>
                <p><strong>Plateforme :</strong> {{ platform }}</p>
                <p><strong>Description :</strong> {{ description }}</p>
                <p>
                    <strong>Prochaine étape :</strong>
                    connecter le moteur IA pour générer le code,
                    puis mettre en place la compilation et les tests.
                </p>
            </div>
            {% endif %}

            <p class="note">
                GENIUS APP AI — Première version expérimentale.
                La génération réelle du code, la compilation APK
                et les tests automatiques seront ajoutés ensuite.
            </p>
        </section>
    </main>

    <footer>
        GENIUS APP AI © 2026 — Construisons tes idées.
    </footer>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def home():
    description = ""
    platform = "Android"
    submitted = False

    if request.method == "POST":
        description = request.form.get("description", "").strip()
        platform = request.form.get("platform", "Android")

        if description:
            submitted = True

    return render_template_string(
        HTML,
        description=description,
        platform=platform,
        submitted=submitted
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)

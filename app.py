
import os
import re
import io
import json
import time
import uuid
import zipfile
import threading
from flask import Flask, request, render_template_string, send_file
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
).strip()

MAX_FILES = 40
MAX_TOTAL_SIZE = 1500000
MAX_DESCRIPTION_LENGTH = 5000
BUNDLE_TTL = 3600

bundles = {}
bundles_lock = threading.Lock()


HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport"
content="width=device-width, initial-scale=1.0">
<title>GENIUS APP AI</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    padding: 18px;
    background: #0a0820;
    color: white;
    font-family: Arial, sans-serif;
}

.container {
    max-width: 760px;
    margin: auto;
}

header {
    text-align: center;
    padding: 22px 10px;
}

.logo {
    font-size: 42px;
}

h1 {
    color: #b69aff;
    font-size: 28px;
    margin: 12px 0;
}

.subtitle {
    color: #c8c4df;
    line-height: 1.6;
}

.card {
    background: #191537;
    border: 1px solid #38305e;
    border-radius: 18px;
    padding: 20px;
    margin: 18px 0;
}

label {
    display: block;
    font-weight: bold;
    margin: 16px 0 9px;
    color: #e5ddff;
}

textarea, select {
    width: 100%;
    border: 1px solid #51457e;
    background: #0e0b28;
    color: white;
    border-radius: 10px;
    padding: 14px;
    font-size: 16px;
}

textarea {
    min-height: 150px;
    resize: vertical;
}

button, .download {
    display: block;
    width: 100%;
    padding: 15px;
    border: none;
    border-radius: 12px;
    background: #7c00ff;
    color: white;
    font-size: 16px;
    font-weight: bold;
    text-align: center;
    text-decoration: none;
    margin-top: 18px;
    cursor: pointer;
}

button:disabled {
    opacity: 0.6;
}

.secondary {
    background: #252044;
    border: 1px solid #6753a5;
}

.small {
    font-size: 13px;
    color: #bcb5dc;
    line-height: 1.6;
}

.success {
    color: #70f2bc;
    line-height: 1.6;
}

.error {
    color: #ff9aab;
    line-height: 1.6;
    overflow-wrap: anywhere;
}

.file {
    background: #100d2b;
    border: 1px solid #39315e;
    border-radius: 9px;
    padding: 12px;
    margin: 8px 0;
    overflow-wrap: anywhere;
}

.file-name {
    color: #81e5ff;
    font-weight: bold;
}

.file-size {
    color: #aaa2ce;
    font-size: 12px;
    margin-top: 5px;
}

pre {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    color: #ded7ff;
    line-height: 1.6;
    font-family: Arial, sans-serif;
}

footer {
    text-align: center;
    color: #827ba7;
    font-size: 12px;
    padding: 20px 0;
}
</style>
</head>

<body>
<div class="container">

<header>
    <div class="logo">🧠</div>
    <h1>GENIUS APP AI</h1>
    <div class="subtitle">
        Décris ton idée. Génère ton projet.<br>
        Construis tes applications avec l'IA.
    </div>
</header>

<div class="card">
    <h2>🚀 Créons ton projet</h2>

    <form method="POST" action="/"
          onsubmit="document.getElementById('submit').disabled=true;
          document.getElementById('submit').innerText='⏳ GÉNÉRATION EN COURS...';">

        <label for="description">
            1. Décris l'application que tu veux créer
        </label>

        <textarea id="description" name="description"
        maxlength="5000" required
        placeholder="Exemple : crée une application Android de gestion des dépenses avec un tableau de bord, l'ajout de revenus et de dépenses, des statistiques et une sauvegarde des données. Je veux une interface moderne en français.">{{ description|default('') }}</textarea>

        <label for="platform">
            2. Choisis la plateforme
        </label>

        <select id="platform" name="platform">
            <option value="android"
            {% if platform == 'android' %}selected{% endif %}>
                📱 Application Android (Kotlin)
            </option>

            <option value="web"
            {% if platform == 'web' %}selected{% endif %}>
                🌐 Application Web
            </option>
        </select>

        <button id="submit" type="submit">
            ✨ GÉNÉRER MON PROJET
        </button>
    </form>

    <p class="small">
        GENIUS APP AI transforme ta description en fichiers
        organisés. La compilation automatique en APK sera
        ajoutée dans une prochaine évolution.
    </p>
</div>

{% if error %}
<div class="card">
    <h3 class="error">⚠️ Un problème est survenu</h3>
    <p class="error">{{ error }}</p>
    <p class="small">
        Vérifie ta connexion Internet et réessaie.
        Ne partage jamais ta clé API.
    </p>
</div>
{% endif %}

{% if project %}
<div class="card">
    <h2 class="success">✅ Projet généré !</h2>

    <h3>{{ project.project_name }}</h3>

    <p>{{ project.summary }}</p>

    <p class="small">
        {{ project.files|length }} fichier(s) généré(s)
    </p>

    <a class="download"
       href="/download/{{ download_token }}">
       📦 TÉLÉCHARGER LE PROJET ZIP
    </a>

    <h3>📂 Fichiers du projet</h3>

    {% for file in project.files %}
    <div class="file">
        <div class="file-name">
            📄 {{ file.path }}
        </div>
        <div class="file-size">
            {{ file.size }} octets
        </div>
    </div>
    {% endfor %}

    <h3>📘 Instructions</h3>
    <pre>{{ project.instructions }}</pre>

    <p class="small">
        Le ZIP contient les fichiers générés. Il faudra
        vérifier le projet et le compiler avant de pouvoir
        installer une application Android.
    </p>
</div>
{% endif %}

<footer>
    GENIUS APP AI • Imagine • Crée • Construis
</footer>

</div>
</body>
</html>
"""


def clean_expired_bundles():
    now = time.time()

    with bundles_lock:
        expired = [
            token for token, item in bundles.items()
            if now - item["created"] > BUNDLE_TTL
        ]

        for token in expired:
            bundles.pop(token, None)

        while len(bundles) > 5:
            oldest = min(
                bundles,
                key=lambda token: bundles[token]["created"]
            )
            bundles.pop(oldest, None)


def safe_project_path(path):
    if not isinstance(path, str):
        return None

    path = path.strip().replace("\\\\", "/")

    if not path or len(path) > 200:
        return None

    if path.startswith("/") or path.startswith("~"):
        return None

    if re.match(r"^[A-Za-z]:", path):
        return None

    parts = path.split("/")

    if any(part in ("", ".", "..") for part in parts):
        return None

    if any(
        part.startswith(".")
        and part.lower() in (
            ".env",
            ".git",
            ".ssh",
            ".aws"
        )
        for part in parts
    ):
        return None

    filename = parts[-1].lower()

    if filename in (
        ".env",
        ".env.local",
        ".env.production",
        "id_rsa",
        "id_ed25519"
    ):
        return None

    return "/".join(parts)


def extract_json(text):
    text = text.strip()

    text = re.sub(
        r"^```(?:json)?\\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(r"\\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end <= start:
        raise ValueError(
            "L'IA n'a pas renvoyé un projet au format attendu."
        )

    return json.loads(text[start:end + 1])


def generate_project(description, platform):
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "La clé GEMINI_API_KEY est absente des variables "
            "d'environnement de Render."
        )

    if platform == "android":
        platform_rules = """
PLATEFORME ANDROID :
- Utilise Kotlin et Android Gradle.
- Génère un vrai squelette de projet Android.
- Inclus settings.gradle.kts.
- Inclus build.gradle.kts à la racine.
- Inclus app/build.gradle.kts.
- Inclus app/src/main/AndroidManifest.xml.
- Inclus le code Kotlin nécessaire.
- Inclus les ressources nécessaires dans res si utile.
- Inclus un README.md avec les étapes de compilation.
- Utilise des versions de dépendances compatibles entre elles.
- N'affirme pas qu'une compilation a réussi : aucun build
  n'a encore été exécuté.
- Le projet doit être autonome autant que possible.
"""
    else:
        platform_rules = """
PLATEFORME WEB :
- Génère une application Web complète et organisée.
- Inclus les fichiers HTML, CSS et JavaScript nécessaires.
- Inclus README.md avec les instructions de lancement.
- Si un serveur est nécessaire, inclus ses fichiers de
  configuration et les dépendances nécessaires.
- Préfère une solution simple à lancer.
"""

    prompt = f"""
Tu es GENIUS APP AI, un ingénieur logiciel expérimenté.

MISSION :
Créer un projet logiciel complet à partir de cette demande :

{description}

PLATEFORME :
{platform}

{platform_rules}

RÈGLES IMPORTANTES :
1. Génère le plus possible un projet fonctionnel, pas seulement
   une architecture ou quelques extraits de code.
2. Tous les fichiers doivent avoir leur contenu complet.
3. Les chemins doivent être relatifs à la racine du projet.
4. Ne mets aucun secret, mot de passe, jeton ou clé API dans
   les fichiers générés.
5. N'utilise jamais de chemin absolu ni de chemin contenant
   "..".
6. Limite le projet à {MAX_FILES} fichiers maximum.
7. Si le projet est trop grand, privilégie les fichiers
   essentiels nécessaires à son fonctionnement.
8. Les instructions doivent être en français.
9. Ne prétends pas avoir exécuté des tests ou compilé le projet.
10. Le code doit être cohérent entre les différents fichiers.

RENVOIE UNIQUEMENT UN OBJET JSON VALIDE, sans Markdown,
sans ``` et sans texte avant ou après.

Respecte exactement cette structure :

{{
  "project_name": "nom-du-projet",
  "summary": "Résumé du projet",
  "instructions": "Instructions de lancement et de compilation",
  "files": [
    {{
      "path": "README.md",
      "content": "Contenu complet du fichier"
    }}
  ]
}}
"""

    endpoint = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/"
        + GEMINI_MODEL
        + ":generateContent"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }

    data = json.dumps(payload).encode("utf-8")

    req = Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        },
        method="POST"
    )

    try:
        with urlopen(req, timeout=150) as response:
            raw = response.read().decode("utf-8")

    except HTTPError as exc:
        details = exc.read().decode(
            "utf-8", errors="replace"
        )

        if exc.code == 429:
            raise RuntimeError(
                "La limite de requêtes de l'API Gemini est "
                "atteinte. Attends un peu puis réessaie."
            )

        if exc.code in (401, 403):
            raise RuntimeError(
                "Gemini refuse la clé API ou son accès. "
                "Vérifie la configuration de Render."
            )

        if exc.code == 404:
            raise RuntimeError(
                "Le modèle Gemini configuré n'est pas "
                "disponible. Vérifie le nom du modèle."
            )

        print("Erreur Gemini HTTP", exc.code, details[:1000])

        raise RuntimeError(
            "Le service Gemini a renvoyé une erreur HTTP "
            + str(exc.code)
            + ". Réessaie plus tard."
        )

    except (URLError, TimeoutError):
        raise RuntimeError(
            "Le service Gemini ne répond pas actuellement. "
            "Vérifie la connexion et réessaie."
        )

    try:
        response_data = json.loads(raw)

        candidates = response_data.get("candidates", [])

        if not candidates:
            raise ValueError("Aucune réponse de Gemini.")

        parts = candidates[0].get(
            "content", {}
        ).get("parts", [])

        answer = "".join(
            part.get("text", "")
            for part in parts
            if isinstance(part.get("text"), str)
        )

        if not answer.strip():
            raise ValueError("La réponse de Gemini est vide.")

        project = extract_json(answer)

    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise RuntimeError(
            "La réponse de l'IA n'a pas pu être convertie "
            "en projet. Essaie une description plus simple."
        )

    if not isinstance(project, dict):
        raise RuntimeError(
            "Le format du projet généré est incorrect."
        )

    raw_files = project.get("files")

    if not isinstance(raw_files, list) or not raw_files:
        raise RuntimeError(
            "Aucun fichier n'a été fourni par l'IA."
        )

    if len(raw_files) > MAX_FILES:
        raw_files = raw_files[:MAX_FILES]

    files = []
    seen_paths = set()
    total_size = 0

    for item in raw_files:
        if not isinstance(item, dict):
            continue

        path = safe_project_path(item.get("path"))
        content = item.get("content")

        if path is None or not isinstance(content, str):
            continue

        if path in seen_paths:
            continue

        content_bytes = content.encode("utf-8")

        if len(content_bytes) > MAX_TOTAL_SIZE:
            continue

        if total_size + len(content_bytes) > MAX_TOTAL_SIZE:
            break

        seen_paths.add(path)
        total_size += len(content_bytes)

        files.append({
            "path": path,
            "content": content,
            "size": len(content_bytes)
        })

    if not files:
        raise RuntimeError(
            "Les fichiers générés sont vides ou invalides. "
            "Réessaie avec une demande plus précise."
        )

    project_name = str(
        project.get("project_name", "mon-projet")
    )[:100]

    project["project_name"] = project_name
    project["summary"] = str(
        project.get("summary", "Projet généré par l'IA.")
    )[:3000]

    project["instructions"] = str(
        project.get(
            "instructions",
            "Consulte le fichier README.md."
        )
    )[:10000]

    project["files"] = files

    return project


def create_zip(project):
    memory_file = io.BytesIO()

    with zipfile.ZipFile(
        memory_file,
        mode="w",
        compression=zipfile.ZIP_DEFLATED
    ) as archive:

        for item in project["files"]:
            archive.writestr(
                item["path"],
                item["content"]
            )

    memory_file.seek(0)

    return memory_file.read()


@app.route("/", methods=["GET", "POST"])
def index():
    description = ""
    platform = "android"
    project = None
    error = None
    download_token = None

    if request.method == "POST":
        description = request.form.get(
            "description", ""
        ).strip()

        platform = request.form.get(
            "platform", "android"
        ).strip()

        if platform not in ("android", "web"):
            platform = "android"

        if not description:
            error = "Décris d'abord l'application à créer."

        elif len(description) > MAX_DESCRIPTION_LENGTH:
            error = (
                "Ta description est trop longue. "
                "Réduis-la à 5000 caractères maximum."
            )

        else:
            try:
                project = generate_project(
                    description,
                    platform
                )

                zip_data = create_zip(project)
                download_token = uuid.uuid4().hex

                with bundles_lock:
                    bundles[download_token] = {
                        "created": time.time(),
                        "data": zip_data,
                        "name": re.sub(
                            r"[^a-zA-Z0-9_-]+",
                            "-",
                            project["project_name"]
                        ).strip("-")[:60] or "mon-projet"
                    }

                clean_expired_bundles()

            except RuntimeError as exc:
                error = str(exc)

            except Exception:
                app.logger.exception(
                    "Erreur pendant la génération du projet"
                )

                error = (
                    "Une erreur inattendue est survenue. "
                    "Réessaie avec une demande plus simple."
                )

    return render_template_string(
        HTML,
        description=description,
        platform=platform,
        project=project,
        download_token=download_token,
        error=error
    )


@app.route("/download/<token>", methods=["GET"])
def download_project(token):
    with bundles_lock:
        item = bundles.get(token)

        if item is None:
            return (
                "Ce téléchargement a expiré. "
                "Génère à nouveau ton projet.",
                404
            )

        if time.time() - item["created"] > BUNDLE_TTL:
            bundles.pop(token, None)

            return (
                "Ce téléchargement a expiré. "
                "Génère à nouveau ton projet.",
                404
            )

        zip_data = item["data"]
        filename = item["name"] + ".zip"

    return send_file(
        io.BytesIO(zip_data),
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
        max_age=0
    )


@app.route("/health", methods=["GET"])
def health():
    return {
        "status": "ok",
        "application": "GENIUS APP AI"
    }


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
)

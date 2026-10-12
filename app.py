import os
import re
import io
import json
import time
import uuid
import zipfile
import threading

from flask import (
    Flask,
    request,
    render_template_string,
    send_file
)

from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


app = Flask(__name__)

GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY", ""
).strip()

GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL", "gemini-3.8-flash"
).strip()

MAX_FILES = 40
MAX_TOTAL_SIZE = 1_500_000
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

.small {
    font-size: 13px;
    color: #bcb5dc;
    line-height: 1.6;
}

.success {
    color: #70f2bc;
    line-height: 1.6;
}

.warning {
    color: #ffd580;
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
        placeholder="Exemple : crée une application Android de gestion des dépenses...">{{ description|default('') }}</textarea>

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
        Les fichiers sont contrôlés automatiquement.
        Ces contrôles ne remplacent pas une véritable
        compilation ou des tests d'exécution.
    </p>
</div>

{% if error %}
<div class="card">
    <h3 class="error">⚠️ Un problème est survenu</h3>
    <p class="error">{{ error }}</p>
    <p class="small">
        Vérifie ta connexion et réessaie lorsque le
        service sera disponible. Ne partage jamais ta clé API.
    </p>
</div>
{% endif %}

{% if project %}
<div class="card">
    <h2 class="success">✅ Projet généré</h2>

    <h3>{{ project.project_name }}</h3>

    <p>{{ project.summary }}</p>

    <p class="small">
        {{ project.files|length }} fichier(s) généré(s)
    </p>

    <h3>🔎 Contrôle automatique</h3>

    {% if project.checks.ok %}
        <p class="success">
            ✅ Les contrôles de structure sont satisfaisants.
        </p>
    {% else %}
        <p class="warning">
            ⚠️ Certains éléments attendus sont manquants.
            Le projet peut nécessiter des corrections.
        </p>
    {% endif %}

    {% for message in project.checks.messages %}
        <div class="file">{{ message }}</div>
    {% endfor %}

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
        Le rapport vérifie des éléments de structure.
        Il ne garantit pas que le code fonctionne.
        La compilation automatique sera ajoutée séparément.
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
            token
            for token, item in bundles.items()
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

    forbidden = {
        ".env",
        ".env.local",
        ".env.production",
        "id_rsa",
        "id_ed25519"
    }

    if any(part.lower() in forbidden for part in parts):
        return None

    if ".git" in [part.lower() for part in parts]:
        return None

    if ".ssh" in [part.lower() for part in parts]:
        return None

    if ".aws" in [part.lower() for part in parts]:
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


def validate_project_structure(files, platform):
    """
    Vérifie localement la structure du projet.
    Cette fonction ne contacte pas Gemini.
    """

    paths = {
        item["path"].lower()
        for item in files
    }

    messages = []
    ok = True

    if platform == "android":
        expected_groups = [
            (
                "Fichier de configuration Gradle",
                {
                    "settings.gradle",
                    "settings.gradle.kts"
                }
            ),
            (
                "Configuration Gradle principale",
                {
                    "build.gradle",
                    "build.gradle.kts"
                }
            ),
            (
                "Configuration Gradle de l'application",
                {
                    "app/build.gradle",
                    "app/build.gradle.kts"
                }
            ),
            (
                "Manifeste Android",
                {
                    "app/src/main/androidmanifest.xml"
                }
            )
        ]

        for label, alternatives in expected_groups:
            if not paths.intersection(alternatives):
                messages.append(
                    "⚠️ " + label + " manquant."
                )
                ok = False
            else:
                messages.append(
                    "✅ " + label + " présent."
                )

        has_source = any(
            path.endswith(".kt") or path.endswith(".java")
            for path in paths
        )

        if has_source:
            messages.append("✅ Fichier source Kotlin/Java présent.")
        else:
            messages.append(
                "⚠️ Aucun fichier source Kotlin ou Java détecté."
            )
            ok = False

        has_readme = any(
            path == "readme.md"
            for path in paths
        )

        if has_readme:
            messages.append("✅ README présent.")
        else:
            messages.append(
                "⚠️ README absent : les instructions peuvent manquer."
            )

    else:
        has_html = any(
            path.endswith(".html")
            for path in paths
        )

        has_css = any(
            path.endswith(".css")
            for path in paths
        )

        has_js = any(
            path.endswith(".js")
            for path in paths
        )

        if has_html:
            messages.append("✅ Fichier HTML présent.")
        else:
            messages.append("⚠️ Aucun fichier HTML détecté.")
            ok = False

        if has_css:
            messages.append("✅ Fichier CSS présent.")
        else:
            messages.append(
                "⚠️ Aucun fichier CSS détecté. "
                "Le projet peut utiliser un autre style."
            )

        if has_js:
            messages.append("✅ Fichier JavaScript présent.")
        else:
            messages.append(
                "⚠️ Aucun fichier JavaScript détecté. "
                "Le projet peut être purement HTML/CSS."
            )

    if len(files) > 0:
        messages.append(
            "ℹ️ Nombre de fichiers vérifiés : "
            + str(len(files))
        )

    return {
        "ok": ok,
        "messages": messages
    }


def generate_project(description, platform):
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "La variable GEMINI_API_KEY est absente "
            "des variables d'environnement de Render."
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
- Inclus les ressources nécessaires si elles sont utiles.
- Inclus README.md avec les étapes de compilation.
- Utilise des versions de dépendances compatibles.
- N'affirme pas que le projet a été compilé ou testé.
"""
    else:
        platform_rules = """
PLATEFORME WEB :
- Génère une application Web organisée.
- Inclus les fichiers HTML, CSS et JavaScript nécessaires.
- Inclus README.md avec les instructions de lancement.
- Ajoute les fichiers de configuration nécessaires.
- Préfère une solution simple à lancer.
"""

    prompt = f"""
Tu es GENIUS APP AI, un ingénieur logiciel expérimenté.

Crée un projet logiciel à partir de cette demande :

{description}

PLATEFORME : {platform}

{platform_rules}

RÈGLES :
1. Fournis le contenu complet de chaque fichier.
2. Génère un projet cohérent, pas seulement des extraits.
3. Utilise des chemins relatifs à la racine.
4. N'inclus aucun secret, mot de passe ou clé API.
5. N'utilise aucun chemin absolu ni chemin contenant "..".
6. Limite le projet à {MAX_FILES} fichiers.
7. Privilégie les fichiers essentiels si le projet est grand.
8. Rédige les instructions en français.
9. Ne prétends pas avoir exécuté de tests ou une compilation.

RENVOIE UNIQUEMENT UN OBJET JSON VALIDE, sans Markdown :

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
        if exc.code == 429:
            raise RuntimeError(
                "Le quota Gemini est atteint. "
                "Attends sa réinitialisation avant de réessayer. "
                "Aucune nouvelle tentative automatique n'a été faite."
            )

        if exc.code in (401, 403):
            raise RuntimeError(
                "Gemini refuse la clé API ou son accès. "
                "Vérifie la configuration de Render."
            )

        if exc.code == 404:
            raise RuntimeError(
                "Le modèle Gemini configuré n'est pas disponible. "
                "Vérifie le nom du modèle."
            )

        if exc.code == 503:
            raise RuntimeError(
                "Gemini est temporairement indisponible. "
                "Attends quelques minutes avant de réessayer."
            )

        app.logger.warning(
            "Erreur Gemini HTTP : %s", exc.code
        )

        raise RuntimeError(
            "Gemini a renvoyé une erreur HTTP "
            + str(exc.code)
            + ". Réessaie plus tard."
        )

    except (URLError, TimeoutError):
        raise RuntimeError(
            "Impossible de joindre le service Gemini. "
            "Vérifie ta connexion et réessaie plus tard."
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
            raise ValueError("Réponse vide de Gemini.")

        project = extract_json(answer)

    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise RuntimeError(
            "La réponse de l'IA n'a pas pu être convertie "
            "en projet. Réessaie avec une description plus simple."
        )

    if not isinstance(project, dict):
        raise RuntimeError(
            "Le format du projet généré est incorrect."
        )

    raw_files = project.get("files")

    if not isinstance(raw_files, list) or not raw_files:
        raise RuntimeError(
            "L'IA n'a fourni aucun fichier exploitable."
        )

    files = []
    seen_paths = set()
    total_size = 0

    for item in raw_files[:MAX_FILES]:
        if not isinstance(item, dict):
            continue

        path = safe_project_path(item.get("path"))
        content = item.get("content")

        if path is None or not isinstance(content, str):
            continue

        if path in seen_paths:
            continue

        content_bytes = content.encode("utf-8")

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
            "Les fichiers générés sont vides ou invalides."
        )

    project_name = str(
        project.get("project_name", "mon-projet")
    )[:100]

    project = {
        "project_name": project_name,
        "summary": str(
            project.get(
                "summary",
                "Projet généré par GENIUS APP AI."
            )
        )[:3000],
        "instructions": str(
            project.get(
                "instructions",
                "Consulte le fichier README.md."
            )
        )[:10000],
        "files": files
    }

    # Vérification locale : aucune requête Gemini supplémentaire.
    project["checks"] = validate_project_structure(
        files,
        platform
    )

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
                "Utilise 5000 caractères maximum."
            )

        else:
            try:
                project = generate_project(
                    description,
                    platform
                )

                zip_data = create_zip(project)

                download_token = uuid.uuid4().hex

                safe_name = re.sub(
                    r"[^a-zA-Z0-9_-]+",
                    "-",
                    project["project_name"]
                ).strip("-")[:60] or "mon-projet"

                with bundles_lock:
                    bundles[download_token] = {
                        "created": time.time(),
                        "data": zip_data,
                        "name": safe_name
                    }

                clean_expired_bundles()
            except RuntimeError as exc:
                error = str(exc)

            except Exception:
                app.logger.exception(
                    "Erreur de génération du projet"
                )

                error = (
                    "Une erreur inattendue est survenue. "
                    "Réessaie plus tard."
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
                "Téléchargement expiré. "
                "Génère à nouveau le projet.",
                404
            )

        if time.time() - item["created"] > BUNDLE_TTL:
            bundles.pop(token, None)

            return (
                "Téléchargement expiré. "
                "Génère à nouveau le projet.",
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
           

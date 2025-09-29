import flask
from flask import Flask, render_template, request
from src.forms import parse_inflected_verb, inflect_verb_with_features, FV_CLASSES
from src.constants import VERB_FEATURE_VALUES

# --- Flask Application ---
app = Flask(__name__)

TEMPLATE_DEFAULTS = {
    "feature_options": VERB_FEATURE_VALUES,
    "fv_classes": FV_CLASSES,
}

@app.route('/')
def index():
    """Renders the main page."""
    return render_template("index.html", **TEMPLATE_DEFAULTS)

@app.route('/parse', methods=['POST'])
def handle_parse():
    """Handles the parsing form submission."""
    inflected_form = request.form.get('inflected_form', '')
    if not inflected_form:
        result = {"error": "Please enter a verb form."}
    else:
        result = parse_inflected_verb(inflected_form)
    return render_template(
        "index.html",
        parse_result=result,
        **TEMPLATE_DEFAULTS,
    )

@app.route('/inflect', methods=['POST'])
def handle_inflect():
    """Handles the inflection form submission."""
    verb_root = request.form.get('verb_root', '')
    features = {
        'tam': request.form.get('tam'),
        'deixis': request.form.get('deixis'),
        'class': request.form.get('class')
    }
    fv_class = request.form.get('fv_class')
    
    if not verb_root:
        result = "Please enter a verb root."
    else:
        result = inflect_verb_with_features(verb_root, fv_class, features)
        
    return render_template(
        "index.html",
        inflect_result=result,
        **TEMPLATE_DEFAULTS,
    )

if __name__ == '__main__':
    app.run(debug=True)
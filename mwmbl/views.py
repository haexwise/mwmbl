import justext
import requests
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django_htmx.http import push_url

from mwmbl.format import format_result
from mwmbl.search_setup import ranker

from justext.core import html_to_dom, ParagraphMaker, classify_paragraphs, revise_paragraph_classification, \
    LENGTH_LOW_DEFAULT, STOPWORDS_LOW_DEFAULT, MAX_LINK_DENSITY_DEFAULT, NO_HEADINGS_DEFAULT, LENGTH_HIGH_DEFAULT, \
    STOPWORDS_HIGH_DEFAULT, MAX_HEADING_DISTANCE_DEFAULT, DEFAULT_ENCODING, DEFAULT_ENC_ERRORS, preprocessor

from mwmbl.settings import NUM_EXTRACT_CHARS
from mwmbl.tinysearchengine.indexer import Document


def justext_with_dom(html_text, stoplist, length_low=LENGTH_LOW_DEFAULT,
        length_high=LENGTH_HIGH_DEFAULT, stopwords_low=STOPWORDS_LOW_DEFAULT,
        stopwords_high=STOPWORDS_HIGH_DEFAULT, max_link_density=MAX_LINK_DENSITY_DEFAULT,
        max_heading_distance=MAX_HEADING_DISTANCE_DEFAULT, no_headings=NO_HEADINGS_DEFAULT,
        encoding=None, default_encoding=DEFAULT_ENCODING,
        enc_errors=DEFAULT_ENC_ERRORS):
    """
    Converts an HTML page into a list of classified paragraphs. Each paragraph
    is represented as instance of class ˙˙justext.paragraph.Paragraph˙˙.
    """
    dom = html_to_dom(html_text, default_encoding, encoding, enc_errors)

    titles = dom.xpath("//title")
    title = titles[0].text if len(titles) > 0 else None

    dom = preprocessor(dom)

    paragraphs = ParagraphMaker.make_paragraphs(dom)

    classify_paragraphs(paragraphs, stoplist, length_low, length_high,
        stopwords_low, stopwords_high, max_link_density, no_headings)
    revise_paragraph_classification(paragraphs, max_heading_distance)

    return paragraphs, title


def index(request):
    query = request.GET.get("q")
    results = ranker.search(query) if query else None
    return render(request, "index.html", {
        "results": results,
        "query": query,
        "user": request.user,
    })


def home_fragment(request):
    query = request.GET["q"]
    results = ranker.search(query)
    response = render(request, "home.html", {"results": results, "query": query})
    current_url = request.htmx.current_url
    # Replace query string with new query
    stripped_url = current_url[:current_url.index("?")] if "?" in current_url else current_url
    query_string = "?q=" + query if len(query) > 0 else ""
    new_url = stripped_url + query_string
    # Set the htmx replace header
    response["HX-Replace-Url"] = new_url
    return response


def fetch_url(request):
    url = request.GET["url"]
    query = request.GET["query"]
    response = requests.get(url)
    paragraphs, title = justext_with_dom(response.content, justext.get_stoplist("English"))
    good_paragraphs = [p for p in paragraphs if p.class_type == 'good']

    extract = ' '.join([p.text for p in good_paragraphs])
    if len(extract) > NUM_EXTRACT_CHARS:
        extract = extract[:NUM_EXTRACT_CHARS - 1] + '…'

    result = Document(title=title, url=url, extract=extract, score=0.0)
    return render(request, "home.html", {
        "results": [format_result(result, query)],
        "query": query,
    })

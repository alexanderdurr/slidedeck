"""Code to convert the markdown source into the final HTML output
"""

import os
from collections import defaultdict
import codecs
import re
import jinja2
import markdown
from slidedeck.mdx_mathjax import MathJaxExtension
from slidedeck.mdx_bibtex import BibtexExtension
import git
import datetime

#############################################################################
# Globals
#############################################################################

# these are a set of regular expressions that are looked for in the markdown
# that provide metadata about the slide deck and are used to populate the
# title slide (at the beginning) and thank you slide (at the end)
#
# lines in the markdown that look like:
#
# % author: FirstName LastName
#
# Will be detected.
DECK_SETTINGS_RE = {
    'thankyou': u'^%\s*thankyou:\s*(.*)$',
    'thankyou_details': u'^%\s*thankyou_details:\s*(.*)$',
    'title': u'^%\s*title:\s*(.*)$',
    'subtitle': u'^%\s*subtitle:\s*(.*)$',
    'author': u'^%\s*author:\s*(.*)$',
    'contact': u'^%\s*contact:\s*(.*)$',
    'favicon': u'^%\s*favicon:\s*(.*)$',
    'bibliography': u'^%\s*bibliography:\s*(.*)$',
    'footer': u'^%\s*footer:([^#\n]*).*$'
}

#############################################################################
# Functions related to the render command
#############################################################################


def render_slides(md, template_fn):

    md, settings = parse_deck_settings(md)
    md_slides = md.split('\n---\n')
    print("Compiled {:d} slides.".format(len(md_slides)))
    print(settings)
    slides = []
    # Process each slide separately.
    for md_slide in md_slides:
        slide = {}
        sections = md_slide.split('\n\n')
        # Extract metadata at the beginning of the slide (look for key: value)
        # pairs.
        metadata_section = sections[0]
        metadata = parse_metadata(metadata_section)
        slide.update(metadata)
        remainder_index = metadata and 1 or 0
        # Get the content from the rest of the slide.
        extensions = [MathJaxExtension(),
                      'markdown.extensions.fenced_code',
                      'markdown.extensions.meta']

        # Bibfile
        bibfile = settings.get('bibliography', None)
        if bibfile:
            extensions.append(
                BibtexExtension(bibliography=bibfile))

        content_section = '\n\n'.join(sections[remainder_index:])
        html = markdown.markdown(content_section,
                                 extensions=extensions)
        slide['content'] = postprocess_html(html, metadata)

        slides.append(slide)

    template = jinja2.Template(open(template_fn).read())
    return template.render(locals())


def write_slides(slidestring, output_fn):
    with codecs.open(output_fn, 'w', encoding='utf8') as outfile:
        outfile.write(slidestring)


def process_slides(markdown_fn, output_fn, template_fn):
    if not os.path.exists(markdown_fn):
        raise OSError('The markdown file "%s" could not be found.' %
                      markdown_fn)
    md = codecs.open(markdown_fn, encoding='utf8').read()

    # Check for Dos\Windows line encoding \r\n and convert to unix style \n
    if '\r\n' in md:
        md = md.replace('\r\n', '\n')

    slides = render_slides(md, template_fn)
    write_slides(slides, output_fn)


def parse_footer(settings_footer):
    """
    This function takes a string, splits it per line
    and parses each line.

    Keywords 'git-hash' and 'git-date' is replaced with
    branch commit and commit date for the latest commit.
    """

    footer = settings_footer.split("<br/>")

    try:
        repo = git.Repo(search_parent_directories=True)
    except git.exc.InvalidGitRepositoryError:
        print("Warning: Not a valid git repository.")
    else:
        master = repo.active_branch

        for i, f in enumerate(footer):

            if f.strip().startswith("git-hash"):
                sha = repo.head.object.hexsha
                short_sha = repo.git.rev_parse(sha, short=1)

                if repo.tags and (repo.tags[0].commit == master.commit):
                    latest = repo.tags[0]
                else:
                    latest = short_sha

                footer[i] = "{} {}".format(master.name, latest)

            if f.strip().startswith("git-date"):
                latest_commit = datetime.datetime.fromtimestamp(
                    master.commit.committed_date)

                footer[i] = latest_commit.strftime('%Y-%m-%d')

    return " | ".join(footer) + " | "


def parse_deck_settings(md):
    """Parse global settings for the slide deck, such as the author and
    contact information.

    Parameters
    ----------
    md : unicode
        The full markdown source of the slides

    Returns
    -------
    md : unicode
        The markdown source, after the settings have been removed, such
        that they don't get actually put into the slides directly
    settings : dict
        A dict containing the settings. The keys wil be the set of keys
        in DECK_SETTINGS_RE, modulo the keys that were actually parsed
        from the document.
    """
    settings = defaultdict(lambda: [])
    for key, value in DECK_SETTINGS_RE.items():
        found = True
        while found:
            m = re.search(value, md, re.MULTILINE)
            if m:
                tmp = m.group(1)
                settings[key].append(tmp.strip())
                md = md.replace(m.group(0), '')
            else:
                found = False

    # if a setting is repeated, we join them together with a <br/> tag
    # in between.
    settings = {k: '<br/>'.join(v) for k, v in settings.items()}

    if 'footer' in settings.keys():
        settings['footer'] = parse_footer(settings['footer'])

    print("Parsed slide deck settings, and found setting for: {:s}.".format(
        ', '.join(settings.keys())))
    # strip off the newline characters at the beginning and end of the document
    # that might have been left
    md = md.strip()
    return md, settings


def parse_metadata(section):
    """Given the first part of a slide, returns metadata associated with it."""
    metadata = {}
    metadata_lines = section.split('\n')
    for line in metadata_lines:
        colon_index = line.find(':')
        if colon_index != -1:
            key = line[:colon_index].strip()
            val = line[colon_index + 1:].strip()
            metadata[key] = val

    return metadata


def postprocess_html(html, metadata):
    """Returns processed HTML to fit into the slide template format."""
    if metadata.get('build_lists') and metadata['build_lists'] == 'true':
        html = html.replace('<ul>', '<ul class="build">')
        html = html.replace('<ol>', '<ol class="build">')

    # html = html.replace('<code>', '<pre>')
    return html

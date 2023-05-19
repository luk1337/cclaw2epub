#!/usr/bin/env python3
import argparse
import inspect
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime

import jinja2 as jinja2
import requests
from bs4 import BeautifulSoup


@dataclass
class Chapter:
    name: str
    html: str


@dataclass
class Cover:
    src: str
    filename: str
    width: int
    height: int


@dataclass
class ToC:
    url: str
    title: str
    author: str
    published_time: str
    cover: Cover
    chapters: list
    images: list


class Book:
    def __init__(self, base: str):
        self.base = base

    def create_folder_structure(self):
        os.makedirs(self.base, exist_ok=True)
        os.makedirs(os.path.join(self.base, 'META-INF'), exist_ok=True)
        os.makedirs(os.path.join(self.base, 'OEBPS', 'Images'), exist_ok=True)
        os.makedirs(os.path.join(self.base, 'OEBPS', 'Text'), exist_ok=True)
        os.makedirs(os.path.join(self.base, 'OEBPS', 'Styles'), exist_ok=True)

        with open(os.path.join(self.base, 'META-INF', 'container.xml'), 'wt+') as file:
            file.write(inspect.cleandoc('''
                <?xml version="1.0" encoding="UTF-8"?>
                <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
                  <rootfiles>
                    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
                  </rootfiles>
                </container>
            '''))

        with open(os.path.join(self.base, 'OEBPS', 'Styles', 'stylesheet.css'), 'wt+') as file:
            file.write(inspect.cleandoc('''
                div.svg_outer {
                   display: block;
                   margin-bottom: 0;
                   margin-left: 0;
                   margin-right: 0;
                   margin-top: 0;
                   padding-bottom: 0;
                   padding-left: 0;
                   padding-right: 0;
                   padding-top: 0;
                   text-align: left;
                }

                div.svg_inner {
                   display: block;
                   text-align: center;
                }

                h1, h2 {
                   text-align: center;
                   page-break-before: always;
                   margin-bottom: 10%;
                   margin-top: 10%;
                }

                h3, h4, h5, h6 {
                   text-align: center;
                   margin-bottom: 15%;
                   margin-top: 10%;
                }

                ol, ul {
                   padding-left: 8%;
                }

                body {
                  margin: 2%;
                }

                p {
                  overflow-wrap: break-word;
                }

                dd, dt, dl {
                  padding: 0;
                  margin: 0;
                }

                img {
                   display: block;
                   min-height: 1em;
                   max-height: 100%;
                   max-width: 100%;
                   padding-bottom: 0;
                   padding-left: 0;
                   padding-right: 0;
                   padding-top: 0;
                   margin-left: auto;
                   margin-right: auto;
                   margin-bottom: 2%;
                   margin-top: 2%;
                }

                img.inline {
                   display: inline;
                   min-height: 1em;
                   margin-bottom: 0;
                   margin-top: 0;
                }

                .thumbcaption {
                  display: block;
                  font-size: 0.9em;
                  padding-right: 5%;
                  padding-left: 5%;
                }

                hr {
                   color: black;
                   background-color: black;
                   height: 2px;
                }

                a:link {
                   text-decoration: none;
                   color: #0B0080;
                }

                a:visited {
                   text-decoration: none;
                }

                a:hover {
                   text-decoration: underline;
                }

                a:active {
                   text-decoration: underline;
                }

                table {
                   width: 90%;
                   border-collapse: collapse;
                }

                table, th, td {
                   border: 1px solid black;
                }
            '''))

        with open(os.path.join(self.base, 'mimetype'), 'wt+') as file:
            file.write('application/epub+zip')

    @staticmethod
    def fetch_toc(url: str, author: str, volume: int):
        soup = BeautifulSoup(requests.get(url).text, features='html.parser')

        title = soup.find('h1', attrs={'class': 'entry-title'}).text[:-len(' ToC')]
        if volume:
            title += f', Vol. {volume}'
        cover = soup.find('div', attrs={'class': 'wp-block-image'}).find('img')
        published_time = datetime.fromisoformat(
            soup.find('meta', attrs={'property': 'article:published_time'}).attrs['content']
        ).strftime('%Y-%m-%dT%H:%M:%SZ')
        images = [cover.attrs['data-orig-file']]

        volumes = list(filter(lambda x: x.text.startswith('Volume'),
                              soup.find_all('h2', attrs={'class': 'wp-block-heading has-text-align-center'})))
        if volumes and not volume:
            sys.exit('Multi volume series detected, please use --volume to select the volume you want to use.')

        chapters = []

        for chapter in [x.find('a') for x in soup.find_all('p', attrs={'class': 'has-text-align-center'})]:
            href = chapter.attrs['href']

            if not href.startswith('https://cclawtranslations.home.blog/'):
                continue

            if volume:
                chapter_volume = chapter.parent.find_previous_sibling('h2', attrs={
                    'class': 'wp-block-heading has-text-align-center'
                }).text.split()[-1]

                if chapter_volume < volume:
                    continue

                if chapter_volume > volume:
                    break

            html = requests.get(href).text

            for img in BeautifulSoup(html, features='html.parser').find_all(attrs={'class': 'wp-block-image'}):
                images.append(img.find('img').attrs['data-orig-file'])

            chapters.append(Chapter(
                name=chapter.text,
                html=html
            ))

        return ToC(
            url=url,
            title=title,
            author=author,
            published_time=published_time,
            cover=Cover(
                src=cover.attrs['data-orig-file'],
                filename=cover.attrs['data-orig-file'].split('/')[-1],
                width=int(cover.attrs['data-orig-size'].split(',')[0]),
                height=int(cover.attrs['data-orig-size'].split(',')[1]),
            ),
            chapters=chapters,
            images=images
        )

    def fetch_images(self, urls: list):
        for url in urls:
            request = requests.get(url)
            filename = url.split('/')[-1]

            with open(os.path.join(self.base, 'OEBPS', 'Images', filename), 'wb') as file:
                file.write(request.content)

    def write_cover(self, cover: Cover):
        with open(os.path.join(self.base, 'OEBPS', 'Text', 'Cover.xhtml'), 'wt+') as file:
            file.write(jinja2.Environment().from_string(inspect.cleandoc('''
                <?xml version="1.0" encoding="utf-8"?>
                <!DOCTYPE html>
                <html xmlns="http://www.w3.org/1999/xhtml">
                  <head>
                    <title>Cover</title>
                    <link href="../Styles/stylesheet.css" type="text/css" rel="stylesheet" />
                  </head>
                  <body>
                    <div class="svg_outer svg_inner">
                      <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" height="99%" width="100%" version="1.1" preserveAspectRatio="xMidYMid meet" viewBox="0 0 {{ width }} {{ height }}">
                        <image xlink:href="../Images/{{ filename }}" width="{{ width }}" height="{{ height }}" />
                        <!-- {{ src }} -->
                      </svg>
                    </div>
                  </body>
                </html>
            ''')).render(
                src=cover.src,
                filename=cover.filename,
                width=cover.width,
                height=cover.height,
            ))

    def write_toc(self, toc: ToC):
        with open(os.path.join(self.base, 'OEBPS', 'toc.ncx'), 'wt+') as file:
            file.write(jinja2.Environment().from_string(inspect.cleandoc('''
                <?xml version="1.0" encoding="utf-8" ?>
                <ncx version="2005-1" xml:lang="en" xmlns="http://www.daisy.org/z3986/2005/ncx/">
                  <head>
                    <meta content="{{ url }}" name="dtb:uid"/>
                    <meta content="2" name="dtb:depth"/>
                    <meta content="0" name="dtb:totalPageCount"/>
                    <meta content="0" name="dtb:maxPageNumber"/>
                  </head>
                  <docTitle>
                    <text>{{ title }}</text>
                  </docTitle>
                  <navMap>
                  {%- for chapter in chapters %}
                    <navPoint id="chapter{{ loop.index }}" playOrder="{{ loop.index }}">
                       <navLabel>
                         <text>{{ chapter.name }}</text>
                       </navLabel>
                       <content src="Text/{{ chapter.name }}.xhtml"/>
                    </navPoint>
                  {%- endfor %}
                  </navMap>
                </ncx>
            ''')).render(
                url=toc.url,
                title=toc.title,
                chapters=toc.chapters,
            ))

        with open(os.path.join(self.base, 'OEBPS', 'Text', 'toc.xhtml'), 'wt+') as file:
            file.write(jinja2.Environment().from_string(inspect.cleandoc('''
                <?xml version="1.0" encoding="utf-8"?>
                <!DOCTYPE html>
                <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" xmlns:epub="http://www.idpf.org/2007/ops" lang="en">
                  <head>
                    <title>Table of Contents</title>
                  </head>
                  <body>
                    <nav epub:type="toc" id="toc">
                      <h1>Table of Contents</h1>
                      <ol>
                      {%- for chapter in chapters %}
                        <li>
                          <a href="../Text/{{ chapter.name }}.xhtml">{{ chapter.name }}</a>
                        </li>
                      {%- endfor %}
                      </ol>
                    </nav>
                  </body>
                </html>
            ''')).render(
                chapters=toc.chapters,
            ))

    def write_illustrations(self, chapter: Chapter):
        with open(os.path.join(self.base, 'OEBPS', 'Text', f'{chapter.name}.xhtml'), 'wt+') as file:
            images = []

            for img in BeautifulSoup(chapter.html, features='html.parser').find_all(attrs={'class': 'wp-block-image'}):
                images.append(img.find('img').attrs['data-orig-file'])

            file.write(jinja2.Environment().from_string(inspect.cleandoc('''
                <?xml version="1.0" encoding="utf-8"?>
                <!DOCTYPE html>
                <html xmlns="http://www.w3.org/1999/xhtml">
                  <head>
                    <title>{{ chapter.name }}</title>
                    <link href="../Styles/stylesheet.css" type="text/css" rel="stylesheet"/>
                  </head>
                  <body>
                    {%- for image in images %}
                      <p><img src="../Images/{{ image.split('/')[-1] }}"/></p>
                    {%- endfor %}
                  </body>
                </html>
            ''')).render(
                chapter=chapter,
                images=images,
            ))

    def write_chapters(self, chapters: list):
        for chapter in chapters:
            if chapter.name == 'Illustrations':
                self.write_illustrations(chapter)
                continue

            with open(os.path.join(self.base, 'OEBPS', 'Text', f'{chapter.name}.xhtml'), 'wt+') as file:
                soup = BeautifulSoup(chapter.html, features='html.parser')
                entry_content = soup.find('div', attrs={'class': 'entry-content'})

                # Remove all content prior to chapter name
                for p in entry_content.find_all('p'):
                    if not p.find_previous_sibling('h2', attrs={'class', 'wp-block-heading'}):
                        p.decompose()
                    else:
                        break

                # Remove unwanted elements
                if wordads_ad_wrapper := entry_content.find('div', attrs={'class': 'wordads-ad-wrapper'}):
                    wordads_ad_wrapper.decompose()
                entry_content.find('div', attrs={'class': 'sharedaddy'}).decompose()
                [x.decompose() for x in entry_content.find_all('div', attrs={'class': 'wp-block-spacer'})]
                if hr := entry_content.find('hr'):
                    hr.decompose()
                entry_content.find('script').decompose()
                if style := entry_content.find('style'):
                    style.decompose()

                # Remap images
                for image in entry_content.find_all('img'):
                    img = image
                    url = img.attrs['data-orig-file']
                    width, height = img.attrs['data-orig-size'].split(',')

                    image.replace_with(BeautifulSoup(inspect.cleandoc(f'''
                        <div class="svg_outer svg_inner">
                          <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" height="99%" width="100%" version="1.1" preserveAspectRatio="xMidYMid meet" viewBox="0 0 {width} {height}">
                            <image xlink:href="../Images/{url.split("/")[-1]}" width="{width}" height="{height}" />
                            <!-- {url} -->
                          </svg>
                        </div>
                    '''), features='html.parser'))

                file.write(jinja2.Environment().from_string(inspect.cleandoc('''
                    <?xml version="1.0" encoding="utf-8"?>
                    <!DOCTYPE html>
                    <html xmlns="http://www.w3.org/1999/xhtml">
                      <head>
                        <title>{{ chapter.name }}</title>
                        <link href="../Styles/stylesheet.css" type="text/css" rel="stylesheet"/>
                      </head>
                      <body>
                        {{ body|safe }}
                      </body>
                    </html>
                ''')).render(
                    chapter=chapter,
                    body=entry_content.encode_contents().decode().strip(),
                ))

    def write_content(self, toc: ToC):
        with open(os.path.join(self.base, 'OEBPS', 'content.opf'), 'wt+') as file:
            file.write(jinja2.Environment().from_string(inspect.cleandoc('''
                <?xml version="1.0" encoding="utf-8"?>
                <package version="3.0" unique-identifier="BookId" xmlns="http://www.idpf.org/2007/opf">
                  <metadata xmlns:opf="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/">
                    <dc:title>{{ toc.title }}</dc:title>
                    <dc:language>en</dc:language>
                    <dc:creator id="creator">{{ toc.author }}</dc:creator>
                    <meta refines="#creator" property="file-as">{{ toc.author }}</meta>
                    <meta refines="#creator" property="role">aut</meta>
                    <dc:identifier id="BookId">{{ toc.url }}</dc:identifier>
                    <meta property="dcterms:modified">{{ toc.published_time }} </meta>
                    <meta name="cover" content="image1" />
                    <meta refines="#BookId" property="identifier-type">URI</meta>
                  </metadata>
                  <manifest>
                    {%- for image in toc.images %}
                    {%- if image.endswith('.jpg') %}
                      <item id="image{{ loop.index }}" href="Images/{{ image.split('/')[-1] }}" media-type="image/jpeg"/>
                    {%- elif image.endswith('.png') %}
                      <item id="image{{ loop.index }}" href="Images/{{ image.split('/')[-1] }}" media-type="image/png"/>
                    {%- endif %}
                    {%- endfor %}
                    {%- for chapter in toc.chapters %}
                      <item id="xhtml{{ loop.index }}" href="Text/{{ chapter.name }}.xhtml" media-type="application/xhtml+xml" properties="svg"/>
                    {%- endfor %}
                    <item id="stylesheet" href="Styles/stylesheet.css" media-type="text/css"/>

                    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
                    <item id="cover" href="Text/Cover.xhtml" media-type="application/xhtml+xml" properties="svg"/>
                    <item id="nav" href="Text/toc.xhtml" media-type="application/xhtml+xml" properties="nav"/>
                  </manifest>
                  <spine toc="ncx">
                    <itemref idref="cover"/>
                    {%- for chapter in toc.chapters %}
                      <itemref idref="xhtml{{ loop.index }}"/>
                    {%- endfor %}
                    <itemref idref="nav"/>
                  </spine>
                  <guide>
                    <reference type="cover" title="Cover" href="Text/Cover.xhtml"/>
                  </guide>
                </package>
            ''')).render(
                toc=toc,
            ))

    def write_epub(self, out: str):
        shutil.make_archive(out, 'zip', self.base)
        shutil.move(f'{out}.zip', out)

    @staticmethod
    def build(toc_url: str, author: str, out: str, volume: int):
        with tempfile.TemporaryDirectory() as tmp_dir:
            book = Book(tmp_dir)
            toc = book.fetch_toc(toc_url, author, volume)

            book.create_folder_structure()
            book.fetch_images(toc.images)
            book.write_cover(toc.cover)
            book.write_toc(toc)
            book.write_content(toc)
            book.write_chapters(toc.chapters)
            book.write_epub(out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build epub file from CClaw Translations ToC')
    parser.add_argument('-a', '--author', help='Book author', required=True)
    parser.add_argument('-t', '--toc', help='URL to CClaw ToC', required=True)
    parser.add_argument('-v', '--volume', help='Volume')
    parser.add_argument('out', help='Output epub path')
    args = parser.parse_args()

    Book.build(toc_url=args.toc, author=args.author, volume=args.volume, out=args.out)

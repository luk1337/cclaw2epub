# cclaw2epub

## Usage
```
$ pip install -r requirements.txt
...
$ ./cclaw2epub.py \
    --author "Asakura Neru" \
    --toc "https://cclawtranslations.home.blog/watashi-no-yuri-mo-eigyou-da-to-omotta-toc/" \
    book.epub
$ ebook-meta book.epub
Title               : Watashi no Yuri mo, Eigyou da to Omotta?
Author(s)           : Asakura Neru [Asakura Neru]
Languages           : eng
$ ./cclaw2epub.py \
    --author "Amano Seiju" \
    --toc "https://cclawtranslations.home.blog/kurasu-no-daikirai-na-joshi-to-kekkon-suru-koto-ni-natta-toc/" \
    --volume 7 \
    book.epub
$ ebook-meta book.epub
Title               : Kurasu no Daikirai na Joshi to Kekkon Suru Koto ni Natta, Vol. 7
Author(s)           : Amano Seiju [Amano Seiju]
Languages           : eng
```

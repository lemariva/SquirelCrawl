# SquirelCrawl

This code compress a webpage into an html file. Images are converted to base64 and integrated together with CSS files in the html. Useful for webpages on microcontrollers (or low memory devices), a complete offline copy of a webpage etc.

Requirements
-------------------
The application was tested using [Python 2.7](https://www.python.org/download/releases/2.7/). The following libraries are required:

* [beautifulsoup4](https://pypi.python.org/pypi/beautifulsoup4)
* [requests](http://docs.python-requests.org/en/master/)
* [cssutils](https://pypi.python.org/pypi/cssutils/)
* [tinycss](https://pypi.python.org/pypi/tinycss)
* [htmlmin](https://pypi.python.org/pypi/htmlmin/)
* [jsmin](https://pypi.python.org/pypi/jsmin)
* [mincss2](https://pypi.python.org/pypi/mincss) (modified mincss library included)
* [pillow](https://pypi.python.org/pypi/Pillow)

These can be installed using [pip](https://packaging.python.org/tutorials/installing-packages/) as:
```
pip install <library>
```
A tutorial for installing `pip` on Windows can be found [here](https://github.com/BurntSushi/nfldb/wiki/Python-&-pip-Windows-installation). `pip` can be downloaded from [get-pip](https://pip.pypa.io/en/stable/installing/).

Use
--------------------
```
python squirelcrawl --url <http(s)://...> --path <folder>
```
Optional arguments are the following:
* `-iq (def.: 5)`: the images are compress before converted to base64, the option defines the image quality for the compression. Pillow library is used for the compression;
* `-csd (def.: 0)`: the css are crawled to search for image links (basically `background(-image): url(...)`). Only the used classes (in the html file) are searched. If this option is set, then all classes are crawled. This may need a lot of time;
* `-ie (def.: 1)`: the converted images are saved as `txt` in the `base64/` folder;
* `--mcss (def.: 0)`: unused css classes are removed using the `mincss` library. This option reduces substantially the size of the resulting html. But it does not always work great;
* `--cjs (def.: 0)`: if set, remove all `<script>...</script>` sections. Be careful, bootstrap css may need some JavaScript to look great;
* `--cmeta (def.: 0)`: if set, remove all `<meta .../>` sections; 
* `--clink (def.: 0)`: if set, remove all `<link .../>` sections;
* `--clink (def.: 0)`: if set, remove all `<a ...>...</a>` sections (including the texts)
* `--calinkref (def.: 1)`: if set, replace all `href` of the `<a>` sections with `javascript:a_links()` allowing to use a javascript to actuate while clicking;
* `--d (def.: 1`: if set, debugging info is displayed;
* `--overlay (def.: 0)`: combines the overlay(-body).[css, js, html] files in the html file (**);

(**) `squirelcrawl.py` requires the following files, if the `--overlay` option is set to `1`:

* `overlay.html` - two overlay divs are included, for submit/link purposes respectively (included at the end of the body section)
* `overlay.css` - includes the style for overlay.html (included in header section)
* `overlay.js` - includes the necessarily JavaScript for an overlay (included in header section)
* `overlay-body.js` - add the form actions to display the overlay (included at the end of the body section)

The files `overlay.html` and `overlay.css` can be modified by the user to include contain to the webpage.

The `path` folder is created and all files related are saved under this folder. Images and css files are saved in almost the same file structure of the website. A folder `base64` is created if the option `-ie` is set, and the converted to base64 images are saved as `txt` files. Two files are generated (if `--mcss`) is set:
* `index.html`: compressed webpage including css and images as based64 strings.
* `index-compressed.html`: same as `index.html` but the `<style>` sections (which include the css files) are compressed using `mincss` library. The file results very small, but it does not always work (style problems). 

Disclaimers
------------
The author of the code assumes no responsibility for users' decision-making and their code usage. 

License
--------------
Apache 2.0

Changelog
-----------
Revision 0.1: Initial submission.
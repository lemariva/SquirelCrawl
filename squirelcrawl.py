#Copyright [2017] [Mauro Riva - lemariva@gmail.com]
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.
# 
# Compress a webpage into a html file. Images are converted to base64 and integrated together with CSS files in the html.
# Disclaimer: 
# 1) The author of the code assumes no responsibility for users' decision making and their code usage. 
# 2) Use at your own risk!
#


import sys
import os
import argparse

from PIL import Image # pillow

import requests
import re
import base64
import shutil

import cssutils
from urlparse import urlparse
import tinycss

import htmlmin
from jsmin import jsmin

from bs4 import BeautifulSoup
from mincss2.processor import Processor


def make_dir(dir_path):
    if sys.version_info[0] < 3:
        try:
            os.stat(dir_path)
        except:
            os.makedirs(dir_path)     
    else:
        os.makedirs(dir_path, exist_ok=True)    

def img_base64(filename, contain):
    ext = filename.split(".")[-1]
    encoded_string = u"data:image/" + ext + ";base64," + base64.b64encode(contain)      
    
    txt = filename.split(".")[-2].split("/")[-1]
    with open(project_path + "/base64/" + txt + ".txt", "wb") as f:
        f.write(encoded_string.encode('utf-8'))
        f.close()
        
    #log_images_base64.append([filename, "\n\n", encoded_string, "\n\n"])
    return encoded_string

def compress_img(path, quality=5):
    # compress image
    file_ext = path.split(".")[-1]
    if(file_ext in ["jpg","png","gif"]):   
        image = Image.open(path)
        image.save(path, quality=quality, optimize=True)
        
def download_file(href, subdir = ""):
    if "http://" not in href and "https://" not in href:
        if "//" in href:
            path_s = href.split("/")
            file_name = ""
            for i in range(3, len(path_s)):
                file_name = file_name + "/" + path_s[i]
        else:
            file_name = href     
    
        if "http://" not in subdir and "https://" not in subdir:
            domain = '{uri.scheme}://{uri.netloc}{uri.path}'.format(uri=urlparse(site_name))      # with subdirectory not working!
            file_url = domain + subdir + "/" + file_name      
        else:
            domain = '{uri.scheme}://{uri.netloc}'.format(uri=urlparse(subdir)) 
            file_url = domain + file_name   
    else:
        file_url = href
        
    try:
        raw_data = requests.get(file_url, stream=True)
        
    except requests.exceptions.ConnectionError:
        error_links.append(file_url)
        return [0, 0]
    
    if verbose:
        print("--- Downloading file: {} status {}".format(file_url, raw_data.status_code))
    
    if raw_data.status_code != 200:
        error_links.append(file_url)  
        return [0, 0] 
    
    folder = ("/").join(urlparse(file_url).path.split("/")[:-1]) + "/"
    
    return raw_data, folder

def div_style(bs, tags):
    div_style = bs.findAll(tags, style=re.compile("background(-image)?:( )?url")) 
    
    for i in range(len(div_style)):
        img_url = re.findall('url\(([^)]+)\)',str(div_style[i]))[0]
        # cleaning possible " or '  
        img_url_clean = str(img_url).replace('"', '').replace("'", "")
        
        # downloading data
        raw_data, folder = download_file(img_url_clean)
        make_dir(project_path + folder)
        file_name = (img_url_clean.split("/")[-1]).split("?")[0]
        with open(project_path + folder + file_name, "wb") as f:
            shutil.copyfileobj(raw_data.raw, f)
            f.close()
        
        # compress image
        compress_img(project_path + folder + file_name, quality_img)
        
        url_links.append([img_url, project_path + folder + file_name])     
        
def urls_in_css(classes, css):
    parser = tinycss.make_parser()
    for rule in parser.parse_stylesheet(css).rules:
        try:
            path = rule.selector.as_css()
            path_split = path.split(".")
            for i in range(len(path_split)):
                if path_split[i] in classes or deep_classes:
                    if path_split[i] not in css_classes or deep_classes:
                        for d in rule.declarations:
                            for tok in d.value:
                                if tok.type == 'URI':
                                    yield tok.value
                        css_classes.append(path_split[i])
        except AttributeError:
            print "--- Warning reading css: There's no item with that code! Maybe base64 compression?" # base64 compression 
              
                   
def search_save_assets_img(bs, css, href = "/"):
    classes = [value 
               for element in bs.findAll(class_=True) 
               for value in element["class"]]
    ids = []
    for tag in bs.findAll(True,{'id':True}) :
        ids.append(tag['id'])
    
    classes = classes + ids
    
    # downloading img url in css
    for img_url in urls_in_css(classes, css):
        
        raw_data, folder = download_file(img_url)
        if(raw_data is 0):
            raw_data, folder = download_file(img_url, "/".join(href.split("/")[:-1]))
        
        if raw_data is not 0:
            # save img file
            make_dir(project_path + folder)
            file_name = (img_url.split("/")[-1]).split("?")[0]
            with open(project_path + folder + file_name, "wb") as f:
                shutil.copyfileobj(raw_data.raw, f)
                f.close()

            url_css.append([img_url, project_path + folder + file_name])    
            
def html_style(bs, tags):
    styles = bs.findAll(tags) 
    for i in range(len(styles)):
        search_save_assets_img(bs=bs, css=unicode(styles[i].string))
        
def save_asset(bs, tags, attr, check):
    links = bs.findAll(tags)
    for l in links:
        href = l.get(attr)
        if href is not None and href not in url_links:
            if check in href:
                href = l.get(attr)
                if verbose:
                    print("- Working with : {}".format(href))
                
                # downloading item
                raw_data, folder = download_file(href)         
                text = raw_data.text
                
                # search in asset for images and replacing with base64        
                search_save_assets_img(bs, text, href)
            
                for i in range(len(url_css)):
                    links_array = url_css[i]
                    if verbose:
                        print("--- Processing images (base64): {}".format(links_array[1]))
            
                    # compress image
                    compress_img(links_array[1], quality_img)

                    # converting img to base64 to replace in asset
                    with open(links_array[1], "rb") as image_file:       
                        encoded_string = img_base64(links_array[1], image_file.read());
                        text= text.replace(links_array[0], encoded_string)                
                
                # saving asset file
                make_dir(project_path + folder)
                file_name = (href.split("/")[-1]).split("?")[0]
                with open(project_path + folder + file_name, "wb") as f:
                    f.write(text.encode('utf-8'))
                    f.close()
                        
                url_links.append([href, project_path + folder + file_name])
                           
def save_imgs(bs, tags, attr):
    links = bs.findAll(tags)                                # saving imgs
    for l in links:    
        href = l.get(attr)
        if href is not None and href not in url_links:
            
            print("--- Working with : {}".format(href))
        
            raw_data, folder = download_file(href)
            
            if(raw_data is 0):
                raw_data, folder = download_file(href, "/".join(href.split("/")[:-1]))            
            # save imgs
            make_dir(project_path + folder)  
            file_name = (href.split("/")[-1]).split("?")[0]
            with open(project_path + folder + file_name, "wb") as f:
                shutil.copyfileobj(raw_data.raw, f)
                f.close()
    
            # compress image
            compress_img(project_path + folder + file_name, quality_img)
                    
            url_links.append([href, project_path + folder + file_name])    
            

def save_assets(bs, html_text):
    # saving .css
    save_asset(bs=bs, tags="link", attr="href", check=".css")  
    # div/span with style (background-img)
    div_style(bs=bs, tags="div")
    div_style(bs=bs, tags="span")
    # style in html
    html_style(bs=bs, tags="style")       
    # saving minimal js
    ### TODO
    # saving imgs
    save_imgs(bs=bs, tags="img", attr="src")                


def delete_tags(bs, tags, attr="", replace=""):
    divs_to_clean = bs.findAll(tags)
    
    if not attr: 
        if(verbose):
            print("- Cleaning: {} <{}> tag(s)".format(str(len(divs_to_clean)),tags))
        for i in range(len(divs_to_clean)):
            divs_to_clean[i].decompose()     
    else:
        if(verbose):
            print("- Cleaning {} from: {} <{}> tag(s)".format(attr,str(len(divs_to_clean)),tags))
        for i in range(len(divs_to_clean)):
            divs_to_clean[i][attr] = replace        

def add_contain(bs, path, filename, tag, target, replace=""):        
    file_ext = filename.split(".")[-1]    # to check js files to compress
    
    if add_overlay: # check option
        with open(path + "/" + filename, "rb") as overlay_file:
            overlay_tag = bs.new_tag(tag)
            overlay_txt = overlay_file.read()
            
            if replace is not "":
                overlay_txt = overlay_txt.replace(replace[0], replace[1]) 
            
            if file_ext is "js":
                overlay_tag.string = jsmin(overlay_txt) 
            else:
                overlay_tag.string = overlay_txt
            
            overlay_ref = bs.findAll(target)
            overlay_ref[0].append(overlay_tag)  
            overlay_file.close()    

def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')
    
def crawl(link):
    if "http://" not in link and "https://" not in link:
        link = site_name + link

    if site_name in link and link not in url_links:
        print("Webpage to analyse: {}".format(link))

        try:
            r = requests.get(link)
        except requests.exceptions.ConnectionError:
            print("Connection Error")
            sys.exit(1)

        if r.status_code != 200:
            print("Invalid Response")       
            sys.exit(1)
            
        # changing project_path to subdirectory
        
        print("Working directory : {}".format(project_path))
        text = r.content
            
        encoding = r.encoding if 'charset' in r.headers.get('content-type', '').lower() else None
        soup = BeautifulSoup(text, "html.parser", from_encoding=encoding)
        
        # processing assets
        save_assets(soup, text)
        
        # replacing path from assets
        for i in range(len(url_links)):
            # listing links
            links_array = url_links[i]
            if verbose:
                print("- Processing file:  {}".format(links_array[1]))
            
            # getting file extension 
            file_ext = links_array[1].split(".")[-1]
            # img and background-images
            if(file_ext in ["jpg","png","gif"]):   
                with open(links_array[1], "rb") as image_file:
                    base64_img = "data:image/" + file_ext + ";base64," + base64.b64encode(image_file.read())          
                    # backgroung images in div-style
                    div_style = soup.findAll('div', style=re.compile("background(-image)?:( )?url\("+links_array[0]+"\)"))   
                    if div_style:       
                        if(verbose):
                            print("---- found {} times".format(len(div_style)))
                        for j in range(len(div_style)):                         
                            style_replace = div_style[j].get('style').replace(links_array[0], base64_img)  #style_replace = div_style[j].find(string=re.compile("url"))
                            div_style[j]['style'] = style_replace                                          #style_replace.replaceWith(style_replace.string.replace(links_array[0], base64_img))                
                    # backgroung images in span-style
                    div_style = soup.findAll('span', style=re.compile("background(-image)?:( )?url\("+links_array[0]+"\)"))   
                    if div_style:       
                        if(verbose):
                            print("---- found {} times".format(len(div_style)))
                        for j in range(len(div_style)):                         
                            style_replace = div_style[j].get('style').replace(links_array[0], base64_img)
                            div_style[j]['style'] = style_replace                  
                    # images   
                    div_style = soup.findAll('img', src=re.compile(links_array[0]))  
                    if div_style:                    
                        div_style[0]['src'] = base64_img
            # external css
            else:                       
                with open(links_array[1], "rb") as ccs_file:
                    style_txt = ccs_file.read()
                    style_tag = soup.new_tag("style")
                    style_tag.string = unicode(style_txt)                    
                    style_ref = soup.findAll('link', attrs={'href': re.compile(links_array[1])})
                    # style found -> replace
                    if style_ref:
                        style_ref[0].replaceWith(style_tag)
                    # otherwise add style to header    
                    else:
                        style_ref = soup.findAll('head')
                        style_ref[0].append(style_tag)
                    ccs_file.close()
            
        # replacing images inside html style            
        for i in range(len(url_css)):
            links_array = url_css[i]
            if(verbose):
                print("--- Processing img in style:  {}".format(links_array[0]))
            # getting file extension 
            file_ext = links_array[1].split(".")[-1]
            
            #print(soup)  
            if(file_ext in ["jpg","png"]):   
                with open(links_array[1], "rb") as image_file:
                    base64_img = img_base64(links_array[1], image_file.read())
                    div_style = soup.findAll('style', string=re.compile("background(-image)?:( )?url\("+links_array[0]+"\)"))
                    if div_style:
                        if(verbose):
                            print("found ", len(div_style), " times")
                        for j in range(len(div_style)):
                            style_replace = div_style[j].find(string=re.compile("url"))
                            style_replace.replaceWith(style_replace.string.replace(links_array[0], base64_img))
                    image_file.close()
        

        # cleaning to reduce index size
        if delete_js:
            delete_tags(soup, "script")
        if delete_meta:       
            delete_tags(soup, "meta")
        if delete_link:
            delete_tags(soup, "link")
        if delete_alink:
            delete_tags(soup, "a")            
        if delete_linkref:
            delete_tags(soup, "a", "href", "javascript:a_links();")     
            delete_tags(soup, "a", "target", "") 
           
        # adding overlayer    
        add_contain(soup, base_dir, "overlay.html", "div", "body");
        add_contain(soup, base_dir, "overlay.js", "script", "head");
        add_contain(soup, base_dir, "overlay.css", "style", "head");

        # modify for tag actions/ids for overlay message
        divs_form = soup.findAll('form')
        for i in range(len(divs_form)):
            form_id = divs_form[i].get('id')
            if not form_id:
                form_id =  "temp"+str(i)
                divs_form[i]['id'] = form_id
            divs_form[i]['action'] = ""       
            add_contain(soup, base_dir, "overlay-body.js", "script", "body", ["#overlay#", form_id]);

        # write index.html file
        with open(project_path + "/index.html", "wb") as f:
            text = htmlmin.minify(soup.prettify(formatter="minimal"), remove_comments=True, remove_all_empty_space=True)
            text = text.replace("&lt;","<")     # encoding problems! (escape string) -> TODO
            text = text.replace("&gt;",">")     # encoding problems! (escape string) -> TODO
            f.write(text.encode('utf-8'))
            f.close()      
             
        # reduce-css using mincss
        if css_compress:
            p.process(project_path + "/index.html")
            divs_to_clean = soup.findAll('style')
            for i in range(len(divs_to_clean)):
                divs_to_clean[i].decompose()   
            if(verbose):
                print("- Cleaning: {} <style> tag(s)". format(len(divs_to_clean)))            
            
            for each in p.inlines:
                style_tag = soup.new_tag("style")
                style_tag.string = unicode(each.after) 
                style_ref = soup.findAll('head')
                style_ref[0].append(style_tag)            
    
            if(verbose):
                print("- Added: {} <style> compressed tag(s)". format(len(p.inlines)))    
            
            # adding again external css for overlayer
            add_contain(soup, base_dir, "overlay.css", "style", "head");
      
            # write index-compressed.html file
            with open(project_path + "/index-compressed.html", "wb") as f:
                text = htmlmin.minify(soup.prettify(formatter="minimal"), remove_comments=True, remove_all_empty_space=True)
                text = text.replace("&lt;","<")     # encoding problems! (escape string) -> TODO
                text = text.replace("&gt;",">")     # encoding problems! (escape string) -> TODO
                f.write(text.encode('utf-8'))
                f.close()
            
# main

reload(sys)  
sys.setdefaultencoding('utf8')
base_dir = os.getcwd()

p = Processor(phantomjs=False)

try:

    parser = argparse.ArgumentParser(description='Compress a webpage into an html file. Images are converted to base64 and integrated together with CSS files in the html file. Disclaimer:  The author of the code assumes no responsibility for users\' decision-making and their code usage. ')
    parser.add_argument('--url', metavar='url', type=str, help='webpage url including http(s)://', required=True)
    parser.add_argument('--path', metavar='path', type=str, help='project name / folder where the downloaded files are saved', required=True)
    parser.add_argument('--iq', metavar = 'imgq', type=int, default=5, help='compress quality images (default=5)') 
    parser.add_argument('--csd', metavar = 'cssdeep', type=str2bool, nargs='?', default=0, help='analyse unused css-classes to image-urls. More time needed if activated. (default=0)')
    parser.add_argument('--ie', metavar = 'image', type=str2bool, nargs='?', default=1, help='export the base64 converted image into base64 (default=1)')
    parser.add_argument('--overlay', metavar = 'overlay', type=str2bool, nargs='?', default=1, help='combines the overlay(-body).[css, js, html] files in the html file (default=1)')
    parser.add_argument('--mcss', metavar = 'mincss', type=str2bool, nargs='?', default=1, help='compress the css to reduce file size (uses mincss libs). Generates a second file index-compressed.html (default=1)')    
    parser.add_argument('--cjs', metavar = 'cleanjs', type=str2bool, nargs='?', default=0, help='eliminate all javascript <script> sections to reduce space (default=0)')
    parser.add_argument('--cmeta', metavar = 'cleanmeta', type=str2bool, nargs='?', default=0, help='eliminate all <meta> sections to reduce space (default=0)')
    parser.add_argument('--clink', metavar = 'cleanlink', type=str2bool, nargs='?', default=0, help='eliminate all <link .../> sections to reduce space (default=0)')
    parser.add_argument('--calink', metavar = 'cleanalink', type=str2bool, nargs='?', default=0, help='eliminate all <a> sections to reduce space (default=0)')
    parser.add_argument('--calinkref', metavar = 'cleanalinkref', type=str2bool, nargs='?', default=1, help='replace all <a href="...">...</a> with <a href="javascript:a_links()">...</a> to pop an overlay (default=1)')
    parser.add_argument('--d', metavar='debug', type=str2bool, nargs='?', default=1, help='debugging activated (default=0)')
    
    args = parser.parse_args()
    
    # getting values from shell
    verbose = args.d
    site_name = args.url
    project_name = args.path
    deep_classes = args.csd
    quality_img = args.iq
    base64export = args.ie
    css_compress = args.mcss
    
    delete_js = args.cjs
    delete_meta = args.cmeta
    delete_link = args.clink
    delete_alink = args.calink
    delete_linkref = args.calinkref
  
    add_overlay = args.overlay
    
except IndexError:
    print("Usage:\npython app.py --url www.example.com --path folder_name")
    sys.exit(1)

# make main directory
project_path = base_dir + "/" + project_name
make_dir(project_path)

# sub paths
path_s = site_name.split("/")
file_directory = ""
for i in range(3, len(path_s)):
    file_directory = file_directory + "/" + path_s[i]

if(len(file_directory)>0):
    if file_directory[len(file_directory) - 1] != "/":
        file_directory = file_directory + "/"
        
project_path = os.path.dirname(project_path + "/" + file_directory.split("/")[-1])

# make sub directories
make_dir(project_path)
# make base64 directory
make_dir(project_path + "/base64")

# global variables    
url_links = []
url_css = []
css_classes = []
error_links = []

# starting crawling the website
crawl(site_name)

# listing url_links & error_links
print("\n\nLinks crawled\n")
for link in url_links:
    print("--- {}".format(link[0]))
    
for link in url_css:
    print("--- {}".format(link[0]))
        
print("\n\nLinks with error\n")
for link in error_links:
    print("--- {}".format(link[0]))
    

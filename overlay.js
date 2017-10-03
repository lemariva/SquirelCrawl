/*
 * Created by Martin Giger
 * This Source Code Form is subject to the terms of the Mozilla Public License,
 * v. 2.0. If a copy of the MPL was not distributed with this file, You can
 * obtain one at http://mozilla.org/MPL/2.0/.
 */

function Overlay(el) {
        this._overlay = el;

        this.hide = this.hide.bind(this);
        this._prevent = this._prevent.bind(this);
        this._keyboardHide = this._keyboardHide.bind(this);

        this._overlay.addEventListener("click", this.hide, false);
        this._overlay.classList.add("so-backdrop");

        var dialog = this.getDialog();
        dialog.addEventListener("click", this._prevent, true);
        dialog.addEventListener("keyup", this._keyboardHide, false);
}

Overlay.prototype = {
    _overlay: "",
    getMain: function() {
        var main = document.getElementsByTagName("MAIN");
        if(main.length == 0) {
            main = document.querySelector("[role='main']");
        }
        else {
            main = main[0];
        }
        return main;
    },
    getDialog: function() {
        var dialog = this._overlay.getElementsByTagName("DIALOG");
        if(dialog.length == 0) {
            dialog = this._overlay.querySelector("[role='dialog']");
        }
        else {
            dialog = dialog[0];
        }
        return dialog;
    },
    get isShowing() {
        return !this._overlay.hasAttribute("hidden");
    },
    show: function() {
        this._overlay.removeAttribute("hidden");
        //this.getMain().setAttribute("aria-hidden", true);
        var dialog = this.getDialog();
        dialog.setAttribute("tabindex", 0);
        dialog.focus();
        this._emit("show");
    },
    hide: function() {
        this._overlay.setAttribute("hidden", true);
        //var main = this.getMain();
        //main.setAttribute("aria-hidden", false);
        //main.focus();
        this.getDialog().removeAttribute("tabindex");
        this._emit("hide");
    },
    _prevent: function(e) {
        if("stopPropagation" in e)
            e.stopPropagation();
        else
            e.preventBubble();
    },
    _keyboardHide: function(e) {
        if(e.key == "Esc" || e.key == "Escape" || e.keyCode == 23) {
            this.hide();
        }
    },
    _emit: function(name) {
        var e = new Event(name);
        return this._overlay.dispatchEvent(e);
    }
};

function a_links()
{
    var overlay_links = new Overlay(document.getElementById("overlay-links"));
    overlay_links.show();
}


